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
from app.persistence.repositories import PostgresIdentityRepository
from app.providers.api_tennis import ApiTennisProvider
from app.providers.base import TennisDataProvider
from app.providers.fake import FakeTennisProvider
from app.providers.livetennis import LiveTennisProvider
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
    redis_client = None
    owns_realtime = realtime is None
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
            provider = ApiTennisProvider(
                client=api_tennis_client,
                identities=PostgresIdentityRepository(database),
                api_key=api_key.get_secret_value(),
                now=clock,
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
            provider = FakeTennisProvider(identities=identities, now=clock)

    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=settings.cache_max_entries)

    if realtime is None:
        import time as _time

        import redis.asyncio as aioredis

        from app.persistence.repositories import MatchSnapshotRepository
        from app.realtime.leases import ViewerLeaseStore
        from app.realtime.publisher import RealtimePublisher

        database = database or Database(settings.database_url)
        redis_client = aioredis.from_url(settings.redis_url)
        realtime = SimpleNamespace(
            redis=redis_client,
            leases=ViewerLeaseStore(
                redis_client,
                lease_seconds=settings.viewer_lease_seconds,
                grace_seconds=settings.subscription_grace_seconds,
                now=_time.time,
            ),
            publisher=RealtimePublisher(redis_client, now=clock),
            store=MatchSnapshotRepository(database),
        )

    service = TennisService(
        provider,
        cache,
        now=clock,
        timezone=settings.product_timezone,
        snapshots=realtime.store,
        publisher=realtime.publisher,
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
        chat_orchestrator = ChatOrchestrator(BusinessTools(service), chat_model)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if live_client is not None:
            await live_client.aclose()
        if api_tennis_client is not None:
            await api_tennis_client.aclose()
        if owns_realtime and redis_client is not None:
            await redis_client.aclose()
        if owns_realtime and database is not None:
            await database.dispose()

    app = FastAPI(title="Tennix API", lifespan=lifespan)
    app.state.settings = settings
    app.state.tennis_service = service
    app.state.chat_orchestrator = chat_orchestrator
    app.state.realtime = realtime

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
