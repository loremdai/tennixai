"""Permissive API-Tennis vendor DTOs.

These models mirror the vendor wire format (aliases included) and tolerate
unknown fields. They are imported ONLY by the API-Tennis adapter; nothing here
may reach service, API, or UI layers.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

ResultT = TypeVar("ResultT")


class VendorModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class ApiTennisResponse(VendorModel, Generic[ResultT]):
    success: int | None = None
    error: str | None = None
    result: ResultT | None = None


class PbpPointDto(VendorModel):
    number_point: str | None = None
    score: str | None = None
    break_point: str | None = None
    set_point: str | None = None
    match_point: str | None = None


class PbpGameDto(VendorModel):
    set_number: str | None = None
    number_game: str | None = None
    player_served: str | None = None
    serve_winner: str | None = None
    serve_lost: str | None = None
    score: str | None = None
    points: list[PbpPointDto] = Field(default_factory=list)


class ScoreRowDto(VendorModel):
    score_first: str | None = None
    score_second: str | None = None
    score_set: str | None = None


class StatisticDto(VendorModel):
    player_key: int | str | None = None
    stat_period: str | None = None
    stat_type: str | None = None
    stat_name: str | None = None
    stat_value: str | None = None
    stat_won: float | None = None
    stat_total: float | None = None


class MatchDto(VendorModel):
    event_key: int | str
    event_date: str | None = None
    event_time: str | None = None
    event_first_player: str | None = None
    first_player_key: int | str | None = None
    first_player_dp1_key: int | str | None = None
    first_player_dp2_key: int | str | None = None
    event_second_player: str | None = None
    second_player_key: int | str | None = None
    second_player_dp1_key: int | str | None = None
    second_player_dp2_key: int | str | None = None
    event_final_result: str | None = None
    event_game_result: str | None = None
    event_serve: str | None = None
    event_winner: str | None = None
    event_status: str | None = None
    event_type_type: str | None = None
    tournament_name: str | None = None
    tournament_key: int | str | None = None
    tournament_round: str | None = None
    tournament_season: str | None = None
    event_live: str | None = None
    event_qualification: str | None = None
    pointbypoint: list[PbpGameDto] = Field(default_factory=list)
    scores: list[ScoreRowDto] = Field(default_factory=list)
    statistics: list[StatisticDto] = Field(default_factory=list)


class DrawTournamentDto(VendorModel):
    tournament_key: int | str | None = None
    tournament_name: str | None = None
    tournament_surface: str | None = None
    tournament_country: str | None = None
    tournament_season: str | None = None


class DrawResultDto(VendorModel):
    tournament: DrawTournamentDto | None = None
    source: str | None = None
    brackets: list[dict[str, Any]] = Field(default_factory=list)


class HeadToHeadDto(VendorModel):
    h2h: list[MatchDto] = Field(default_factory=list, alias="H2H")
    first_player_results: list[MatchDto] = Field(
        default_factory=list, alias="firstPlayerResults"
    )
    second_player_results: list[MatchDto] = Field(
        default_factory=list, alias="secondPlayerResults"
    )


class PlayerSeasonStatDto(VendorModel):
    season: str | None = None
    type: str | None = None
    rank: str | None = None
    titles: str | None = None
    matches_won: str | None = None
    matches_lost: str | None = None


class StandingDto(VendorModel):
    place: int | str | None = None
    player: str | None = None
    player_key: int | str | None = None
    league: str | None = None
    movement: str | None = None
    country: str | None = None
    points: int | str | None = None


class PlayerDto(VendorModel):
    player_key: int | str
    player_name: str | None = None
    player_full_name: str | None = None
    player_country: str | None = None
    player_bday: str | None = None
    stats: list[PlayerSeasonStatDto] = Field(default_factory=list)


class EventDto(VendorModel):
    event_type_key: int | str | None = None
    event_type_type: str | None = None
