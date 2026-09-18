"""Local runtime assembly for the P4.1 role split (T76).

`build_local_runtime_assembly` constructs the read-side dependency graph for
the local `api` role: loopback PostgreSQL and Redis, the API-Tennis REST
provider (bounded user-driven fallbacks only), the player directory and
resolver, the canonical match catalog, the runtime-state repository, the P2
snapshot read pieces and the P3 query facade.

The API role never owns upstream connections: no realtime worker, no
WebSocket feed and no background discovery task is constructed here —
`realtime.worker` is always `None`. The `runtime` role's worker graph is
added by T77/T78 as a separate factory branch, keeping WebSocket ownership
in exactly one process. Constructing this assembly performs no I/O: engines
and clients are lazy and only the lifespan shutdown (`aclose`) releases
them. Only canonical data with internal IDs flows through this module.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import redis.asyncio as aioredis

from app.config import Settings
from app.decision.engine import DecisionEngine
from app.decision.policy import PolicyArtifact, PolicyRejected
from app.decision.worker import DecisionWorker, MarketRepositoryLinks, TrackingDemand
from app.errors import AppError
from app.markets.live import PolymarketMarketFeed
from app.markets.polymarket import PolymarketProvider
from app.markets.publisher import MarketHotPublisher
from app.markets.worker import MarketWorker
from app.paper.service import PaperTradingService
from app.persistence.database import Database
from app.persistence.market_repositories import MarketRepository
from app.persistence.paper_repositories import PaperLedgerRepository
from app.persistence.player_directory import PostgresPlayerDirectoryRepository
from app.persistence.repositories import (
    MatchCatalogRepository,
    MatchSnapshotRepository,
    PostgresIdentityRepository,
    RawProviderEventRepository,
    RuntimeStateRepository,
)
from app.players.resolver import PlayerResolver
from app.players.sync import PlayerDirectorySync
from app.prediction.service import PredictionService
from app.providers.api_tennis import ApiTennisProvider
from app.providers.api_tennis_live import ApiTennisLiveFeedProvider
from app.realtime.leases import ViewerLeaseStore
from app.realtime.p3_metrics import P3Metrics
from app.realtime.publisher import DecisionPublisher, PaperPublisher, RealtimePublisher
from app.realtime.worker import RealtimeWorker
from app.runtime.daemon import (
    LocalRuntimeDaemon,
    MarketBridge,
    SportsBridge,
    TrackingDemandSource,
    TtlCache,
)
from app.runtime.demand import catalog_match_info
from app.runtime.health import RuntimeHealthRegistry
from app.runtime.models import LiveLocalConfigurationError, LocalRuntimeSettings
from app.service import P3QueryService


@dataclass
class LocalRuntimeAssembly:
    """Dependency graph for one local runtime role.

    In the `api` role `realtime.worker` is `None`; the namespace keeps the
    P2 shape (redis/leases/publisher/store) so read and SSE-stream routes
    work unchanged while upstream ownership stays in the runtime process.
    """

    database: Database
    redis: Any
    provider: ApiTennisProvider
    directory: PostgresPlayerDirectoryRepository
    resolver: PlayerResolver
    catalog: MatchCatalogRepository
    state: RuntimeStateRepository
    realtime: SimpleNamespace  # worker is None in API role
    p3_queries: P3QueryService
    _api_client: httpx.AsyncClient | None = field(
        default=None, repr=False, compare=False
    )

    async def aclose(self) -> None:
        """Release every resource this assembly owns, exactly once."""
        if self._api_client is not None:
            await self._api_client.aclose()
        redis_aclose = getattr(self.redis, "aclose", None)
        if redis_aclose is not None:
            await redis_aclose()
        database_dispose = getattr(self.database, "dispose", None)
        if database_dispose is not None:
            await database_dispose()


def build_local_runtime_assembly(
    settings: Settings,
    live: LocalRuntimeSettings,
    *,
    now: Callable[[], datetime],
) -> LocalRuntimeAssembly:
    """Build the `api` role graph from validated live-local settings.

    `live` must come from `require_live_local`; the dedicated loopback
    database and Redis DB 11 URLs are taken from it, never from the shared
    `database_url`/`redis_url` settings. No connection is opened here and no
    worker or feed object is constructed.
    """
    api_key = settings.api_tennis_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        # Defensive: require_live_local already guarantees the credential.
        raise LiveLocalConfigurationError("LOCAL_CREDENTIALS_MISSING")

    database = Database(live.database_url)
    redis_client = aioredis.from_url(live.redis_url, decode_responses=True)
    api_client = httpx.AsyncClient(base_url=settings.api_tennis_base_url, timeout=15.0)
    identities = PostgresIdentityRepository(database)
    directory = PostgresPlayerDirectoryRepository(database)
    provider = ApiTennisProvider(
        client=api_client,
        identities=identities,
        api_key=api_key.get_secret_value(),
        now=now,
        directory=directory,
    )
    resolver = PlayerResolver(directory)
    catalog = MatchCatalogRepository(database)
    state = RuntimeStateRepository(database)
    store = MatchSnapshotRepository(database)
    publisher = RealtimePublisher(redis_client, now=now)
    leases = ViewerLeaseStore(
        redis_client,
        lease_seconds=settings.viewer_lease_seconds,
        grace_seconds=settings.subscription_grace_seconds,
        now=time.time,
    )
    realtime = SimpleNamespace(
        redis=redis_client,
        leases=leases,
        publisher=publisher,
        store=store,
        worker=None,
    )
    p3_queries = P3QueryService(
        database=database,
        markets=MarketRepository(database),
        paper=PaperLedgerRepository(database),
        hot_books=MarketHotPublisher(redis_client, now_fn=now),
    )
    return LocalRuntimeAssembly(
        database=database,
        redis=redis_client,
        provider=provider,
        directory=directory,
        resolver=resolver,
        catalog=catalog,
        state=state,
        realtime=realtime,
        p3_queries=p3_queries,
        _api_client=api_client,
    )


# ---------------------------------------------------------------------------
# T79: the `runtime` role daemon graph (single upstream owner)
# ---------------------------------------------------------------------------


class _SnapshotPredictor:
    """Adapts the lazy PredictionService to the DecisionWorker contract."""

    def __init__(self, service: PredictionService) -> None:
        self._service = service

    async def predict_snapshot(self, match_id: str, snapshot: Any) -> Any:
        if snapshot is None:
            return None
        return self._service.predict(snapshot)


class _PublisherBookSource:
    """DecisionWorker book source: canonical hot book plus provider rules.

    Metadata and rules reads go through TTL caches (the metadata cache is the
    very instance the daemon's paper path uses) so the per-decision cycle
    never re-issues the underlying provider REST calls inside a TTL window.
    """

    def __init__(
        self,
        publisher: Any,
        ledger: Any,
        *,
        metadata_cache: TtlCache,
        rules_cache: TtlCache,
    ) -> None:
        self._publisher = publisher
        self._ledger = ledger
        self._metadata_cache = metadata_cache
        self._rules_cache = rules_cache

    async def get_book(self, market_id: str) -> Any:
        if self._publisher is None:
            return None
        return await self._publisher.get_hot_book(market_id)

    async def get_metadata(self, market_id: str) -> Any:
        return await self._metadata_cache.get(market_id)

    async def get_rules_hash(self, market_id: str) -> str:
        rules = await self._rules_cache.get(market_id)
        return rules.rules_hash

    async def get_frozen_rules_hash(self, match_id: str) -> str | None:
        for intent in await self._ledger.load_all_intents():
            if intent.match_id == match_id:
                return intent.rules_hash
        return None


@dataclass
class LocalRuntimeDaemonGraph:
    """Owned object graph for the `runtime` role child process (T79).

    Construction performs no I/O — engines, Redis and HTTP clients are
    lazy; only ``aclose`` releases them. The graph is the single upstream
    WebSocket owner: the API role never constructs one.
    """

    daemon: LocalRuntimeDaemon
    realtime: RealtimeWorker
    market_worker: MarketWorker
    decision_worker: DecisionWorker
    health: RuntimeHealthRegistry
    paper: PaperTradingService
    hot_books: MarketHotPublisher
    _market_feed: PolymarketMarketFeed = field(repr=False)
    _market_provider: PolymarketProvider = field(repr=False)
    _api_client: httpx.AsyncClient = field(repr=False)
    _redis: Any = field(repr=False)
    _database: Database = field(repr=False)

    async def aclose(self) -> None:
        """Release every resource this graph owns, exactly once."""
        await self._market_feed.shutdown()
        await self._market_provider.aclose()
        await self._api_client.aclose()
        redis_aclose = getattr(self._redis, "aclose", None)
        if redis_aclose is not None:
            await redis_aclose()
        await self._database.dispose()


def build_local_runtime_daemon(
    settings: Settings,
    live: LocalRuntimeSettings,
    *,
    now: Callable[[], datetime] | None = None,
) -> LocalRuntimeDaemonGraph:
    """Build the `runtime` role graph from validated live-local settings.

    `live` must come from `require_live_local`; the dedicated loopback
    database and Redis DB 11 URLs are taken from it. Mirrors the P4 wiring
    in `app.main` but keeps upstream WebSocket ownership in this single
    process. No connection is opened here — everything is lazy until
    `daemon.run()`.
    """
    api_key = settings.api_tennis_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        # Defensive: require_live_local already guarantees the credential.
        raise LiveLocalConfigurationError("LOCAL_CREDENTIALS_MISSING")

    clock = now or (lambda: datetime.now(UTC))
    database = Database(live.database_url)
    redis_client = aioredis.from_url(live.redis_url, decode_responses=True)
    api_client = httpx.AsyncClient(base_url=settings.api_tennis_base_url, timeout=15.0)

    identities = PostgresIdentityRepository(database)
    directory_repo = PostgresPlayerDirectoryRepository(database)
    provider = ApiTennisProvider(
        client=api_client,
        identities=identities,
        api_key=api_key.get_secret_value(),
        now=clock,
        directory=directory_repo,
    )
    resolver = PlayerResolver(directory_repo)
    catalog = MatchCatalogRepository(database)
    state = RuntimeStateRepository(database)
    snapshots = MatchSnapshotRepository(database)
    raw_events = RawProviderEventRepository(database)
    markets = MarketRepository(database)
    ledger = PaperLedgerRepository(database)

    # The Polymarket provider owns the execution-metadata and rules reads the
    # decision path needs; it is constructed before the decision worker so the
    # book source and the daemon's paper path can share ONE metadata cache.
    async def register_market(
        provider_event_id: str, condition_id: str, token_ids: tuple[str, str]
    ) -> str:
        return await markets.get_or_create_market_id(
            provider="polymarket",
            provider_event_id=provider_event_id,
            condition_id=condition_id,
            token_ids=token_ids,
        )

    async def lookup_market_external(market_id: str) -> Any:
        return await markets.get_external_id(market_id)

    market_provider = PolymarketProvider(
        gamma_base_url=settings.polymarket_gamma_base_url,
        clob_base_url=settings.polymarket_clob_base_url,
        resolver=resolver,
        registrar=register_market,
        external_lookup=lookup_market_external,
    )

    # One shared execution-metadata cache feeds both the paper path (daemon)
    # and the decision path (book source); the rules-hash cache is decision
    # only. Both use the discovery cadence as their TTL, matching the paper
    # path's existing 120s window, so the two never diverge.
    metadata_ttl = timedelta(seconds=live.market_discovery_seconds)
    metadata_cache = TtlCache(
        market_provider.get_execution_metadata, clock, ttl=metadata_ttl
    )
    rules_cache = TtlCache(market_provider.get_rules, clock, ttl=metadata_ttl)

    registry = RuntimeHealthRegistry(state=state, clock=clock)

    links = MarketRepositoryLinks(markets)
    tracking = TrackingDemand(
        links=links,
        match_info=catalog_match_info(catalog),
        ledger=ledger,
        now=clock,
        coverage_window=timedelta(minutes=settings.p3_tracking_window_minutes),
    )

    realtime_publisher = RealtimePublisher(redis_client, now=clock)
    market_publisher = MarketHotPublisher(redis_client, now_fn=clock)
    decision_publisher = DecisionPublisher(redis_client, now_fn=clock)
    paper_publisher = PaperPublisher(redis_client, now_fn=clock)
    leases = ViewerLeaseStore(
        redis_client,
        lease_seconds=settings.viewer_lease_seconds,
        grace_seconds=settings.subscription_grace_seconds,
        now=time.time,
    )

    feed = ApiTennisLiveFeedProvider(
        api_key=api_key.get_secret_value(),
        identities=identities,
        now=clock,
        base_url=settings.api_tennis_ws_url,
    )
    paper = PaperTradingService(
        ledger=ledger,
        clock=clock,
        publish=paper_publisher.publish_marker,
    )

    policy_path = Path(settings.p3_model_artifact_dir) / "policy.json"
    policy = None
    if policy_path.is_file():
        try:
            policy = PolicyArtifact.load(policy_path)
        except PolicyRejected:
            policy = None  # fail closed: the engine emits NO BET

    metrics = P3Metrics()
    decision_worker = DecisionWorker(
        predictor=_SnapshotPredictor(
            PredictionService(artifact_dir=Path(settings.p3_model_artifact_dir))
        ),
        engine=DecisionEngine(policy=policy, stake=settings.p3_fixed_stake_usd),
        paper=paper,
        books=_PublisherBookSource(
            market_publisher,
            ledger,
            metadata_cache=metadata_cache,
            rules_cache=rules_cache,
        ),
        links=links,
        observations=markets,
        positions=ledger,
        publisher=decision_publisher,
        metrics=metrics,
        clock=clock,
        freshness_for=registry.freshness_for,
    )

    sports_bridge = SportsBridge(decision_worker=decision_worker, health=registry)
    realtime_worker = RealtimeWorker(
        identity=identities,
        snapshots=snapshots,
        leases=leases,
        publisher=realtime_publisher,
        feed=feed,
        rest=provider,
        raw=raw_events,
        now=clock,
        max_live_subscriptions=settings.max_live_subscriptions,
        demand_source=TrackingDemandSource(
            tracking=tracking, links=links, health=registry
        ),
        on_snapshot=sports_bridge.on_snapshot,
        on_connection=sports_bridge.on_connection,
    )

    market_feed = PolymarketMarketFeed(ws_url=settings.polymarket_ws_url)

    async def token_lookup(market_id: str) -> tuple[str, str]:
        external = await markets.get_external_id(market_id)
        if external is None:
            raise AppError("market_not_found", "market is not registered", 404)
        return external.token_ids

    market_bridge = MarketBridge(decision_worker=decision_worker, health=registry)
    market_worker = MarketWorker(
        feed=market_feed,
        rest=market_provider,
        publisher=market_publisher,
        observations=markets,
        raw=raw_events,
        demand_source=tracking.demanded_markets,
        token_lookup=token_lookup,
        now=clock,
        on_state=market_bridge.on_state,
        on_connection=market_bridge.on_connection,
        metrics=metrics,
    )

    daemon = LocalRuntimeDaemon(
        realtime=realtime_worker,
        market_worker=market_worker,
        decision_worker=decision_worker,
        health=registry,
        clock=clock,
        paper=paper,
        hot_books=market_publisher,
        market_provider=market_provider,
        markets=markets,
        ledger=ledger,
        catalog_provider=provider,
        catalog_store=catalog,
        directory=PlayerDirectorySync(provider, directory_repo, now=clock),
        resolver=resolver,
        metrics=metrics,
        metadata_cache=metadata_cache,
        live_catalog_seconds=live.live_catalog_seconds,
        upcoming_catalog_seconds=live.upcoming_catalog_seconds,
        ranking_seconds=live.ranking_seconds,
        market_discovery_seconds=live.market_discovery_seconds,
    )
    return LocalRuntimeDaemonGraph(
        daemon=daemon,
        realtime=realtime_worker,
        market_worker=market_worker,
        decision_worker=decision_worker,
        health=registry,
        paper=paper,
        hot_books=market_publisher,
        _market_feed=market_feed,
        _market_provider=market_provider,
        _api_client=api_client,
        _redis=redis_client,
        _database=database,
    )
