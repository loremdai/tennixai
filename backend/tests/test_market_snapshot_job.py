"""Bounded coverage-lane snapshot job tests (T86). No real network."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.errors import AppError
from app.markets.models import BookLevel, MarketExternalId
from app.markets.quotes import (
    ClobBooksBatch,
    QuoteSnapshotRecord,
    QuoteSource,
    QuoteState,
    TokenBook,
)
from app.persistence.market_repositories import MarketOverviewRow
from app.runtime.market_snapshot import MarketQuoteSnapshotJob

NOW = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)
MARKET_IDS = [f"mkt_{index}" for index in range(5)]
TOKENS = {
    market_id: (f"tok_a{index}", f"tok_b{index}")
    for index, market_id in enumerate(MARKET_IDS)
}


def overview(
    market_id: str,
    *,
    status: str = "open",
    match_id: str | None = None,
    event_start: datetime | None = None,
) -> MarketOverviewRow:
    return MarketOverviewRow(
        market_id=market_id,
        question=f"Question {market_id}",
        status=status,
        rules_version=1,
        observed_at=NOW,
        event_start=event_start or NOW + timedelta(hours=1),
        updated_at=NOW,
        outcome_a_player_id=f"ply_a_{market_id}",
        outcome_a_name="Provider A",
        outcome_b_player_id=f"ply_b_{market_id}",
        outcome_b_name="Provider B",
        active_match_id=match_id or f"mat_{market_id}",
        link_evidence_available=True,
    )


class FakeMarkets:
    def __init__(self, rows, *, tokens=None):
        self._rows = list(rows)
        self._tokens = dict(tokens if tokens is not None else TOKENS)
        self.external_calls: list[tuple[str, ...]] = []

    async def list_market_overviews(self):
        return list(self._rows)

    async def list_external_ids(self, market_ids):
        self.external_calls.append(tuple(market_ids))
        return {
            market_id: MarketExternalId(
                market_id=market_id,
                provider="polymarket",
                provider_event_id=f"ev_{market_id}",
                condition_id=f"cond_{market_id}",
                token_ids=self._tokens[market_id],
            )
            for market_id in market_ids
            if market_id in self._tokens
        }


class FakeProjections:
    def __init__(self, stored=None):
        self.stored = dict(stored or {})
        self.writes: list[QuoteSnapshotRecord] = []
        self.limited: list[tuple[str, ...]] = []
        self.load_many_calls = 0

    async def upsert(self, record):
        self.writes.append(record)
        self.stored[record.market_id] = record
        return True

    async def load_many(self, market_ids):
        self.load_many_calls += 1
        return {mid: self.stored[mid] for mid in market_ids if mid in self.stored}

    async def mark_limited(self, market_ids, *, now, expires_at):
        ids = tuple(market_ids)
        self.limited.append(ids)
        # Mirror the repository: stored levels survive, the state is retagged
        # (or a minimal limited row is created when none exists yet).
        for market_id in ids:
            existing = self.stored.get(market_id)
            if existing is not None:
                self.stored[market_id] = existing.model_copy(
                    update={"state": QuoteState.LIMITED}
                )
            else:
                self.stored[market_id] = QuoteSnapshotRecord(
                    market_id=market_id,
                    source=QuoteSource.SNAPSHOT,
                    state=QuoteState.LIMITED,
                    as_of=now,
                    expires_at=expires_at,
                )
        return len(ids)


class FakeProvider:
    def __init__(self, *, fail_with=None, rate_after=None):
        self.calls: list[tuple[str, ...]] = []
        self._fail_with = fail_with
        self._rate_after = rate_after

    async def get_order_books(self, token_ids):
        self.calls.append(tuple(token_ids))
        if self._rate_after is not None and len(self.calls) > self._rate_after:
            raise AppError("rate_limited", "rate limited", 429, {"retry_after": "30"})
        if self._fail_with is not None:
            raise self._fail_with
        books = {
            token: TokenBook(
                token_id=token,
                bids=(BookLevel(price=Decimal("0.58"), size=Decimal("10")),),
                asks=(BookLevel(price=Decimal("0.60"), size=Decimal("10")),),
                book_hash=f"h_{token}",
                provider_timestamp=NOW,
            )
            for token in token_ids
        }
        return ClobBooksBatch(books=books, raw=({"asset_id": token_ids[0]},))


class FakeRaw:
    def __init__(self):
        self.batches: list[tuple[int, int]] = []

    async def append(self, *, provider, channel, kind, payload, observed_at, **kwargs):
        self.batches.append((payload["batch_index"], len(payload["books"])))


class FakeCatalog:
    def __init__(self, *, live=(), upcoming=()):
        self._live = list(live)
        self._upcoming = list(upcoming)

    async def list_matches(self, status):
        from app.domain import MatchStatus

        return list(self._live) if status is MatchStatus.LIVE else list(self._upcoming)


class FakeHot:
    def __init__(self, books=None):
        self.books = dict(books or {})
        self.calls = 0

    async def get_hot_books(self, market_ids):
        self.calls += 1
        return {mid: self.books[mid] for mid in market_ids if mid in self.books}


def job(
    *,
    markets,
    projections,
    provider=None,
    raw=None,
    catalog=None,
    hot=None,
    max_markets=250,
    token_batch_size=100,
) -> MarketQuoteSnapshotJob:
    return MarketQuoteSnapshotJob(
        markets=markets,
        projections=projections,
        provider=provider or FakeProvider(),
        raw=raw or FakeRaw(),
        catalog=catalog or FakeCatalog(),
        hot_books=hot or FakeHot(),
        clock=lambda: NOW,
        max_markets=max_markets,
        token_batch_size=token_batch_size,
        quote_fresh_seconds=300,
        realtime_fresh_seconds=5,
    )


async def test_snapshot_job_splits_batches_and_writes_every_candidate():
    markets = FakeMarkets([overview(market_id) for market_id in MARKET_IDS])
    projections = FakeProjections()
    provider = FakeProvider()
    raw = FakeRaw()
    runner = job(
        markets=markets,
        projections=projections,
        provider=provider,
        raw=raw,
        token_batch_size=4,
    )

    coverage = await runner.run_once()

    # 5 markets x 2 tokens split into batches of <= 4 tokens => 3 requests.
    assert len(provider.calls) == 3
    assert all(len(call) <= 4 for call in provider.calls)
    assert len(raw.batches) == 3  # one raw row per batch, never per token
    assert len(markets.external_calls) == 1  # ONE bulk private-token read
    assert len(projections.writes) == 5
    assert all(record.state is QuoteState.SNAPSHOT for record in projections.writes)
    assert coverage.candidate == 5 and coverage.attempted == 5
    assert coverage.fresh_snapshot == 5
    assert (
        sum(
            [
                coverage.fresh_realtime,
                coverage.fresh_snapshot,
                coverage.partial,
                coverage.no_liquidity,
                coverage.unavailable,
                coverage.stale,
                coverage.limited,
            ]
        )
        == coverage.candidate
    )
    assert coverage.last_successful_batch_at == NOW
    assert coverage.rate_limited is False


async def test_snapshot_job_marks_the_overflow_as_limited_without_dropping_it():
    markets = FakeMarkets([overview(market_id) for market_id in MARKET_IDS])
    projections = FakeProjections()
    runner = job(markets=markets, projections=projections, max_markets=3)

    coverage = await runner.run_once()

    assert projections.limited == [tuple(MARKET_IDS[3:])]
    assert coverage.candidate == 5 and coverage.attempted == 3
    assert coverage.limited == 2


async def test_snapshot_job_rotates_live_markets_first():
    from types import SimpleNamespace

    from app.domain import CircuitTier

    def match(match_id: str, *, circuit: CircuitTier) -> SimpleNamespace:
        # The job consumes match objects structurally: id + tournament tier.
        return SimpleNamespace(id=match_id, tournament=SimpleNamespace(circuit=circuit))

    rows = [
        overview("mkt_itf", match_id="mat_itf"),
        overview("mkt_live", match_id="mat_live"),
        overview("mkt_atp", match_id="mat_atp"),
    ]
    markets = FakeMarkets(
        rows,
        tokens={
            "mkt_itf": ("tok_itf_a", "tok_itf_b"),
            "mkt_live": ("tok_live_a", "tok_live_b"),
            "mkt_atp": ("tok_atp_a", "tok_atp_b"),
        },
    )
    projections = FakeProjections()
    provider = FakeProvider()
    runner = job(
        markets=markets,
        projections=projections,
        provider=provider,
        catalog=FakeCatalog(
            live=[match("mat_live", circuit=CircuitTier.ITF)],
            upcoming=[
                match("mat_atp", circuit=CircuitTier.ATP),
                match("mat_itf", circuit=CircuitTier.ITF),
            ],
        ),
        max_markets=2,
        token_batch_size=2,
    )

    coverage = await runner.run_once()

    # Live first, then ATP, then ITF: the ITF market is the one left over.
    assert [record.market_id for record in projections.writes] == [
        "mkt_live",
        "mkt_atp",
    ]
    assert projections.limited == [("mkt_itf",)]
    assert coverage.limited == 1


async def test_snapshot_job_respects_429_and_skips_the_next_round():
    markets = FakeMarkets([overview(market_id) for market_id in MARKET_IDS])
    projections = FakeProjections()
    provider = FakeProvider(rate_after=1)
    runner = job(
        markets=markets,
        projections=projections,
        provider=provider,
        token_batch_size=4,
    )

    first = await runner.run_once()
    assert first.rate_limited is True
    assert first.retry_after_until == NOW + timedelta(seconds=30)
    assert len(provider.calls) == 2  # no busy retry inside the round
    assert first.batch_failures == 0

    second = await runner.run_once()
    assert len(provider.calls) == 2  # the whole next round is skipped
    assert second.rate_limited is True
    assert second.attempted == 0


async def test_snapshot_job_counts_batch_failures_and_keeps_going():
    markets = FakeMarkets([overview(market_id) for market_id in MARKET_IDS])
    projections = FakeProjections()
    provider = FakeProvider(fail_with=AppError("provider_unavailable", "down", 503))
    runner = job(
        markets=markets,
        projections=projections,
        provider=provider,
        token_batch_size=4,
    )

    coverage = await runner.run_once()

    assert coverage.batch_failures == 3
    assert coverage.attempted == 0
    assert projections.writes == []
    # Nothing was fabricated; the missing markets are reported unavailable.
    assert coverage.unavailable == coverage.candidate
    assert coverage.last_successful_batch_at is None


async def test_snapshot_job_skips_markets_without_identity_tokens_or_open_status():
    rows = [
        overview("mkt_0"),
        overview("mkt_closed", status="closed"),
        overview("mkt_unknown_token", match_id="mat_unknown_token"),
    ]
    markets = FakeMarkets(rows, tokens={"mkt_0": TOKENS["mkt_0"]})
    projections = FakeProjections()
    runner = job(markets=markets, projections=projections)

    coverage = await runner.run_once()

    assert coverage.candidate == 1
    assert [record.market_id for record in projections.writes] == ["mkt_0"]


async def test_snapshot_job_reports_fresh_realtime_markets_from_hot_state():
    from app.markets.models import OrderBookState, OutcomeBook

    market_id = MARKET_IDS[0]
    hot = FakeHot(
        {
            market_id: OrderBookState(
                market_id=market_id,
                books=(
                    OutcomeBook(
                        outcome_player_id=f"ply_a_{market_id}",
                        bids=(BookLevel(price=Decimal("0.61"), size=Decimal("10")),),
                        asks=(BookLevel(price=Decimal("0.63"), size=Decimal("10")),),
                    ),
                    OutcomeBook(
                        outcome_player_id=f"ply_b_{market_id}",
                        bids=(BookLevel(price=Decimal("0.37"), size=Decimal("10")),),
                        asks=(BookLevel(price=Decimal("0.39"), size=Decimal("10")),),
                    ),
                ),
                sequence=3,
                book_hash="ws_hash",
                provider_timestamp=NOW,
                received_at=NOW,
            )
        }
    )
    markets = FakeMarkets([overview(market_id)])
    projections = FakeProjections()
    runner = job(markets=markets, projections=projections, hot=hot)

    coverage = await runner.run_once()

    assert hot.calls == 1  # one bulk hot-book read for the coverage counts
    assert coverage.fresh_realtime == 1
    assert coverage.fresh_snapshot == 0


async def test_snapshot_job_has_no_lane_side_effects():
    """The job's constructor takes display-lane dependencies only: no
    decision worker, no paper service, no feed and no LLM are reachable."""
    import inspect

    parameters = set(inspect.signature(MarketQuoteSnapshotJob.__init__).parameters)
    assert parameters.isdisjoint(
        {
            "decision_worker",
            "paper",
            "feed",
            "llm",
            "predictor",
            "engine",
            "realtime",
            "market_worker",
        }
    )
