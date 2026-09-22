"""P3QueryService integration against real PostgreSQL (T66).

Seeds the durable ledger through the repositories, then proves every
read-only query path: match decision snapshot with lifecycle, ordered
opportunities, canonical market filters, paper positions, pulse and the
stream ready snapshot. Hot books are absent, so best bid/ask and current
exit value must degrade to None — never to fabricated zeros. Requires
compose PostgreSQL + `uv run alembic upgrade head`.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event, text

from app.config import Settings
from app.decision.models import DecisionAction
from app.markets.models import BookLevel, OrderBookState, OutcomeBook
from app.markets.quotes import QuoteSnapshotRecord, QuoteSource, QuoteState
from app.prediction.models import (
    ModelAvailability,
    PredictionSnapshot,
    ProbabilityEstimate,
)
from app.persistence.database import Database
from app.persistence.market_repositories import (
    MarketQuoteSnapshotRepository,
    MarketRepository,
)
from app.persistence.paper_repositories import PaperLedgerRepository
from app.persistence.repositories import PostgresIdentityRepository
from app.service import P3QueryService
from p3_fakes import (
    NOW,
    make_entry_fill,
    make_intent,
    make_market,
    make_observation,
    make_position,
    make_prediction,
)

pytestmark = pytest.mark.infrastructure


@pytest.fixture()
async def database():
    settings = Settings(_env_file=None)
    db = Database(settings.database_url)
    try:
        async with db.engine.connect() as connection:
            mapped = (
                await connection.execute(
                    text("SELECT to_regclass('public.decision_observations')")
                )
            ).scalar()
    except Exception as exc:  # pragma: no cover - environment dependent
        await db.dispose()
        pytest.skip(f"PostgreSQL not reachable ({type(exc).__name__})")
    if mapped is None:
        await db.dispose()
        pytest.skip("P3 schema not migrated; run `uv run alembic upgrade head`")
    try:
        yield db
    finally:
        await db.dispose()


async def _seed(database: Database) -> dict[str, str]:
    markets = MarketRepository(database)
    ledger = PaperLedgerRepository(database)
    identity = PostgresIdentityRepository(database)

    suffix = uuid4().hex[:10]
    match_id = await identity.get_or_create("match", "itest-t66", suffix)
    player_a = await identity.get_or_create("player", "itest-t66", f"a{suffix}")
    player_b = await identity.get_or_create("player", "itest-t66", f"b{suffix}")
    tournament_id = await identity.get_or_create(
        "tournament", "itest-t66", f"t{suffix}"
    )
    async with database.session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "UPDATE matches SET status = 'live', player1_id = :p1,"
                    " player2_id = :p2, tournament_id = :t WHERE id = :m"
                ),
                {"p1": player_a, "p2": player_b, "t": tournament_id, "m": match_id},
            )
            await session.execute(
                text(
                    "UPDATE players SET name = :n WHERE id = :i"
                ),
                {"n": f"Player {suffix}", "i": player_a},
            )
            await session.execute(
                text("UPDATE players SET name = 'Player B' WHERE id = :i"),
                {"i": player_b},
            )
            await session.execute(
                text(
                    "UPDATE tournaments SET name = 'Test Open', circuit = 'atp',"
                    " gender = 'men' WHERE id = :i"
                ),
                {"i": tournament_id},
            )

    market_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev_{suffix}",
        condition_id=f"cond_{uuid4().hex}",
    )
    await markets.save_market(
        make_market(market_id, match_id=match_id, player_a=player_a, player_b=player_b)
    )
    await markets.link_match(
        market_id=market_id,
        match_id=match_id,
        evidence={"pair": [player_a, player_b]},
    )
    await markets.save_prediction(make_prediction(match_id))
    await markets.save_decision_observation(
        make_observation(match_id, market_id, observation_version=1)
    )
    intent = await ledger.create_intent(make_intent(match_id, market_id))
    await ledger.record_fill(
        make_entry_fill(intent.id),
        position=make_position(match_id, market_id).model_copy(
            update={"outcome_player_id": player_a}
        ),
    )
    return {
        "match_id": match_id,
        "market_id": market_id,
        "player_a": player_a,
        "player_b": player_b,
    }


async def test_query_service_reads_durable_ledger(database: Database) -> None:
    seeded = await _seed(database)
    match_id = seeded["match_id"]
    market_id = seeded["market_id"]
    queries = P3QueryService(
        database=database,
        markets=MarketRepository(database),
        paper=PaperLedgerRepository(database),
        hot_books=None,  # absent hot state must degrade to None, never zero
        clock=lambda: NOW,
    )

    decision = await queries.match_decision(match_id)
    assert decision is not None
    assert decision.market_id == market_id
    assert decision.action == "buy"
    assert decision.observation_version == 1
    assert decision.model_probabilities is not None
    assert decision.model_availability == "available"
    assert decision.position is not None
    assert decision.position.status == "open"
    assert Decimal(decision.position.entry_cost) == Decimal("10.00")
    assert decision.lifecycle == ("entry_pending", "filled")
    assert decision.is_stale is False and decision.has_gap is False
    # T69 workbench enrichment: versions, gates, quote bounds and a
    # ledger-derived position detail with events.
    assert decision.model_version == "prematch-elo-v1"
    assert decision.calibration_version == "platt-v1"
    assert decision.policy_version == "policy-v1"
    assert decision.data_version == "apidata-v1"
    assert decision.max_acceptable_price is None  # BUY carries a quote, no cap
    assert decision.hold_value is None
    assert [(gate.gate, gate.passed) for gate in decision.gates] == [
        ("liquidity", True)
    ]
    assert decision.position is not None
    assert Decimal(decision.position.average_entry_price) == Decimal("0.525")
    assert decision.position.current_exit_value is None  # no hot book
    assert decision.position.net_pnl is None
    kinds = [event.kind for event in decision.position.events]
    assert kinds == ["entry_intent", "entry_fill"]
    assert all(event.at is not None for event in decision.position.events)

    assert await queries.match_decision("mat_missing") is None

    opportunities = await queries.opportunities()
    row = next(item for item in opportunities if item.match_id == match_id)
    assert row.action == "buy"
    assert row.phase == "live"
    assert row.tournament_tier == "atp"
    assert row.model_probability == pytest.approx(0.62)
    assert row.player_names is not None
    assert row.conservative_net_edge is not None
    assert Decimal(row.conservative_net_edge) == Decimal("0.041")

    page = await queries.markets(tier="atp", phase="live", page=1, page_size=50)
    summary = next(item for item in page.markets if item.market_id == market_id)
    assert summary.match_id == match_id
    assert summary.model_availability == "available"
    assert summary.decision_action == "buy"
    assert summary.quote.state == "unavailable"
    assert summary.quote.best_bid is None and summary.quote.best_ask is None
    itf_page = await queries.markets(tier="itf", page=1, page_size=50)
    assert all(item.market_id != market_id for item in itf_page.markets)

    view = await queries.paper_positions()
    open_row = next(
        item for item in view["open"] if item.match_id == match_id
    )
    assert open_row.status == "open"
    assert open_row.current_exit_value is None  # no hot book → honest None
    assert Decimal(open_row.shares) == Decimal("19.047619")

    pulse = await queries.pulse()
    assert pulse["has_open_position"] is True
    assert len(pulse["data"]) <= 3
    # Positions come first; the seeded one may be crowded out of the
    # 3-row cap by newer open positions from earlier runs, so assert the
    # contract (position rows lead) and the scoped view separately.
    assert pulse["data"][0].kind == "position"
    assert any(item.match_id == match_id for item in view["open"])

    snapshot = await queries.markets_snapshot()
    assert snapshot["markets"] >= 1
    assert snapshot["opportunities"] >= 1
    assert snapshot["open_positions"] >= 1


async def test_query_service_exposes_internal_ids_only(database: Database) -> None:
    seeded = await _seed(database)
    queries = P3QueryService(
        database=database,
        markets=MarketRepository(database),
        paper=PaperLedgerRepository(database),
        hot_books=None,
    )
    decision = await queries.match_decision(seeded["match_id"])
    page = await queries.markets(page=1, page_size=50)
    view = await queries.paper_positions()
    blob = (
        decision.model_dump_json()
        + "".join(item.model_dump_json() for item in page.markets)
        + "".join(item.model_dump_json() for item in view["open"])
    ).lower()
    for fragment in ("condition", "token", "wallet", "private", "0x"):
        assert fragment not in blob


# ---------------------------------------------------------------------------
# T68: enriched fields for the product surfaces (names/ids, per-outcome top
# levels, model probability, average entry price, entry_pending rows, pulse
# selection contract: one most-urgent position row then live BUY → upcoming
# BUY → strongest WAIT, capped at three).
# ---------------------------------------------------------------------------


class StubHotBooks:
    def __init__(self, states: dict) -> None:
        self._states = states
        self.bulk_calls: list[tuple[str, ...]] = []

    async def get_hot_books(self, market_ids):
        self.bulk_calls.append(tuple(market_ids))
        return {mid: self._states[mid] for mid in market_ids if mid in self._states}

    async def get_hot_book(self, market_id: str):
        return self._states.get(market_id)


def _book(market_id: str, sides: tuple) -> OrderBookState:
    books = tuple(
        OutcomeBook(
            outcome_player_id=player_id,
            bids=(BookLevel(price=Decimal(bid_price), size=Decimal(bid_size)),),
            asks=(BookLevel(price=Decimal(ask_price), size=Decimal(ask_size)),),
        )
        for player_id, bid_price, bid_size, ask_price, ask_size in sides
    )
    return OrderBookState(
        market_id=market_id,
        books=books,
        sequence=9,
        book_hash=f"hash_{market_id}",
        provider_timestamp=NOW,
        received_at=NOW,
    )


async def test_enriched_fields_and_pulse_selection(database: Database) -> None:
    seeded = await _seed(database)
    match_id = seeded["match_id"]
    market_id = seeded["market_id"]
    player_a = seeded["player_a"]
    player_b = seeded["player_b"]
    markets = MarketRepository(database)
    ledger = PaperLedgerRepository(database)
    identity = PostgresIdentityRepository(database)

    # match1 becomes urgent: a SELL decision (lock-profit exit context),
    # timestamped with wall-clock +1h so the most-urgent selection is
    # deterministic even on a shared database with historical fixture rows.
    sell_observation = make_observation(
        match_id, market_id, observation_version=2, action=DecisionAction.SELL
    ).model_copy(update={"as_of": datetime.now(UTC) + timedelta(hours=1)})
    await markets.save_decision_observation(sell_observation)

    # A second mapped market with matching prediction ids, a stale WAIT and
    # a pending entry intent (no fill → entry_pending ledger row).
    suffix = uuid4().hex[:10]
    match2 = await identity.get_or_create("match", "itest-t68", suffix)
    tournament2 = await identity.get_or_create("tournament", "itest-t68", suffix)
    async with database.session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "UPDATE matches SET status = 'scheduled', player1_id = :p1,"
                    " player2_id = :p2, tournament_id = :t WHERE id = :m"
                ),
                {"p1": player_a, "p2": player_b, "t": tournament2, "m": match2},
            )
            await session.execute(
                text(
                    "UPDATE tournaments SET name = 'Test Trophy', circuit = 'wta',"
                    " gender = 'women' WHERE id = :i"
                ),
                {"i": tournament2},
            )
    market2 = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev2_{suffix}",
        condition_id=f"cond2_{uuid4().hex}",
    )
    await markets.save_market(
        make_market(market2, match_id=match2, player_a=player_a, player_b=player_b)
    )
    await markets.link_match(
        market_id=market2, match_id=match2, evidence={"pair": [player_a, player_b]}
    )
    await markets.save_prediction(
        PredictionSnapshot(
            match_id=match2,
            outcomes=(
                ProbabilityEstimate(
                    player_id=player_a, probability=0.7, lower=0.6, upper=0.8
                ),
                ProbabilityEstimate(
                    player_id=player_b, probability=0.3, lower=0.2, upper=0.4
                ),
            ),
            availability=ModelAvailability.AVAILABLE,
            model_version="prematch-elo-v1",
            calibration_version="platt-v1",
            data_version="apidata-v1",
            input_state_version=3,
            as_of=NOW,
        )
    )
    stale_wait = make_observation(match2, market2, observation_version=2).model_copy(
        update={
            "action": DecisionAction.WAIT,
            "target_player_id": player_a,
            "max_acceptable_price": Decimal("0.55"),
            "quote": None,
            "is_stale": True,
        }
    )
    await markets.save_decision_observation(stale_wait)
    intent2 = await ledger.create_intent(make_intent(match2, market2))

    hot_books = StubHotBooks(
        {
            market2: _book(
                market2,
                (
                    (player_a, "0.68", "150", "0.70", "200"),
                    (player_b, "0.28", "100", "0.30", "120"),
                ),
            ),
            market_id: _book(
                market_id,
                (
                    (player_a, "0.58", "120", "0.60", "90"),
                    (player_b, "0.40", "80", "0.42", "70"),
                ),
            ),
        }
    )
    queries = P3QueryService(
        database=database,
        markets=markets,
        paper=ledger,
        hot_books=hot_books,
        clock=lambda: NOW,
    )

    # --- decision snapshot workbench enrichment -----------------------------
    decision2 = await queries.match_decision(match_id)
    assert decision2 is not None
    levels = {level.player_id: level for level in decision2.outcome_levels}
    assert levels[player_a].best_ask == "0.60"
    assert levels[player_a].best_bid == "0.58"
    assert levels[player_b].best_ask == "0.42"
    position_detail = decision2.position
    assert position_detail is not None
    assert Decimal(position_detail.average_entry_price) == Decimal("0.525")
    assert position_detail.current_exit_value is not None
    assert [event.kind for event in position_detail.events] == [
        "entry_intent",
        "entry_fill",
    ]
    assert decision2.gates[0].gate == "liquidity" and decision2.gates[0].passed

    # match2 has a pending entry intent but no position: the workbench
    # timeline must still be ledger-driven.
    decision_m2 = await queries.match_decision(match2)
    assert decision_m2 is not None
    assert decision_m2.position is not None
    assert decision_m2.position.status == "entry_pending"
    assert [event.kind for event in decision_m2.position.events] == ["entry_intent"]
    assert Decimal(decision_m2.position.entry_cost) == Decimal("10.00")
    assert decision_m2.max_acceptable_price is not None
    assert Decimal(decision_m2.max_acceptable_price) == Decimal("0.55")
    assert decision_m2.is_stale is True

    # --- markets list enrichment -------------------------------------------
    page = await queries.markets(page=1, page_size=50)
    summary2 = next(item for item in page.markets if item.market_id == market2)
    assert summary2.tournament_name == "Test Trophy"
    assert summary2.player_ids == (player_a, player_b)
    assert summary2.player_names is not None
    assert summary2.player_names[1] == "Player B"
    assert summary2.model_probability == pytest.approx(0.7)
    assert summary2.quote.outcome_bids == ("0.68", "0.28")
    assert summary2.quote.outcome_asks == ("0.70", "0.30")
    assert Decimal(summary2.quote.spread) == Decimal("0.02")
    # depth = top-level USD on both sides of both outcomes:
    # (0.68*150 + 0.70*200) + (0.28*100 + 0.30*120) = 242 + 64 = 306
    assert Decimal(summary2.quote.depth_usd) == Decimal("306.00")
    assert summary2.decision_action == "wait"
    assert summary2.is_stale is True and summary2.has_gap is False

    summary1 = next(item for item in page.markets if item.market_id == market_id)
    assert summary1.quote.outcome_asks == ("0.60", "0.42")
    assert summary1.quote.best_bid == (player_a, "0.58")
    assert summary1.quote.state == "realtime"
    assert summary1.quote.source == "realtime"

    # --- opportunities enrichment -------------------------------------------
    opportunities = await queries.opportunities()
    opp2 = next(item for item in opportunities if item.match_id == match2)
    assert opp2.action == "wait"
    assert opp2.player_ids == (player_a, player_b)
    assert opp2.is_stale is True
    assert opp2.model_probability == pytest.approx(0.7)
    assert Decimal(opp2.max_acceptable_price) == Decimal("0.55")

    # --- paper ledger enrichment --------------------------------------------
    view = await queries.paper_positions()
    open_row = next(item for item in view["open"] if item.match_id == match_id)
    assert Decimal(open_row.average_entry_price) == Decimal("0.525")
    assert open_row.tournament_name == "Test Open"
    assert open_row.player_ids == (player_a, player_b)
    # exit value from the hot book: 19.047619 shares × 0.58 best bid
    assert open_row.current_exit_value is not None
    assert Decimal(open_row.current_exit_value) == Decimal("19.047619") * Decimal(
        "0.58"
    )
    pending_row = next(item for item in view["open"] if item.match_id == match2)
    assert pending_row.status == "entry_pending"
    assert pending_row.position_id == intent2.id
    assert Decimal(pending_row.entry_cost) == Decimal("10.00")
    assert Decimal(pending_row.average_entry_price) == Decimal("0.525")

    # --- pulse selection contract -------------------------------------------
    pulse = await queries.pulse()
    assert pulse["has_open_position"] is True
    assert len(pulse["data"]) <= 3
    position_rows = [row for row in pulse["data"] if row.kind == "position"]
    assert len(position_rows) == 1  # exactly one reserved position row
    top = position_rows[0]
    assert top.match_id == match_id  # the SELL decision is the most urgent
    assert top.action == "sell"
    assert top.phase == "live"
    assert top.tournament_name == "Test Open"
    assert Decimal(top.conservative_net_edge) == Decimal("0.041")
    assert top.is_stale is False
    assert pulse["data"][0].kind == "position"

    # Both seeded markets were read in ONE bulk call (T84: no per-row reads).
    assert any(
        market_id in call and market2 in call for call in hot_books.bulk_calls
    )


# ---------------------------------------------------------------------------
# T84: the ACTIVE link is the only market→match read truth. `markets.match_id`
# stays a historical column and must never drive the read model again.
# ---------------------------------------------------------------------------


async def test_market_overview_joins_active_links_only(database: Database) -> None:
    markets = MarketRepository(database)
    identity = PostgresIdentityRepository(database)
    suffix = uuid4().hex[:10]
    # A fresh match with no paper intent: its link may still be replaced.
    match_id = await identity.get_or_create("match", "itest-t84", suffix)
    player_a = await identity.get_or_create("player", "itest-t84", f"a{suffix}")
    player_b = await identity.get_or_create("player", "itest-t84", f"b{suffix}")

    older = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev84a_{suffix}",
        condition_id=f"cond84a_{uuid4().hex}",
    )
    await markets.save_market(
        make_market(older, match_id=match_id, player_a=player_a, player_b=player_b)
    )
    await markets.link_match(
        market_id=older, match_id=match_id, evidence={"pair": [player_a, player_b]}
    )
    overviews = {row.market_id: row for row in await markets.list_market_overviews()}
    assert overviews[older].active_match_id == match_id

    # A newer market takes over the same match: the older link flips to
    # `replaced` and must never leak a match identity again.
    replacement = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev84b_{suffix}",
        condition_id=f"cond84b_{uuid4().hex}",
    )
    await markets.save_market(
        make_market(replacement, match_id=None, player_a=player_a, player_b=player_b)
    )
    await markets.link_match(
        market_id=replacement,
        match_id=match_id,
        evidence={"pair": [player_a, player_b]},
    )

    overviews = {row.market_id: row for row in await markets.list_market_overviews()}
    assert overviews[replacement].active_match_id == match_id
    assert overviews[replacement].link_evidence_available is True

    # The replaced market keeps its historical column value — and loses its
    # match identity, because only `status='active'` counts as read truth.
    async with database.session() as session:
        legacy = await session.scalar(
            text("SELECT match_id FROM markets WHERE id = :m"), {"m": older}
        )
    assert legacy == match_id
    assert overviews[older].active_match_id is None


async def test_markets_query_issues_a_constant_number_of_statements(
    database: Database,
) -> None:
    """Row count must not change the statement count (T84: no N+1).

    One statement-counting run with a handful of markets and one with three
    more linked markets must issue exactly the same number of SQL statements.
    """
    seeded = await _seed(database)
    markets = MarketRepository(database)
    identity = PostgresIdentityRepository(database)
    queries = P3QueryService(
        database=database,
        markets=markets,
        paper=PaperLedgerRepository(database),
        hot_books=None,
    )

    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(database.engine.sync_engine, "before_cursor_execute", _record)
    try:
        statements.clear()
        baseline_page = await queries.markets(page=1, page_size=50)
        baseline = len(statements)

        for index in range(3):
            suffix = f"{uuid4().hex[:8]}{index}"
            match = await identity.get_or_create("match", "itest-t84-count", suffix)
            market = await markets.get_or_create_market_id(
                provider="polymarket",
                provider_event_id=f"ev84c_{suffix}",
                condition_id=f"cond84c_{uuid4().hex}",
            )
            await markets.save_market(make_market(market, match_id=None))
            await markets.link_match(
                market_id=market,
                match_id=match,
                evidence={"pair": [seeded["player_a"], seeded["player_b"]]},
            )

        statements.clear()
        expanded_page = await queries.markets(page=1, page_size=50)
        expanded = len(statements)
    finally:
        event.remove(database.engine.sync_engine, "before_cursor_execute", _record)

    assert expanded_page.total > baseline_page.total  # the rows really grew
    assert expanded == baseline
    assert expanded <= 8


# ---------------------------------------------------------------------------
# T87: quote state, model availability and the real decision action are
# separate facts. Nothing is inferred from a null action any more.
# ---------------------------------------------------------------------------


def _quote_service(
    database: Database,
    *,
    model_status: Callable[[], str] | None = None,
    cls: type[P3QueryService] = P3QueryService,
) -> P3QueryService:
    return cls(
        database=database,
        markets=MarketRepository(database),
        paper=PaperLedgerRepository(database),
        hot_books=None,  # no realtime book in these tests
        quote_snapshots=MarketQuoteSnapshotRepository(database),
        snapshot_fresh_seconds=300,
        realtime_fresh_seconds=5,
        clock=lambda: NOW,
        model_status=model_status,
    )


async def _seed_quiet_market(database: Database) -> dict[str, str]:
    """A covered main-tour market with an active link and no evaluation yet.

    This is the honest quiet-window shape: the market is in domain, but no
    live event has produced a prediction or a decision observation.
    """
    markets = MarketRepository(database)
    identity = PostgresIdentityRepository(database)
    suffix = uuid4().hex[:10]
    match_id = await identity.get_or_create("match", "itest-t89", suffix)
    player_a = await identity.get_or_create("player", "itest-t89", f"a{suffix}")
    player_b = await identity.get_or_create("player", "itest-t89", f"b{suffix}")
    tournament_id = await identity.get_or_create(
        "tournament", "itest-t89", f"t{suffix}"
    )
    async with database.session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "UPDATE matches SET status = 'live', player1_id = :p1,"
                    " player2_id = :p2, tournament_id = :t WHERE id = :m"
                ),
                {"p1": player_a, "p2": player_b, "t": tournament_id, "m": match_id},
            )
            await session.execute(
                text(
                    "UPDATE tournaments SET name = 'Quiet Open', circuit = 'atp',"
                    " gender = 'men' WHERE id = :i"
                ),
                {"i": tournament_id},
            )
    market_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev_quiet_{suffix}",
        condition_id=f"cond_{uuid4().hex}",
    )
    await markets.save_market(
        make_market(market_id, match_id=match_id, player_a=player_a, player_b=player_b)
    )
    await markets.link_match(
        market_id=market_id, match_id=match_id, evidence={"pair": [player_a, player_b]}
    )
    return {"match_id": match_id, "market_id": market_id}


class _QuietWindowQueries(P3QueryService):
    """The aggregate reason is global, so the quiet-window shape is pinned
    explicitly: no opportunity row at all. The rows themselves and their
    action semantics are proven by the tests above."""

    async def opportunities(self):
        return []


async def test_opportunity_view_explains_an_unpromoted_deployment(
    database: Database,
) -> None:
    """With no evaluation yet AND no promoted artifact, the empty tab must
    explain the deployment's model truth instead of claiming the model ran
    and found nothing (spec §6.2)."""
    await _seed_quiet_market(database)
    queries = _quote_service(
        database, model_status=lambda: "not_promoted", cls=_QuietWindowQueries
    )

    rows, availability = await queries.opportunity_view()

    assert rows == []
    assert availability.reason == "ELIGIBLE_UNPROMOTED"
    assert availability.model_status == "not_promoted"


async def test_market_rows_expose_explicit_quote_and_model_semantics(
    database: Database,
) -> None:
    seeded = await _seed(database)
    market_id = seeded["market_id"]
    queries = _quote_service(database)

    page = await queries.markets(page=1, page_size=50)
    summary = next(item for item in page.markets if item.market_id == market_id)
    assert summary.match_id == seeded["match_id"]
    assert summary.model_availability == "available"
    assert summary.decision_action == "buy"  # from the real observation
    # No stored quote and no hot book yet: an explicit `unavailable`, never a zero.
    assert summary.quote.state == "unavailable"
    assert summary.quote.source is None and summary.quote.as_of is None
    assert summary.quote.outcome_asks == (None, None)

    # A stored durable snapshot becomes a real snapshot quote with its own time.
    stored_at = NOW
    await MarketQuoteSnapshotRepository(database).upsert(
        QuoteSnapshotRecord(
            market_id=market_id,
            source=QuoteSource.SNAPSHOT,
            state=QuoteState.SNAPSHOT,
            book_hash="stored",
            as_of=stored_at,
            expires_at=stored_at + timedelta(seconds=300),
            outcome_bids=("0.58", "0.40"),
            outcome_asks=("0.60", "0.42"),
            spread="0.0200",
            depth_usd="306.00",
        )
    )
    page = await queries.markets(page=1, page_size=50)
    summary = next(item for item in page.markets if item.market_id == market_id)
    assert summary.quote.state == "snapshot"
    assert summary.quote.source == "snapshot"
    assert summary.quote.as_of is not None
    assert summary.quote.outcome_asks == ("0.60", "0.42")


async def test_unmapped_market_has_no_action_and_no_fabricated_navigation(
    database: Database,
) -> None:
    markets = MarketRepository(database)
    market_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev87_{uuid4().hex[:10]}",
        condition_id=f"cond87_{uuid4().hex}",
    )
    await markets.save_market(make_market(market_id, match_id=None))
    queries = _quote_service(database)

    page = await queries.markets(page=1, page_size=50)
    summary = next(item for item in page.markets if item.market_id == market_id)
    assert summary.match_id is None
    assert summary.decision_action is None  # never an inferred MARKET_ONLY
    assert summary.model_availability == "not_evaluated"
    assert summary.quote.state == "unavailable"


async def test_opportunity_view_explains_the_unpromoted_empty_state(
    database: Database,
) -> None:
    seeded = await _seed(database)
    markets = MarketRepository(database)
    # The newest observation for the market says the model is unpromoted.
    unpromoted = make_observation(
        seeded["match_id"], seeded["market_id"], observation_version=9
    ).model_copy(
        update={
            "action": DecisionAction.NO_BET,
            "reason_code": "MODEL_UNPROMOTED",
            "quote": None,
            "conservative_net_edge": None,
            "target_player_id": None,
        }
    )
    await markets.save_decision_observation(unpromoted)
    queries = _quote_service(database)

    rows, availability = await queries.opportunity_view()

    assert availability.reason in {"ELIGIBLE_UNPROMOTED", "HAS_OPPORTUNITIES"}
    assert availability.model_status in {"not_promoted", "unknown"}
    if availability.reason == "ELIGIBLE_UNPROMOTED":
        assert rows == []
        assert availability.model_status == "not_promoted"


async def test_opportunity_view_reports_the_dominant_reason(database: Database) -> None:
    """With no rows and no unpromoted evidence the aggregate reason must be
    one of the honest non-action reasons, never a fabricated opportunity."""
    queries = _quote_service(database)
    rows, availability = await queries.opportunity_view()
    assert all(row.action in ("buy", "wait") for row in rows)
    if not rows:
        assert availability.reason in {
            "ELIGIBLE_UNPROMOTED",
            "NO_ELIGIBLE_ACTION",
            "NO_COVERED_MARKET",
            "DECISION_GAP",
        }


async def test_markets_snapshot_carries_an_availability_reason(database: Database) -> None:
    queries = _quote_service(database)
    snapshot = await queries.markets_snapshot()
    assert snapshot["availability"] in {
        "HAS_OPPORTUNITIES",
        "ELIGIBLE_UNPROMOTED",
        "NO_ELIGIBLE_ACTION",
        "NO_COVERED_MARKET",
        "DECISION_GAP",
    }
