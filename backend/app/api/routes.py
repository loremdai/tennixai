from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    HeadToHeadResultResponse,
    MatchCatalogResponse,
    MatchListResponse,
    MatchResponse,
    PlayerListResponse,
    PlayerResultsResponse,
)
from app.chat.models import ChatEvent, ChatEventType, ChatRequest
from app.chat.orchestrator import ChatOrchestrator
from app.domain import CircuitTier, Discipline, Gender
from app.errors import AppError
from app.service import MatchFilters, TennisService

router = APIRouter(prefix="/api/v1")


def get_service(request: Request) -> TennisService:
    return request.app.state.tennis_service


def get_orchestrator(request: Request) -> ChatOrchestrator:
    return request.app.state.chat_orchestrator


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "tennix-api"}


@router.get("/players/search", response_model=PlayerListResponse)
async def search_players(
    q: str = Query(min_length=1),
    service: TennisService = Depends(get_service),
) -> PlayerListResponse:
    return PlayerListResponse(data=await service.search_players(q))


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


@router.get("/matches/{match_id}", response_model=MatchResponse)
async def get_match(
    match_id: str,
    service: TennisService = Depends(get_service),
) -> MatchResponse:
    return MatchResponse(data=await service.get_match(match_id))


@router.get("/players/{player_id}/results", response_model=PlayerResultsResponse)
async def player_results(
    player_id: str,
    scope: Literal["yesterday", "recent"] = Query(),
    limit: int = Query(default=5, ge=1, le=10),
    service: TennisService = Depends(get_service),
) -> PlayerResultsResponse:
    return PlayerResultsResponse(
        data=await service.get_player_results(player_id, scope, limit)
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
