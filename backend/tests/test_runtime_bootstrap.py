"""RuntimeBootstrapper tests (T75).

Prove the fixed init order (migrations → rankings → known aliases → catalog
→ new-player aliases → missing-name enrichment → marker), the marker written
last and only after full success, typed failures without a marker, preserved
prior marker/data on a failed rerun, zero translator calls on a second
successful init, and aggregate-only outputs. All deterministic fakes; no
real provider, database, or LLM calls.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

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
from app.players.enrichment import PlayerAliasEnricher
from app.players.models import RankingEntry, RankingMovement, Tour
from app.players.repository import MemoryPlayerDirectoryRepository
from app.players.sync import PlayerDirectorySync
from app.runtime.bootstrap import RuntimeBootstrapper
from app.runtime.catalog import CatalogSynchronizer
from app.runtime.models import RuntimeInitRecord

NOW = datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc)
SCHEDULED_AT = NOW + timedelta(hours=5)
MODEL = "test-translator-model"
REVISION = "rev_test"


def ranking_entry(player_id: str, name: str, tour: Tour, rank: int) -> RankingEntry:
    return RankingEntry(
        player=Player(id=player_id, name=name, country_code="usa", ranking=rank),
        tour=tour,
        rank=rank,
        points=1000 - rank,
        movement=RankingMovement.SAME,
        ranking_date=NOW.date(),
        fetched_at=NOW,
    )


ATP = (
    ranking_entry("ply_ben", "Ben Shelton", Tour.ATP, 5),
    ranking_entry("ply_bryan", "Bryan Shelton", Tour.ATP, 301),
)
WTA = (ranking_entry("ply_zheng", "Qinwen Zheng", Tour.WTA, 5),)


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


LIVE_MATCH = make_match("mat_live", MatchStatus.LIVE, ("ply_c", "ply_a"))
STALE_LIVE_FIXTURE = make_match(
    "mat_live", MatchStatus.SCHEDULED, ("ply_c", "ply_a"), scheduled_at=SCHEDULED_AT
)
UPCOMING_MATCH = make_match(
    "mat_upcoming", MatchStatus.SCHEDULED, ("ply_a", "ply_b"), scheduled_at=SCHEDULED_AT
)


class StubRankingsProvider:
    def __init__(
        self,
        atp: tuple[RankingEntry, ...],
        wta: tuple[RankingEntry, ...],
        wta_error: AppError | None = None,
    ) -> None:
        self.atp = atp
        self.wta = wta
        self.wta_error = wta_error

    async def get_rankings(self, tour: Tour) -> tuple[RankingEntry, ...]:
        if tour is Tour.ATP:
            return self.atp
        if self.wta_error is not None:
            raise self.wta_error
        return self.wta


class RecordingMatchProvider:
    def __init__(
        self,
        live: list[Match],
        fixtures: list[Match],
        *,
        live_error: AppError | None = None,
    ) -> None:
        self._live = list(live)
        self._fixtures = list(fixtures)
        self._live_error = live_error
        self.live_calls = 0
        self.fixtures_calls = 0

    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        self.live_calls += 1
        if self._live_error is not None:
            raise self._live_error
        return list(self._live)

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        self.fixtures_calls += 1
        return list(self._fixtures)


class FakeCatalogStore:
    def __init__(self) -> None:
        self.matches: dict[str, Match] = {}

    async def upsert_matches(self, matches, *, observed_at: datetime) -> set[str]:
        known_players = {
            player.id for match in self.matches.values() for player in match.players
        }
        incoming_players = {player.id for match in matches for player in match.players}
        for match in matches:
            self.matches[match.id] = match
        return incoming_players - known_players

    async def get_match(self, match_id: str) -> Match | None:
        return self.matches.get(match_id)


class RecordingMigrations:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self.calls = 0

    async def upgrade_head(self) -> str:
        self.calls += 1
        self._events.append("migrations")
        return REVISION


class SpyDirectorySync(PlayerDirectorySync):
    def __init__(self, provider, repository, *, now, events: list[str]) -> None:
        super().__init__(provider, repository, now=now)
        self._events = events
        self.alias_calls: list[tuple[str, ...]] = []

    async def sync_rankings(self):
        self._events.append("rankings")
        return await super().sync_rankings()

    async def sync_known_player_aliases(self, *, batch_size: int = 500):
        self._events.append("known_aliases")
        return await super().sync_known_player_aliases(batch_size=batch_size)

    async def sync_player_aliases(self, player_ids):
        self._events.append("player_aliases")
        self.alias_calls.append(tuple(player_ids))
        return await super().sync_player_aliases(player_ids)


class SpyCatalogSynchronizer(CatalogSynchronizer):
    def __init__(self, provider, catalog, *, now, events: list[str]) -> None:
        super().__init__(provider, catalog, now=now)
        self._events = events

    async def sync(self):
        self._events.append("catalog")
        return await super().sync()


class RecordingTranslator:
    """Spy translator: records batches; `fail = True` simulates LLM outage."""

    def __init__(self) -> None:
        self.batches: list[tuple[str, ...]] = []
        self.fail = False

    async def translate(self, players) -> str:
        self.batches.append(tuple(player.player_id for player in players))
        if self.fail:
            raise AppError("llm_unavailable", "LLM request failed", 503)
        return json.dumps(
            {
                "players": [
                    {
                        "player_id": player.player_id,
                        "localized_name": f"中文-{player.name}",
                        "aliases": [],
                    }
                    for player in players
                ]
            },
            ensure_ascii=False,
        )


class SpyEnricher(PlayerAliasEnricher):
    def __init__(
        self, repository, translator, *, model: str, events: list[str]
    ) -> None:
        super().__init__(repository, translator, model=model)
        self._events = events
        self.batch_sizes: list[int] = []

    async def enrich_missing(
        self, *, batch_size: int = 25, max_batches: int | None = None
    ):
        self._events.append("enrichment")
        self.batch_sizes.append(batch_size)
        return await super().enrich_missing(
            batch_size=batch_size, max_batches=max_batches
        )


class FakeRuntimeState:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self.records: list[RuntimeInitRecord] = []

    async def is_initialized(self) -> bool:
        return bool(self.records)

    async def mark_initialized(self, record: RuntimeInitRecord) -> None:
        self._events.append("marker")
        self.records.append(record)


class Harness:
    def __init__(
        self,
        *,
        rankings_error: AppError | None = None,
        live_error: AppError | None = None,
    ) -> None:
        self.events: list[str] = []
        self.migrations = RecordingMigrations(self.events)
        self.directory_repository = MemoryPlayerDirectoryRepository()
        self.rankings_provider = StubRankingsProvider(
            atp=ATP, wta=WTA, wta_error=rankings_error
        )
        self.directory = SpyDirectorySync(
            self.rankings_provider,
            self.directory_repository,
            now=lambda: NOW,
            events=self.events,
        )
        self.match_provider = RecordingMatchProvider(
            [LIVE_MATCH], [STALE_LIVE_FIXTURE, UPCOMING_MATCH], live_error=live_error
        )
        self.catalog_store = FakeCatalogStore()
        self.catalog = SpyCatalogSynchronizer(
            self.match_provider,
            self.catalog_store,
            now=lambda: NOW,
            events=self.events,
        )
        self.translator = RecordingTranslator()
        self.enricher = SpyEnricher(
            self.directory_repository,
            self.translator,
            model=MODEL,
            events=self.events,
        )
        self.state = FakeRuntimeState(self.events)

    @property
    def bootstrap(self) -> RuntimeBootstrapper:
        return RuntimeBootstrapper(
            migrations=self.migrations,
            directory=self.directory,
            catalog=self.catalog,
            enricher=self.enricher,
            state=self.state,
            now=lambda: NOW,
        )


@pytest.mark.asyncio
async def test_initialize_runs_required_steps_in_fixed_order() -> None:
    harness = Harness()

    record = await harness.bootstrap.initialize()

    assert harness.events == [
        "migrations",
        "rankings",
        "known_aliases",
        "catalog",
        "player_aliases",
        "enrichment",
        "marker",
    ]
    assert harness.migrations.calls == 1
    assert harness.enricher.batch_sizes == [25]
    # Aliases are synced only for the newly cataloged players, sorted.
    assert harness.directory.alias_calls == [("ply_a", "ply_b", "ply_c")]
    assert isinstance(record, RuntimeInitRecord)
    assert await harness.state.is_initialized() is True


@pytest.mark.asyncio
async def test_initialize_returns_aggregate_counts_only() -> None:
    harness = Harness()

    record = await harness.bootstrap.initialize()

    assert record.completed_at == NOW
    assert record.migration_revision == REVISION
    assert record.player_count == 3  # ranking players discovered
    assert record.match_count == 2  # one live + one upcoming after dedup
    assert set(record.model_dump(mode="json")) == {
        "completed_at",
        "migration_revision",
        "player_count",
        "match_count",
    }


@pytest.mark.asyncio
async def test_init_writes_marker_only_after_all_required_steps_finish() -> None:
    harness = Harness()
    harness.translator.fail = True

    with pytest.raises(AppError) as error_info:
        await harness.bootstrap.initialize()

    assert error_info.value.code == "provider_unavailable"
    assert error_info.value.status_code == 503
    assert error_info.value.details == {}
    assert await harness.state.is_initialized() is False
    # Rows persisted by earlier successful steps are preserved.
    assert set(harness.catalog_store.matches) == {"mat_live", "mat_upcoming"}


@pytest.mark.asyncio
async def test_ranking_failure_aborts_before_catalog_and_marker() -> None:
    harness = Harness(rankings_error=AppError("provider_unavailable", "boom", 503))

    with pytest.raises(AppError) as error_info:
        await harness.bootstrap.initialize()

    assert error_info.value.code == "provider_unavailable"
    assert error_info.value.status_code == 503
    assert harness.events == ["migrations", "rankings"]
    assert harness.match_provider.live_calls == 0
    assert harness.translator.batches == []
    assert await harness.state.is_initialized() is False


@pytest.mark.asyncio
async def test_catalog_provider_failure_propagates_without_marker() -> None:
    harness = Harness(
        live_error=AppError("rate_limited", "API-Tennis quota exceeded", 429)
    )

    with pytest.raises(AppError) as error_info:
        await harness.bootstrap.initialize()

    assert error_info.value.code == "rate_limited"
    assert harness.events[-1] == "catalog"
    assert "marker" not in harness.events
    assert harness.translator.batches == []
    assert await harness.state.is_initialized() is False


@pytest.mark.asyncio
async def test_second_successful_init_repeats_zero_translator_calls() -> None:
    harness = Harness()
    await harness.bootstrap.initialize()
    first_batches = list(harness.translator.batches)
    assert first_batches == [("ply_ben", "ply_bryan", "ply_zheng")]

    second = await harness.bootstrap.initialize()

    # The rerun translates nothing new and re-syncs no new player aliases.
    assert harness.translator.batches == first_batches
    assert harness.directory.alias_calls[-1] == ()
    assert second.player_count == 3
    assert second.match_count == 2
    assert second.migration_revision == REVISION
    assert await harness.state.is_initialized() is True
    assert len(harness.state.records) == 2


@pytest.mark.asyncio
async def test_failed_rerun_preserves_prior_marker_and_data() -> None:
    harness = Harness()
    first = await harness.bootstrap.initialize()

    harness.rankings_provider.wta_error = AppError("provider_unavailable", "boom", 503)
    with pytest.raises(AppError):
        await harness.bootstrap.initialize()

    assert await harness.state.is_initialized() is True
    assert harness.state.records == [first]
    assert set(harness.catalog_store.matches) == {"mat_live", "mat_upcoming"}
    counts = await harness.directory_repository.directory_counts()
    assert counts["players"] == 3
    assert counts["localized"] == 3
