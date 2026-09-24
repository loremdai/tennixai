import asyncio
import contextlib
import json
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    DecisionSnapshotDto,
    HeadToHeadResultResponse,
    MatchCatalogResponse,
    MatchListResponse,
    MatchSnapshotResponse,
    PlayerProfileViewResponse,
    PlayerResolutionResponse,
    PlayerResultPageResponse,
    MarketListResponse,
    MatchDecisionResponse,
    OpportunityListResponse,
    PaperPositionsResponse,
    PulseResponse,
    RankingPageResponse,
    RuntimeHealthDto,
    RuntimeHealthResponse,
)
from app.chat.models import ChatEvent, ChatEventType, ChatRequest
from app.chat.orchestrator import ChatOrchestrator
from app.domain import CircuitTier, Discipline, Gender
from app.errors import AppError
from app.players.models import ResultOutcome, Tour
from app.realtime.publisher import match_channel
from app.service import MatchFilters, TennisService

router = APIRouter(prefix="/api/v1")

VIEWER_RENEW_SECONDS = 20


def get_service(request: Request) -> TennisService:
    return request.app.state.tennis_service


def get_orchestrator(request: Request) -> ChatOrchestrator:
    return request.app.state.chat_orchestrator


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "tennix-api"}


@router.get("/runtime/health", response_model=RuntimeHealthResponse)
async def runtime_health(request: Request) -> RuntimeHealthResponse:
    """Internal P4.1 runtime health: the persisted aggregate written by the
    local runtime daemon, or the typed `runtime_not_started` state when no
    daemon has written one. Never exposes provider identifiers or secrets;
    the P1 `/health` contract above is untouched."""
    state = getattr(request.app.state, "runtime_state", None)
    if state is None:
        return RuntimeHealthResponse(state="runtime_not_started")
    health = await state.load_health()
    if health is None:
        return RuntimeHealthResponse(state="runtime_not_started")
    return RuntimeHealthResponse(
        state="ok", data=RuntimeHealthDto.model_validate(health.model_dump())
    )


@router.get("/players/rankings", response_model=RankingPageResponse)
async def player_rankings(
    tour: Tour = Query(default=Tour.ATP),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=50, le=50),
    country: str | None = Query(default=None),
    service: TennisService = Depends(get_service),
) -> RankingPageResponse:
    return RankingPageResponse(
        data=await service.get_rankings_page(
            tour,
            page=page,
            page_size=page_size,
            country_code=country.strip().casefold() if country else None,
        )
    )


@router.get("/players/search", response_model=PlayerResolutionResponse)
async def search_players(
    q: str = Query(min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    service: TennisService = Depends(get_service),
) -> PlayerResolutionResponse:
    return PlayerResolutionResponse(data=await service.resolve_player(q, limit=limit))


@router.get("/matches", response_model=MatchListResponse)
async def list_matches(
    status: Literal["live", "upcoming"] = Query(),
    player: str | None = Query(default=None, min_length=1),
    service: TennisService = Depends(get_service),
) -> MatchListResponse:
    return MatchListResponse(data=await service.list_matches(status, player))


# Registered before /matches/{match_id} so the literal path wins.
@router.get("/matches/catalog", response_model=MatchCatalogResponse)
async def match_catalog(
    status: Literal["live", "upcoming"] = Query(),
    circuit: list[CircuitTier] | None = Query(default=None),
    gender: list[Gender] | None = Query(default=None),
    discipline: list[Discipline] | None = Query(default=None),
    service: TennisService = Depends(get_service),
) -> MatchCatalogResponse:
    defaults = MatchFilters.default()
    filters = MatchFilters(
        circuits=tuple(circuit) if circuit is not None else defaults.circuits,
        genders=tuple(gender) if gender is not None else defaults.genders,
        disciplines=(
            tuple(discipline) if discipline is not None else defaults.disciplines
        ),
    )
    return MatchCatalogResponse(data=await service.list_catalog(status, filters))


@router.get("/matches/{match_id}", response_model=MatchSnapshotResponse)
async def get_match(
    match_id: str,
    service: TennisService = Depends(get_service),
) -> MatchSnapshotResponse:
    return MatchSnapshotResponse(data=await service.resolve_match_snapshot(match_id))


@router.get("/matches/{match_id}/stream")
async def match_stream(
    match_id: str,
    request: Request,
    service: TennisService = Depends(get_service),
):
    realtime = request.app.state.realtime
    settings = request.app.state.settings
    snapshot = await service.resolve_match_snapshot(match_id)
    viewer_id = f"view_{uuid4().hex}"

    async def event_stream():
        await realtime.leases.acquire(match_id, viewer_id)
        renew_task = asyncio.create_task(_renew_loop(realtime.leases, match_id, viewer_id))
        pubsub = realtime.redis.pubsub()
        await pubsub.subscribe(match_channel(match_id))
        try:
            snapshot_data = json.loads(snapshot.model_dump_json())
            yield _frame(
                "ready",
                {
                    "snapshot": snapshot_data,
                    "state_version": snapshot_data["state_version"],
                    "as_of": snapshot_data["as_of"],
                },
                frame_id=str(snapshot_data["state_version"]),
            )
            last_heartbeat = asyncio.get_running_loop().time()
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=settings.sse_heartbeat_seconds,
                )
                if message is None:
                    now = asyncio.get_running_loop().time()
                    if now - last_heartbeat >= settings.sse_heartbeat_seconds:
                        last_heartbeat = now
                        yield _frame("heartbeat", {})
                    continue
                last_heartbeat = asyncio.get_running_loop().time()
                event = json.loads(message["data"])
                event_type = event.get("type")
                if event_type == "match_ended":
                    yield _frame(
                        "match_ended",
                        event,
                        frame_id=str(event.get("state_version")),
                    )
                    return
                yield _frame(
                    "match_delta",
                    event,
                    frame_id=str(event.get("state_version")),
                )
        finally:
            renew_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await renew_task
            await pubsub.aclose()
            await realtime.leases.release(match_id, viewer_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


async def _renew_loop(leases, match_id: str, viewer_id: str) -> None:
    while True:
        await asyncio.sleep(VIEWER_RENEW_SECONDS)
        await leases.renew(match_id, viewer_id)


def _frame(event: str, data: dict, frame_id: str | None = None) -> str:
    head = f"id: {frame_id}\n" if frame_id is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/players/{player_id}", response_model=PlayerProfileViewResponse)
async def player_profile(
    player_id: str,
    season: int | None = Query(default=None),
    service: TennisService = Depends(get_service),
) -> PlayerProfileViewResponse:
    return PlayerProfileViewResponse(
        data=await service.get_player_profile_view(player_id, season=season)
    )


@router.get("/players/{player_id}/results", response_model=PlayerResultPageResponse)
async def player_results(
    player_id: str,
    season: int = Query(),
    tier: list[CircuitTier] = Query(default_factory=list),
    outcome: ResultOutcome = Query(default=ResultOutcome.ALL),
    page: int = Query(default=1, ge=1),
    page_size: Literal[20] = Query(default=20),
    service: TennisService = Depends(get_service),
) -> PlayerResultPageResponse:
    return PlayerResultPageResponse(
        data=await service.get_player_result_page(
            player_id, season=season, tiers=tuple(tier), outcome=outcome, page=page
        )
    )


@router.get("/head-to-head", response_model=HeadToHeadResultResponse)
async def head_to_head(
    first_player_id: str = Query(min_length=1),
    second_player_id: str = Query(min_length=1),
    limit: int = Query(default=5, ge=1, le=10),
    service: TennisService = Depends(get_service),
) -> HeadToHeadResultResponse:
    return HeadToHeadResultResponse(
        data=await service.get_head_to_head(first_player_id, second_player_id, limit)
    )


# ---------------------------------------------------------------------------
# P3 read-only market/decision endpoints (T66). Snapshots come from durable
# PostgreSQL evidence and Redis hot state; streams use the independent P3
# namespace and never touch the P2 match-stream contract.
# ---------------------------------------------------------------------------

P3_STREAM_PATTERNS = (
    "tnx:p3:quotes",
    "tnx:p3:market:*",
    "tnx:p3:decision:*",
    "tnx:p3:paper:*",
    "tnx:p3:resolution:*",
)
MARKET_EVENT_TYPES = {
    "quotes_changed",
    "market_delta",
    "market_gap",
    "decision_delta",
    "paper_delta",
    "resolution_delta",
}


def get_p3_queries(request: Request):
    queries = getattr(request.app.state, "p3_queries", None)
    if queries is None:
        raise AppError(
            "p3_disabled", "P3 market decision support is disabled", 503
        )
    return queries


def get_p3_redis(request: Request):
    p3_redis = getattr(request.app.state, "p3_redis", None)
    if getattr(request.app.state, "p3_queries", None) is None or p3_redis is None:
        raise AppError(
            "p3_disabled", "P3 market decision support is disabled", 503
        )
    return p3_redis


@router.get("/markets/opportunities", response_model=OpportunityListResponse)
async def market_opportunities(queries=Depends(get_p3_queries)):
    rows, availability = await queries.opportunity_view()
    return OpportunityListResponse(data=list(rows), availability=availability)


@router.get("/markets/pulse", response_model=PulseResponse)
async def market_pulse(queries=Depends(get_p3_queries)):
    pulse = await queries.pulse()
    return PulseResponse(**pulse)


@router.get("/markets", response_model=MarketListResponse)
async def list_markets(
    tier: Literal["atp", "wta", "challenger", "itf", "other"] | None = Query(None),
    gender: Literal["men", "women", "mixed", "unknown"] | None = Query(None),
    phase: Literal["prematch", "live", "closed"] | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    queries=Depends(get_p3_queries),
):
    page_dto = await queries.markets(
        tier=tier, gender=gender, phase=phase, page=page, page_size=page_size
    )
    return MarketListResponse(
        data=list(page_dto.markets),
        page=page_dto.page,
        page_size=page_dto.page_size,
        total=page_dto.total,
    )


@router.get("/paper/positions", response_model=PaperPositionsResponse)
async def paper_positions(queries=Depends(get_p3_queries)):
    view = await queries.paper_positions()
    return PaperPositionsResponse(
        open=list(view["open"]), recent=list(view["recent"])
    )


@router.get("/matches/{match_id}/decision", response_model=MatchDecisionResponse)
async def match_decision(match_id: str, queries=Depends(get_p3_queries)):
    decision = await queries.match_decision(match_id)
    if decision is None:
        raise AppError("not_found", "No P3 decision context for this match", 404)
    return MatchDecisionResponse(data=decision)


@router.get("/markets/stream")
async def markets_stream(request: Request, p3_redis=Depends(get_p3_redis)):
    queries = request.app.state.p3_queries
    settings = request.app.state.settings

    async def event_stream():
        pubsub = p3_redis.pubsub()
        await pubsub.psubscribe(*P3_STREAM_PATTERNS)
        try:
            snapshot = await queries.markets_snapshot()
            yield _frame("ready", snapshot)
            last_heartbeat = asyncio.get_running_loop().time()
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=settings.sse_heartbeat_seconds,
                )
                if message is None:
                    now = asyncio.get_running_loop().time()
                    if now - last_heartbeat >= settings.sse_heartbeat_seconds:
                        last_heartbeat = now
                        yield _frame("heartbeat", {})
                    continue
                last_heartbeat = asyncio.get_running_loop().time()
                event = json.loads(message["data"])
                event_type = str(event.get("type", ""))
                if event_type not in MARKET_EVENT_TYPES:
                    continue
                frame_id = event.get("sequence")
                if frame_id is None:
                    frame_id = event.get("observation_version")
                yield _frame(
                    event_type,
                    event,
                    frame_id=str(frame_id) if frame_id is not None else None,
                )
        finally:
            await pubsub.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/matches/{match_id}/decision/stream")
async def decision_stream(
    match_id: str, request: Request, p3_redis=Depends(get_p3_redis)
):
    queries = request.app.state.p3_queries
    settings = request.app.state.settings

    async def event_stream():
        pubsub = p3_redis.pubsub()
        await pubsub.psubscribe("tnx:p3:decision:*")
        try:
            decision: DecisionSnapshotDto | None = await queries.match_decision(
                match_id
            )
            yield _frame(
                "ready",
                {
                    "match_id": match_id,
                    "decision": (
                        json.loads(decision.model_dump_json())
                        if decision is not None
                        else None
                    ),
                    "observation_version": (
                        decision.observation_version if decision is not None else 0
                    ),
                    "action": decision.action if decision is not None else None,
                },
                frame_id=(
                    str(decision.observation_version) if decision is not None else None
                ),
            )
            last_heartbeat = asyncio.get_running_loop().time()
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=settings.sse_heartbeat_seconds,
                )
                if message is None:
                    now = asyncio.get_running_loop().time()
                    if now - last_heartbeat >= settings.sse_heartbeat_seconds:
                        last_heartbeat = now
                        yield _frame("heartbeat", {})
                    continue
                last_heartbeat = asyncio.get_running_loop().time()
                event = json.loads(message["data"])
                if str(event.get("type", "")) != "decision_delta":
                    continue
                if event.get("match_id") != match_id:
                    continue  # this stream serves exactly one match
                yield _frame(
                    "decision_delta",
                    event,
                    frame_id=str(event.get("observation_version")),
                )
        finally:
            await pubsub.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    orchestrator: ChatOrchestrator = Depends(get_orchestrator),
) -> StreamingResponse:
    async def event_stream():
        try:
            async for event in orchestrator.stream(payload):
                yield event.to_sse()
        except AppError as error:
            yield ChatEvent(
                type=ChatEventType.ERROR,
                payload={
                    "code": error.code,
                    "message": error.message,
                    "details": error.details,
                },
            ).to_sse()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
