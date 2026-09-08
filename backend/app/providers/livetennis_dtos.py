"""Vendor-only DTOs for LiveTennisAPI payloads.

These models exist solely at the provider boundary. They are permissive
(``extra="ignore"``) so additive vendor fields never break parsing, and they
must never be exposed above ``LiveTennisProvider``.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class VendorModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class LivePlayerDto(VendorModel):
    id: int | None = None
    name: str = ""
    country: str | None = None
    ranking: int | None = None


class LiveScoreDto(VendorModel):
    sets: list[int] = []
    games: list[list[int]] = []
    points: list[str | None] = []
    server: int | None = None
    is_tiebreak: bool = False
    timestamp: str | None = None


class _MatchShape(VendorModel):
    id: int
    tournament: str = ""
    tournament_id: str | None = None
    tour: str | None = None
    surface: str | None = None
    indoor: bool | None = None
    format: str | None = None
    round: str | None = None
    status: str | None = None
    event_status: str | None = None
    scheduled_time: str | None = None
    players: dict[str, LivePlayerDto] = {}
    score: LiveScoreDto | None = None
    winner: int | None = None


class LiveMatchDto(_MatchShape):
    pass


class LiveFixtureDto(_MatchShape):
    pass


class ListResponse(VendorModel, Generic[T]):
    data: list[T] = []
    meta: dict[str, object] = {}
