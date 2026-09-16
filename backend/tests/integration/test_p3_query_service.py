"""P3QueryService integration against real PostgreSQL (T66).

Seeds the durable ledger through the repositories, then proves every
read-only query path: match decision snapshot with lifecycle, ordered
opportunities, canonical market filters, paper positions, pulse and the
stream ready snapshot. Hot books are absent, so best bid/ask and current
exit value must degrade to None — never to fabricated zeros. Requires
compose PostgreSQL + `uv run alembic upgrade head`.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.config import Settings
from app.persistence.database import Database
from app.persistence.market_repositories import MarketRepository
from app.persistence.paper_repositories import PaperLedgerRepository
from app.persistence.repositories import PostgresIdentityRepository
from app.service import P3QueryService
from p3_fakes import (
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
        make_entry_fill(intent.id), position=make_position(match_id, market_id)
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
    assert summary.model_covered is True
    assert summary.action == "buy"
    assert summary.best_bid is None and summary.best_ask is None
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
