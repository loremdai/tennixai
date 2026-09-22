"""Active-link projection tests for the markets read path (T84).

Deterministic spies prove the query path loads every dependency in bulk:
one overview query, one decision query, one batched match-facts call, one
batched prediction call and one batched Redis read — for any row count.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.markets.models import BookLevel, OrderBookState, OutcomeBook
from app.persistence.market_repositories import MarketOverviewRow
from app.service import P3QueryService

NOW = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)


def overview(
    market_id: str,
    *,
    match_id: str | None = None,
    status: str = "open",
    question: str | None = None,
) -> MarketOverviewRow:
    return MarketOverviewRow(
        market_id=market_id,
        question=question,
        status=status,
        rules_version=1,
        observed_at=NOW,
        event_start=NOW + timedelta(hours=1),
        updated_at=NOW,
        outcome_a_player_id="ply_a",
        outcome_a_name="Provider A",
        outcome_b_player_id="ply_b",
        outcome_b_name="Provider B",
        active_match_id=match_id,
        link_evidence_available=match_id is not None,
    )


class SpyMarkets:
    """Repository spy: per-row calls raise instead of counting (N+1 kill-switch)."""

    def __init__(self, rows, *, observations=(), predictions=None):
        self._rows = list(rows)
        self._observations = list(observations)
        self._predictions = dict(predictions or {})
        self.overview_calls = 0
        self.observation_calls = 0
        self.prediction_calls: list[tuple[str, ...]] = []

    async def list_market_overviews(self):
        self.overview_calls += 1
        return list(self._rows)

    async def latest_decision_observations(self):
        self.observation_calls += 1
        return list(self._observations)

    async def latest_predictions_for_matches(self, match_ids):
        self.prediction_calls.append(tuple(match_ids))
        return dict(self._predictions)

    async def latest_prediction(self, match_id):
        raise AssertionError("markets() must not fetch predictions per row")


class SpyHotBooks:
    def __init__(self, books=None):
        self._books = dict(books or {})
        self.bulk_calls: list[tuple[str, ...]] = []

    async def get_hot_books(self, market_ids):
        self.bulk_calls.append(tuple(market_ids))
        return {mid: self._books[mid] for mid in market_ids if mid in self._books}

    async def get_hot_book(self, market_id):
        raise AssertionError("markets() must not fetch hot books per row")


def book(market_id: str) -> OrderBookState:
    return OrderBookState(
        market_id=market_id,
        books=(
            OutcomeBook(
                outcome_player_id="ply_a",
                bids=(BookLevel(price=Decimal("0.58"), size=Decimal("120")),),
                asks=(BookLevel(price=Decimal("0.60"), size=Decimal("90")),),
            ),
            OutcomeBook(
                outcome_player_id="ply_b",
                bids=(BookLevel(price=Decimal("0.40"), size=Decimal("80")),),
                asks=(BookLevel(price=Decimal("0.42"), size=Decimal("70")),),
            ),
        ),
        sequence=9,
        book_hash=f"hash_{market_id}",
        provider_timestamp=NOW,
        received_at=NOW,
    )


class StubFactsService(P3QueryService):
    """P3QueryService with the batched match-facts lookup stubbed out."""

    def __init__(self, *, facts, **kwargs):
        super().__init__(database=None, **kwargs)
        self._facts = dict(facts)
        self.fact_calls: list[tuple[str, ...]] = []

    async def _match_facts(self, match_ids):
        self.fact_calls.append(tuple(match_ids))
        return {mid: self._facts[mid] for mid in match_ids if mid in self._facts}


async def test_markets_uses_active_link_and_loads_dependencies_in_bulk() -> None:
    rows = [
        overview("mkt_linked", match_id="mat_1"),
        overview("mkt_unlinked", question="Unlinked moneyline"),
        overview("mkt_linked_two", match_id="mat_2"),
    ]
    spy = SpyMarkets(rows)
    hot = SpyHotBooks({"mkt_linked": book("mkt_linked")})
    service = StubFactsService(
        facts={
            "mat_1": {
                "player_names": ("Alpha", "Beta"),
                "player_ids": ("ply_a", "ply_b"),
                "tier": "atp",
                "gender": "men",
                "tournament_name": "Test Open",
                "phase": "live",
            },
            "mat_2": {
                "player_names": ("Gamma", "Delta"),
                "player_ids": ("ply_a", "ply_b"),
                "tier": "challenger",
                "gender": "men",
                "tournament_name": "Test Challenger",
                "phase": "prematch",
            },
        },
        markets=spy,
        paper=None,
        hot_books=hot,
    )

    page = await service.markets(page=1, page_size=50)
    by_id = {row.market_id: row for row in page.markets}

    # The ACTIVE link drives match identity, facts and quote lookup.
    assert by_id["mkt_linked"].match_id == "mat_1"
    assert by_id["mkt_linked"].tier == "atp"
    assert by_id["mkt_linked"].phase == "live"
    assert by_id["mkt_linked"].tournament_name == "Test Open"
    assert by_id["mkt_linked"].player_names == ("Alpha", "Beta")
    assert by_id["mkt_linked"].outcome_asks == ("0.60", "0.42")
    assert by_id["mkt_linked_two"].match_id == "mat_2"
    assert by_id["mkt_linked_two"].tier == "challenger"

    # An unlinked market keeps its canonical question and invents nothing.
    unlinked = by_id["mkt_unlinked"]
    assert unlinked.match_id is None
    assert unlinked.question == "Unlinked moneyline"
    assert unlinked.tier is None and unlinked.tournament_name is None
    assert unlinked.best_ask is None
    assert unlinked.model_probability is None

    # Bulk-only: one call each, regardless of row count.
    assert spy.overview_calls == 1
    assert spy.observation_calls == 1
    assert len(spy.prediction_calls) == 1
    assert len(hot.bulk_calls) == 1
    assert len(service.fact_calls) == 1
    assert set(spy.prediction_calls[0]) == {"mat_1", "mat_2"}
    assert set(hot.bulk_calls[0]) == {"mkt_linked", "mkt_unlinked", "mkt_linked_two"}
