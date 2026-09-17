"""CatalogSynchronizer tests (T75).

Covers exactly-once provider calls per sync, live-row deduplication by
internal match ID, deterministic newly-seen player IDs, typed failure
propagation that preserves the previously persisted catalog, and canonical
tracking info reads. All deterministic fakes; no real provider calls.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.decision.worker import MatchTrackingInfo
from app.domain import (
    CircuitTier,
    DataFreshness,
    Discipline,
    Match,
    MatchStatus,
    Player,
    Tournament,
)
from app.errors import AppError
from app.runtime.catalog import CatalogSynchronizer

NOW = datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc)
SCHEDULED_AT = NOW + timedelta(hours=5)


def make_match(
    match_id: str,
    status: MatchStatus,
    player_ids: tuple[str, str],
    *,
    scheduled_at: datetime | None = None,
) -> Match:
    return Match(
        id=match_id,
        status=status,
        players=tuple(
            Player(id=player_id, name=f"Player {player_id}") for player_id in player_ids
        ),
        tournament=Tournament(
            id="trn_test",
            name="Test Open",
            circuit=CircuitTier.ATP,
            discipline=Discipline.SINGLES,
        ),
        scheduled_at=scheduled_at,
        freshness=DataFreshness(provider="test", observed_at=NOW),
    )


LIVE = make_match("mat_live", MatchStatus.LIVE, ("ply_c", "ply_a"))
STALE_LIVE_FIXTURE = make_match(
    "mat_live", MatchStatus.SCHEDULED, ("ply_c", "ply_a"), scheduled_at=SCHEDULED_AT
)
UPCOMING = make_match(
    "mat_upcoming", MatchStatus.SCHEDULED, ("ply_a", "ply_b"), scheduled_at=SCHEDULED_AT
)


class RecordingMatchProvider:
    """Counts endpoint calls; raises the injected typed error when set."""

    def __init__(
        self,
        live: list[Match],
        fixtures: list[Match],
        *,
        live_error: AppError | None = None,
        fixtures_error: AppError | None = None,
    ) -> None:
        self._live = list(live)
        self._fixtures = list(fixtures)
        self._live_error = live_error
        self._fixtures_error = fixtures_error
        self.live_calls = 0
        self.fixtures_calls = 0

    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        self.live_calls += 1
        if self._live_error is not None:
            raise self._live_error
        return list(self._live)

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        self.fixtures_calls += 1
        if self._fixtures_error is not None:
            raise self._fixtures_error
        return list(self._fixtures)


class FakeCatalogStore:
    """In-memory stand-in for `MatchCatalogRepository` with the same
    upsert/newly-inserted-player semantics; it never deletes rows."""

    def __init__(self) -> None:
        self.matches: dict[str, Match] = {}
        self.upserted_batches: list[tuple[Match, ...]] = []

    async def upsert_matches(self, matches, *, observed_at: datetime) -> set[str]:
        known_players = {
            player.id for match in self.matches.values() for player in match.players
        }
        batch = tuple(matches)
        self.upserted_batches.append(batch)
        incoming_players = {player.id for match in batch for player in match.players}
        for match in batch:
            self.matches[match.id] = match
        return incoming_players - known_players

    async def get_match(self, match_id: str) -> Match | None:
        return self.matches.get(match_id)


def make_synchronizer(
    provider: RecordingMatchProvider | None = None,
    store: FakeCatalogStore | None = None,
) -> tuple[CatalogSynchronizer, RecordingMatchProvider, FakeCatalogStore]:
    provider = provider or RecordingMatchProvider(
        [LIVE], [STALE_LIVE_FIXTURE, UPCOMING]
    )
    store = store or FakeCatalogStore()
    return CatalogSynchronizer(provider, store, now=lambda: NOW), provider, store


@pytest.mark.asyncio
async def test_catalog_sync_deduplicates_live_and_fixture_rows_and_returns_new_players() -> (
    None
):
    synchronizer, _, store = make_synchronizer()

    result = await synchronizer.sync()

    assert result.live_matches == 1
    assert result.upcoming_matches == 1
    # Sorted internal IDs, even though first-seen order starts with ply_c.
    assert result.newly_seen_player_ids == ("ply_a", "ply_b", "ply_c")
    assert result.observed_at == NOW
    # One deduplicated write batch; the live row wins over the stale fixture.
    assert len(store.upserted_batches) == 1
    assert {match.id for match in store.upserted_batches[0]} == {
        "mat_live",
        "mat_upcoming",
    }
    assert store.matches["mat_live"].status is MatchStatus.LIVE


@pytest.mark.asyncio
async def test_sync_calls_each_provider_endpoint_exactly_once_per_sync() -> None:
    synchronizer, provider, _ = make_synchronizer()

    await synchronizer.sync()
    assert (provider.live_calls, provider.fixtures_calls) == (1, 1)

    await synchronizer.sync()
    assert (provider.live_calls, provider.fixtures_calls) == (2, 2)


@pytest.mark.asyncio
async def test_second_sync_reports_no_newly_seen_players() -> None:
    synchronizer, _, _ = make_synchronizer()
    await synchronizer.sync()

    second = await synchronizer.sync()

    assert second.newly_seen_player_ids == ()


@pytest.mark.asyncio
async def test_provider_failure_preserves_previously_persisted_catalog() -> None:
    store = FakeCatalogStore()
    healthy = RecordingMatchProvider([LIVE], [STALE_LIVE_FIXTURE, UPCOMING])
    synchronizer = CatalogSynchronizer(healthy, store, now=lambda: NOW)
    await synchronizer.sync()
    before = dict(store.matches)

    failing_live = CatalogSynchronizer(
        RecordingMatchProvider(
            [],
            [],
            live_error=AppError(
                "provider_unavailable", "API-Tennis request failed", 503
            ),
        ),
        store,
        now=lambda: NOW,
    )
    with pytest.raises(AppError) as live_failure:
        await failing_live.sync()
    assert live_failure.value.code == "provider_unavailable"

    failing_fixtures = CatalogSynchronizer(
        RecordingMatchProvider(
            [LIVE],
            [],
            fixtures_error=AppError("rate_limited", "API-Tennis quota exceeded", 429),
        ),
        store,
        now=lambda: NOW,
    )
    with pytest.raises(AppError) as fixture_failure:
        await failing_fixtures.sync()
    assert fixture_failure.value.code == "rate_limited"

    # The prior catalog survives untouched and no failed sync wrote anything.
    assert store.matches == before
    assert len(store.upserted_batches) == 1


@pytest.mark.asyncio
async def test_tracking_info_returns_canonical_fields_for_known_match() -> None:
    synchronizer, _, _ = make_synchronizer()
    await synchronizer.sync()

    info = await synchronizer.tracking_info("mat_upcoming")

    assert info == MatchTrackingInfo(
        status=MatchStatus.SCHEDULED,
        scheduled_at=SCHEDULED_AT,
        circuit=CircuitTier.ATP,
        discipline=Discipline.SINGLES,
    )


@pytest.mark.asyncio
async def test_tracking_info_returns_none_for_unknown_match() -> None:
    synchronizer, _, _ = make_synchronizer()

    assert await synchronizer.tracking_info("mat_missing") is None
