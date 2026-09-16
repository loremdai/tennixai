import asyncio
import contextlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.api.schemas import ErrorBody, ErrorResponse
from app.cache import AsyncTTLCache
from app.chat.client import FakeChatModel, OpenAICompatibleChatModel
from app.chat.orchestrator import ChatOrchestrator
from app.chat.tools import BusinessTools
from app.config import Settings
from app.errors import AppError
from app.identity import MemoryIdentityRepository
from app.persistence.database import Database
from app.persistence.player_directory import PostgresPlayerDirectoryRepository
from app.persistence.repositories import PostgresIdentityRepository
from app.players.repository import MemoryPlayerDirectoryRepository
from app.players.resolver import PlayerResolver
from app.players.sync import DirectorySeeder, PlayerDirectorySync
from app.providers.api_tennis import ApiTennisProvider
from app.providers.api_tennis_live import ApiTennisLiveFeedProvider
from app.providers.base import TennisDataProvider
from app.providers.fake import FakeTennisProvider
from app.providers.livetennis import LiveTennisProvider
from app.providers.replay import ReplayTennisProvider
from app.realtime.worker import RealtimeWorker
from app.service import TennisService


def _build_clock(settings: Settings):
    fixed_now = (
        datetime.fromisoformat(settings.fixed_now.replace("Z", "+00:00"))
        if settings.fixed_now
        else None
    )
    if fixed_now is not None and fixed_now.tzinfo is None:
        raise ValueError("TENNIX_FIXED_NOW must be timezone-aware")
    return (lambda: fixed_now) if fixed_now is not None else (lambda: datetime.now(timezone.utc))


def create_app(
    settings: Settings | None = None,
    *,
    provider: TennisDataProvider | None = None,
    chat_orchestrator: Any = None,
    realtime: Any = None,
) -> FastAPI:
    settings = settings or Settings()
    clock = _build_clock(settings)
    identities = MemoryIdentityRepository()

    live_client: httpx.AsyncClient | None = None
    api_tennis_client: httpx.AsyncClient | None = None
    database: Database | None = None
    directory: object | None = None
    resolver: PlayerResolver | None = None
    seeder: DirectorySeeder | None = None
    redis_client = None
    owns_realtime = realtime is None
    provider_identity = identities
    if provider is None:
        if settings.provider_mode == "api_tennis":
            api_key = settings.api_tennis_api_key
            if api_key is None:
                raise ValueError(
                    "TENNIX_API_TENNIS_API_KEY is required in api_tennis provider mode"
                )
            database = Database(settings.database_url)
            api_tennis_client = httpx.AsyncClient(
                base_url=settings.api_tennis_base_url, timeout=15.0
            )
            provider_identity = PostgresIdentityRepository(database)
            directory = PostgresPlayerDirectoryRepository(database)
            provider = ApiTennisProvider(
                client=api_tennis_client,
                identities=provider_identity,
                api_key=api_key.get_secret_value(),
                now=clock,
                directory=directory,
            )
        elif settings.provider_mode == "replay":
            database = Database(settings.database_url)
            provider_identity = PostgresIdentityRepository(database)
            provider = ReplayTennisProvider.from_file(
                settings.replay_fixture_path,
                identities=provider_identity,
                clock=clock,
                speed=settings.replay_speed,
                identity_namespace=settings.replay_identity_namespace,
            )
        elif settings.provider_mode in ("live", "livetennis"):
            api_key = settings.livetennis_api_key
            if api_key is None:
                raise ValueError("TENNIX_LIVETENNIS_API_KEY is required in live provider mode")
            live_client = httpx.AsyncClient(
                base_url=settings.livetennis_base_url, timeout=10.0
            )
            provider = LiveTennisProvider(
                client=live_client,
                identities=identities,
                api_key=api_key.get_secret_value(),
                now=clock,
            )
        else:
            directory = MemoryPlayerDirectoryRepository()
            provider = FakeTennisProvider(identities=identities, now=clock)

    if directory is not None:
        if settings.provider_mode == "fake":
            # Deterministic in-memory directory so fake-mode pages and Chat
            # resolve names without touching any vendor or the database. The
            # one-shot seeder runs on first use, server or test alike.
            seeder = DirectorySeeder(
                PlayerDirectorySync(provider, directory, now=clock)
            )
            resolver = PlayerResolver(directory, seeder=seeder.ensure)
        else:
            resolver = PlayerResolver(directory)

    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=settings.cache_max_entries)

    if realtime is None:
        import time as _time

        import redis.asyncio as aioredis

        from app.persistence.repositories import MatchSnapshotRepository
        from app.persistence.repositories import RawProviderEventRepository
        from app.realtime.leases import ViewerLeaseStore
        from app.realtime.publisher import RealtimePublisher

        database = database or Database(settings.database_url)
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        store = MatchSnapshotRepository(database)
        publisher = RealtimePublisher(redis_client, now=clock)
        leases = ViewerLeaseStore(
            redis_client,
            lease_seconds=settings.viewer_lease_seconds,
            grace_seconds=settings.subscription_grace_seconds,
            now=_time.time,
        )
        worker = None
        if settings.provider_mode == "api_tennis":
            api_key = settings.api_tennis_api_key
            if api_key is None:
                raise ValueError(
                    "TENNIX_API_TENNIS_API_KEY is required in api_tennis provider mode"
                )
            feed = ApiTennisLiveFeedProvider(
                api_key=api_key.get_secret_value(),
                identities=provider_identity,
                now=clock,
                base_url=settings.api_tennis_ws_url,
            )
            worker = RealtimeWorker(
                identity=provider_identity,
                snapshots=store,
                leases=leases,
                publisher=publisher,
                feed=feed,
                rest=provider,
                raw=RawProviderEventRepository(database),
                now=clock,
                max_live_subscriptions=settings.max_live_subscriptions,
            )
        elif settings.provider_mode == "replay":
            worker = RealtimeWorker(
                identity=provider_identity,
                snapshots=store,
                leases=leases,
                publisher=publisher,
                feed=provider,
                rest=provider,
                raw=RawProviderEventRepository(database),
                now=clock,
                max_live_subscriptions=settings.max_live_subscriptions,
                provider_name=provider.identity_namespace,
            )
        realtime = SimpleNamespace(
            redis=redis_client,
            leases=leases,
            publisher=publisher,
            store=store,
            worker=worker,
        )

    service = TennisService(
        provider,
        cache,
        now=clock,
        timezone=settings.product_timezone,
        snapshots=realtime.store,
        publisher=realtime.publisher,
        resolver=resolver,
        directory=directory,
        seeder=seeder.ensure if seeder is not None else None,
    )

    # P3 read-only market provider. Assembled only when explicitly enabled;
    # public Polymarket endpoints plus the durable identity mapping. No
    # wallet, key, signing or trading channel exists anywhere in this path.
    market_provider = None
    if settings.p3_mode != "disabled" and resolver is not None and database is not None:
        from app.markets.polymarket import PolymarketProvider
        from app.persistence.market_repositories import MarketRepository

        market_repository = MarketRepository(database)

        async def register_market(
            provider_event_id: str, condition_id: str, token_ids: tuple[str, str]
        ) -> str:
            return await market_repository.get_or_create_market_id(
                provider="polymarket",
                provider_event_id=provider_event_id,
                condition_id=condition_id,
                token_ids=token_ids,
            )

        async def lookup_market_external(market_id: str):
            return await market_repository.get_external_id(market_id)

        market_provider = PolymarketProvider(
            gamma_base_url=settings.polymarket_gamma_base_url,
            clob_base_url=settings.polymarket_clob_base_url,
            resolver=resolver,
            registrar=register_market,
            external_lookup=lookup_market_external,
        )

    # P3 market realtime pieces (public market channel + independent Redis
    # namespace). The worker loop is orchestrated by T65; nothing here starts
    # a background task or writes SQL per delta.
    market_feed = None
    market_publisher = None
    decision_publisher = None
    p3_metrics = None
    decision_worker = None
    tracking_demand = None
    paper_service = None
    p3_queries = None
    if settings.p3_mode != "disabled":
        from pathlib import Path

        from app.markets.live import PolymarketMarketFeed
        from app.markets.publisher import MarketHotPublisher
        from app.realtime.p3_metrics import P3Metrics
        from app.realtime.publisher import DecisionPublisher

        market_feed = PolymarketMarketFeed(ws_url=settings.polymarket_ws_url)
        p3_metrics = P3Metrics()
        if redis_client is not None:
            market_publisher = MarketHotPublisher(redis_client, now_fn=clock)
            decision_publisher = DecisionPublisher(redis_client, now_fn=clock)
        if database is not None and market_provider is not None:
            from datetime import timedelta

            from app.decision.engine import DecisionEngine
            from app.decision.policy import PolicyArtifact, PolicyRejected
            from app.decision.worker import (
                DecisionWorker,
                MarketRepositoryLinks,
                TrackingDemand,
            )
            from app.paper.service import PaperTradingService
            from app.persistence.market_repositories import MarketRepository
            from app.persistence.paper_repositories import PaperLedgerRepository
            from app.prediction.service import PredictionService

            async def _noop_publish(event) -> None:
                return None

            class _NullDecisionPublisher:
                async def publish_decision(self, observation) -> None:
                    return None

            policy_path = Path(settings.p3_model_artifact_dir) / "policy.json"
            policy = None
            if policy_path.is_file():
                try:
                    policy = PolicyArtifact.load(policy_path)
                except PolicyRejected:
                    policy = None  # fail closed: engine emits NO BET

            class _SnapshotPredictor:
                def __init__(self, service: PredictionService) -> None:
                    self._service = service

                async def predict_snapshot(self, match_id: str, snapshot):
                    if snapshot is None:
                        return None
                    return self._service.predict(snapshot)

            class _PublisherBookSource:
                def __init__(self, provider, publisher, ledger) -> None:
                    self._provider = provider
                    self._publisher = publisher
                    self._ledger = ledger

                async def get_book(self, market_id: str):
                    if self._publisher is None:
                        return None
                    return await self._publisher.get_hot_book(market_id)

                async def get_metadata(self, market_id: str):
                    return await self._provider.get_execution_metadata(market_id)

                async def get_rules_hash(self, market_id: str):
                    rules = await self._provider.get_rules(market_id)
                    return rules.rules_hash

                async def get_frozen_rules_hash(self, match_id: str):
                    for intent in await self._ledger.load_all_intents():
                        if intent.match_id == match_id:
                            return intent.rules_hash
                    return None

            market_repository = MarketRepository(database)
            paper_ledger = PaperLedgerRepository(database)
            prediction_service = PredictionService(
                artifact_dir=Path(settings.p3_model_artifact_dir)
            )
            paper_service = PaperTradingService(
                ledger=paper_ledger,
                clock=clock,
                publish=(
                    decision_publisher.publish_decision
                    if decision_publisher is not None
                    else _noop_publish
                ),
            )
            links = MarketRepositoryLinks(market_repository)
            tracking_demand = TrackingDemand(
                links=links,
                match_info=None,
                ledger=paper_ledger,
                now=clock,
                coverage_window=timedelta(
                    minutes=settings.p3_tracking_window_minutes
                ),
            )
            decision_worker = DecisionWorker(
                predictor=_SnapshotPredictor(prediction_service),
                engine=DecisionEngine(
                    policy=policy, stake=settings.p3_fixed_stake_usd
                ),
                paper=paper_service,
                books=_PublisherBookSource(
                    market_provider, market_publisher, paper_ledger
                ),
                links=links,
                observations=market_repository,
                positions=paper_ledger,
                publisher=decision_publisher or _NullDecisionPublisher(),
                metrics=p3_metrics,
                clock=clock,
            )

            from app.service import P3QueryService

            p3_queries = P3QueryService(
                database=database,
                markets=market_repository,
                paper=paper_ledger,
                hot_books=market_publisher,
            )

    if chat_orchestrator is None:
        if settings.llm_mode == "openai_compatible":
            api_key = settings.llm_api_key
            if api_key is None or not settings.llm_base_url:
                raise ValueError("TENNIX_LLM_API_KEY and TENNIX_LLM_BASE_URL are required")
            chat_model = OpenAICompatibleChatModel(
                api_key=api_key.get_secret_value(),
                base_url=settings.llm_base_url,
                model=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        else:
            chat_model = FakeChatModel()
        chat_orchestrator = ChatOrchestrator(
            BusinessTools(service, p3_queries=p3_queries), chat_model
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        worker = getattr(realtime, "worker", None)
        worker_task = None
        if worker is not None:
            worker_task = asyncio.create_task(
                worker.run_forever(
                    interval_seconds=0.01
                    if settings.provider_mode == "replay"
                    else 0.1
                )
            )
        yield
        if worker_task is not None:
            worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker_task
            await worker.stop()
        if live_client is not None:
            await live_client.aclose()
        if api_tennis_client is not None:
            await api_tennis_client.aclose()
        if market_provider is not None:
            await market_provider.aclose()
        if owns_realtime and redis_client is not None:
            await redis_client.aclose()
        if owns_realtime and database is not None:
            await database.dispose()

    app = FastAPI(title="Tennix API", lifespan=lifespan)
    app.state.settings = settings
    app.state.tennis_service = service
    app.state.chat_orchestrator = chat_orchestrator
    app.state.realtime = realtime
    app.state.market_provider = market_provider
    app.state.market_feed = market_feed
    app.state.market_publisher = market_publisher
    app.state.decision_publisher = decision_publisher
    app.state.decision_worker = decision_worker
    app.state.p3_metrics = p3_metrics
    app.state.p3_tracking_demand = tracking_demand
    app.state.p3_paper_service = paper_service
    app.state.p3_queries = p3_queries
    app.state.p3_redis = redis_client if p3_queries is not None else None

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        value = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
        request.state.request_id = value
        response = await call_next(request)
        response.headers["X-Request-ID"] = value
        return response

    def _request_id_of(request: Request) -> str:
        return getattr(request.state, "request_id", "")

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, error: AppError) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorBody(code=error.code, message=error.message, details=error.details),
            request_id=_request_id_of(request),
        )
        response = JSONResponse(
            status_code=error.status_code, content=body.model_dump(mode="json")
        )
        retry_after = error.details.get("retry_after")
        if error.code == "rate_limited" and retry_after is not None:
            response.headers["Retry-After"] = str(retry_after)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorBody(
                code="invalid_request",
                message="Request validation failed",
                details={},
            ),
            request_id=_request_id_of(request),
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    app.include_router(router)
    return app


app = create_app()
