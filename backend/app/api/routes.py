import asyncio
import contextlib
import json
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    HeadToHeadResultResponse,
    MatchCatalogResponse,
    MatchListResponse,
    MatchSnapshotResponse,
    PlayerListResponse,
    PlayerProfileViewResponse,
    PlayerResolutionResponse,
    PlayerResultPageResponse,
    PlayerResultsResponse,
    RankingPageResponse,
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


@router.get("/players/rankings", response_model=RankingPageResponse)
async def player_rankings(
    tour: Tour = Query(default=Tour.ATP),
    page: int = Query(default=1, ge=1),
    page_size: Literal[50] = Query(default=50),
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
            yield _frame(
                "ready",
                {
                    "snapshot": json.loads(snapshot.model_dump_json()),
                    "state_version": snapshot.state_version,
                    "as_of": snapshot.as_of.isoformat(),
                },
                frame_id=str(snapshot.state_version),
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
