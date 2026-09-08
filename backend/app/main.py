from contextlib import asynccontextmanager
from datetime import datetime, timezone
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
) -> FastAPI:
    settings = settings or Settings()
    clock = _build_clock(settings)
    identities = MemoryIdentityRepository()

    live_client: httpx.AsyncClient | None = None
    if provider is None:
        if settings.provider_mode == "live":
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
    service = TennisService(provider, cache, now=clock, timezone=settings.product_timezone)

    if chat_orchestrator is None:
        if settings.llm_mode == "openai_compatible":
            api_key = settings.llm_api_key
            if api_key is None or not settings.llm_base_url:
                raise ValueError("TENNIX_LLM_API_KEY and TENNIX_LLM_BASE_URL are required")
            chat_model = OpenAICompatibleChatModel(
                api_key=api_key.get_secret_value(),
                base_url=settings.llm_base_url,
                model=settings.llm_model,
            )
        else:
            chat_model = FakeChatModel()
        chat_orchestrator = ChatOrchestrator(BusinessTools(service), chat_model)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if live_client is not None:
            await live_client.aclose()

    app = FastAPI(title="Tennix API", lifespan=lifespan)
    app.state.settings = settings
    app.state.tennis_service = service
    app.state.chat_orchestrator = chat_orchestrator

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
