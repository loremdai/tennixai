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
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import httpx
import redis.asyncio as aioredis

from app.config import Settings
from app.markets.publisher import MarketHotPublisher
from app.persistence.database import Database
from app.persistence.market_repositories import MarketRepository
from app.persistence.paper_repositories import PaperLedgerRepository
from app.persistence.player_directory import PostgresPlayerDirectoryRepository
from app.persistence.repositories import (
    MatchCatalogRepository,
    MatchSnapshotRepository,
    PostgresIdentityRepository,
    RuntimeStateRepository,
)
from app.players.resolver import PlayerResolver
from app.providers.api_tennis import ApiTennisProvider
from app.realtime.leases import ViewerLeaseStore
from app.realtime.publisher import RealtimePublisher
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
