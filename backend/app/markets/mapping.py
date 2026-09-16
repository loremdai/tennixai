"""Exact market-to-match mapping (T59).

Strict combination rule: both moneyline outcomes resolve through the shared
PlayerResolver to internal player IDs, the unordered pair must match exactly
one candidate match, the schedule must sit inside a bounded tolerance window
and the event context (singles discipline) must not conflict. Fuzzy string
scores, LLM judgement and manual permanent bindings are never the final
authority. A failed mapping keeps the market visible as market-only data
without negative labels; it never reaches a decision.
"""

from collections.abc import Sequence
from datetime import timedelta
from enum import StrEnum

from pydantic import Field

from app.domain import Discipline, Match, MatchStatus
from app.domain import FrozenModel
from app.markets.models import Market
from app.players.models import PlayerResolutionStatus
from app.players.resolver import PlayerResolver

DEFAULT_SCHEDULE_TOLERANCE = timedelta(minutes=45)


class MappingStatus(StrEnum):
    MAPPED = "mapped"
    AMBIGUOUS = "ambiguous"
    NO_MATCH = "no_match"
    UNRESOLVED_PLAYER = "unresolved_player"
    OUT_OF_WINDOW = "out_of_window"


class LinkDecision(StrEnum):
    CREATE = "create"
    REPLACE = "replace"
    NOOP = "noop"
    FROZEN = "frozen"


class MappingResult(FrozenModel):
    status: MappingStatus
    match_id: str | None = None
    player_ids: tuple[str, str] | None = None
    reason: str | None = None
    candidate_count: int = Field(default=0, ge=0)


def evaluate_link_change(
    *,
    current_market_id: str | None,
    target_market_id: str,
    intent_exists: bool,
) -> LinkDecision:
    """Condition replacement semantics.

    The relationship freezes once any intent exists: an identical target is a
    no-op and any change is refused. Without intents, a replacement market may
    take over the active link.
    """
    if current_market_id == target_market_id:
        return LinkDecision.NOOP
    if intent_exists:
        return LinkDecision.FROZEN
    if current_market_id is None:
        return LinkDecision.CREATE
    return LinkDecision.REPLACE


async def map_market(
    market: Market,
    matches: Sequence[Match],
    resolver: PlayerResolver,
    *,
    schedule_tolerance: timedelta = DEFAULT_SCHEDULE_TOLERANCE,
) -> MappingResult:
    player_ids: list[str] = []
    for index, outcome in enumerate(market.outcomes):
        resolution = await resolver.resolve(outcome.player_id)
        if resolution.status is not PlayerResolutionStatus.RESOLVED:
            # The canonical id may be a stale placeholder; fall back once to
            # the outcome name through the same deterministic resolver.
            resolution = await resolver.resolve(outcome.name)
        if (
            resolution.status is not PlayerResolutionStatus.RESOLVED
            or resolution.player is None
        ):
            return MappingResult(
                status=MappingStatus.UNRESOLVED_PLAYER,
                reason=f"outcome_{index}_unresolved",
            )
        player_ids.append(resolution.player.id)

    pair = frozenset(player_ids)
    pair_candidates = [
        match
        for match in matches
        if frozenset((match.players[0].id, match.players[1].id)) == pair
    ]
    if not pair_candidates:
        return MappingResult(status=MappingStatus.NO_MATCH, reason="no_pair_match")

    eligible = [
        match
        for match in pair_candidates
        if match.tournament.discipline is Discipline.SINGLES
    ]
    if not eligible:
        return MappingResult(
            status=MappingStatus.NO_MATCH,
            reason="event_context_conflict",
            candidate_count=len(pair_candidates),
        )

    in_window: list[Match] = []
    for match in eligible:
        if match.scheduled_at is not None and market.event_start is not None:
            delta = abs(match.scheduled_at - market.event_start)
            if delta <= schedule_tolerance:
                in_window.append(match)
        elif match.status is MatchStatus.LIVE:
            # A live match without a schedule stamp is the pair's contest.
            in_window.append(match)

    if not in_window:
        return MappingResult(
            status=MappingStatus.OUT_OF_WINDOW,
            reason="schedule_outside_window",
            candidate_count=len(eligible),
        )
    if len(in_window) > 1:
        return MappingResult(
            status=MappingStatus.AMBIGUOUS,
            reason="multiple_pair_candidates",
            candidate_count=len(in_window),
        )
    winner = in_window[0]
    return MappingResult(
        status=MappingStatus.MAPPED,
        match_id=winner.id,
        player_ids=(player_ids[0], player_ids[1]),
        candidate_count=1,
    )
