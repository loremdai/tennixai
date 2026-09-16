"""The P2 business tools and the deterministic historical guard.

Tools return canonical domain data only. The historical guard lives in the
chat layer because deterministic REST has no history endpoint; it never
calls the provider or the model.
"""

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.chat.models import (
    AnswerContext,
    ChatContext,
    ChatScope,
    FindPlayerMatchesArgs,
    GetHeadToHeadArgs,
    GetLiveMatchesArgs,
    GetMatchArgs,
    GetMatchIntelligenceArgs,
    GetPlayerResultsArgs,
    GetPlayerSeasonRecordArgs,
    MarketOpportunitiesPacket,
    PlayerHistoryContext,
    PlayerHistoryEmptyReason,
    StructuredToolResult,
)
from app.domain import CapabilityStatus, MatchSnapshot, Player
from app.errors import AppError
from app.intelligence import build_intelligence_packet
from app.players.models import PlayerResolutionStatus
from app.service import TennisService

DESCRIPTIONS = {
    "find_player_matches": "Find a player's matches for today, tonight, or their next scheduled match.",
    "get_live_matches": "List matches that are live now, optionally filtered by player name.",
    "get_match": "Get trusted details for one Tennix internal match ID.",
    "get_match_intelligence": "Get compact, topic-scoped canonical facts for the current match.",
    "get_player_results": (
        "Get a player's finished match results. scope=yesterday: matches on the previous local "
        "calendar day. scope=last: exactly the most recent finished match, even when older than "
        "30 days (limit is normalized to 1). scope=recent: the latest finished matches, default 5, "
        "accepts 1-10; a bare '赛果' request means recent. Use one call per player."
    ),
    "get_player_season_record": (
        "Get a player's season record (wins, losses, titles, available surface records). "
        "season defaults to the current season; only the current season through the four prior "
        "seasons are supported. Use one call per player."
    ),
    "get_head_to_head": "Get bounded head-to-head meetings for two players.",
    "list_market_opportunities": (
        "List current model-covered tennis market opportunities (BUY/WAIT) as compact "
        "canonical facts. Read-only; never creates orders."
    ),
    "get_match_decision": (
        "Get the current structured market decision snapshot for this match "
        "(action, reasons, probabilities, quote summary, paper position). Read-only."
    ),
}

TOOL_NAMES = (
    "find_player_matches",
    "get_live_matches",
    "get_match",
    "get_match_intelligence",
    "get_player_results",
    "get_player_season_record",
    "get_head_to_head",
    "list_market_opportunities",
    "get_match_decision",
)

P3_TOOL_NAMES = frozenset({"list_market_opportunities", "get_match_decision"})


class ListMarketOpportunitiesArgs(BaseModel):
    limit: int = Field(default=5, ge=1, le=10)


class GetMatchDecisionArgs(BaseModel):
    pass


class GlobalGetMatchArgs(BaseModel):
    match_id: str = Field(min_length=1)

ARGS_MODELS = {
    "find_player_matches": FindPlayerMatchesArgs,
    "get_live_matches": GetLiveMatchesArgs,
    "get_match": GetMatchArgs,
    "get_match_intelligence": GetMatchIntelligenceArgs,
    "get_player_results": GetPlayerResultsArgs,
    "get_player_season_record": GetPlayerSeasonRecordArgs,
    "get_head_to_head": GetHeadToHeadArgs,
    "list_market_opportunities": ListMarketOpportunitiesArgs,
    "get_match_decision": GetMatchDecisionArgs,
}

def _inline_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve local $defs so tool parameters expose inline enums."""
    definitions = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                return resolve(definitions[ref.rsplit("/", 1)[-1]])
            return {key: resolve(value) for key, value in node.items() if key != "$defs"}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve(schema)


class BusinessTools:
    def __init__(self, service: TennisService, *, p3_queries=None) -> None:
        self._service = service
        self._p3_queries = p3_queries

    def catalog(
        self,
        *,
        names: Iterable[str] | None = None,
        scope: ChatScope | None = None,
    ) -> list[dict[str, Any]]:
        selected_names = tuple(names) if names is not None else TOOL_NAMES
        if self._p3_queries is None:
            selected_names = tuple(
                name
                for name in selected_names
                if name not in P3_TOOL_NAMES
            )
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": DESCRIPTIONS[name],
                    "parameters": _inline_schema(
                        (
                            GlobalGetMatchArgs
                            if name == "get_match" and scope is ChatScope.GLOBAL
                            else ARGS_MODELS[name]
                        ).model_json_schema()
                    ),
                },
            }
            for name in selected_names
        ]

    async def freeze_match_context(self, context: ChatContext) -> ChatContext:
        """Capture the match snapshot once at the start of a chat request."""
        if (
            context.scope is not ChatScope.MATCH
            or context.match_id is None
            or context.snapshot is not None
        ):
            return context
        snapshot = await self._service.resolve_match_snapshot(context.match_id)
        return context.model_copy(update={"snapshot": snapshot})

    async def _resolve_player_query(
        self, query: str, context: ChatContext
    ) -> Player | StructuredToolResult:
        """Shared resolver entry point for every name-bearing tool."""
        context_ids = (
            tuple(player.id for player in context.snapshot.match.players)
            if context.snapshot is not None
            else ()
        )
        result = await self._service.resolve_player(
            query, context_player_ids=context_ids
        )
        if result.status is PlayerResolutionStatus.RESOLVED and result.player is not None:
            return result.player
        return StructuredToolResult(kind="player_resolution", resolution=result)

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: ChatContext,
    ) -> StructuredToolResult:
        def with_context(result: StructuredToolResult) -> StructuredToolResult:
            if (
                context.scope is ChatScope.MATCH
                and context.snapshot is not None
                and result.answer_context is None
            ):
                return result.model_copy(
                    update={"answer_context": _snapshot_answer_context(context.snapshot)}
                )
            return result

        try:
            if name == "find_player_matches":
                args = FindPlayerMatchesArgs.model_validate(arguments)
                resolved = await self._resolve_player_query(args.player_name, context)
                if isinstance(resolved, StructuredToolResult):
                    return with_context(resolved)
                matches = await self._service.find_player_matches_by_id(
                    resolved.id, args.time_scope
                )
                return with_context(StructuredToolResult(kind="matches", matches=matches))
            if name == "get_live_matches":
                args = GetLiveMatchesArgs.model_validate(arguments)
                if args.player_name:
                    resolved = await self._resolve_player_query(args.player_name, context)
                    if isinstance(resolved, StructuredToolResult):
                        return with_context(resolved)
                    matches = await self._service.list_matches_by_player_id(
                        "live", resolved.id
                    )
                else:
                    matches = await self._service.list_matches("live", None)
                return with_context(StructuredToolResult(kind="matches", matches=matches))
            if name == "get_match":
                args = GetMatchArgs.model_validate(arguments)
                match_id = context.match_id if context.scope is ChatScope.MATCH else args.match_id
                if match_id is None:
                    raise AppError("invalid_request", "match_id is required", 422)
                snapshot = context.snapshot
                match = (
                    snapshot.match
                    if snapshot is not None
                    else await self._service.get_match(match_id)
                )
                return with_context(StructuredToolResult(
                    kind="match",
                    matches=[match],
                    answer_context=(
                        _snapshot_answer_context(snapshot)
                        if snapshot is not None
                        else _answer_context(match.id, match.live_state, match.freshness.observed_at)
                    ),
                ))
            if name == "get_match_intelligence":
                args = GetMatchIntelligenceArgs.model_validate(arguments)
                if context.scope is not ChatScope.MATCH or context.match_id is None:
                    raise AppError(
                        "invalid_request",
                        "get_match_intelligence requires match scope",
                        422,
                    )
                packet = (
                    build_intelligence_packet(context.snapshot, topic=args.topic)
                    if context.snapshot is not None
                    else await self._service.get_match_intelligence(
                        context.match_id, args.topic
                    )
                )
                return with_context(StructuredToolResult(
                    kind="intelligence",
                    packet=packet,
                    answer_context=AnswerContext(
                        match_id=packet.match_id,
                        state_version=packet.state_version,
                        as_of=packet.as_of,
                    ),
                ))
            if name == "get_player_results":
                args = GetPlayerResultsArgs.model_validate(arguments)
                resolved = await self._resolve_player_query(args.player_name, context)
                if isinstance(resolved, StructuredToolResult):
                    return with_context(resolved)
                results = await self._service.get_player_results(
                    resolved.id, args.scope.value, args.limit
                )
                return with_context(StructuredToolResult(
                    kind="player_history",
                    matches=list(results.matches),
                    player_history=PlayerHistoryContext(
                        player=resolved,
                        scope=results.scope.value,
                        season=None,
                        availability=results.availability,
                        season_record=None,
                        empty_reason=(
                            PlayerHistoryEmptyReason.NO_RESULTS_IN_SCOPE
                            if not results.matches
                            and results.availability is not CapabilityStatus.UNAVAILABLE
                            else None
                        ),
                    ),
                ))
            if name == "get_player_season_record":
                args = GetPlayerSeasonRecordArgs.model_validate(arguments)
                resolved = await self._resolve_player_query(args.player_name, context)
                if isinstance(resolved, StructuredToolResult):
                    return with_context(resolved)
                season, record = await self._service.get_player_season_record(
                    resolved.id, season=args.season
                )
                return with_context(StructuredToolResult(
                    kind="player_history",
                    player_history=PlayerHistoryContext(
                        player=resolved,
                        scope="season",
                        season=season,
                        availability=(
                            CapabilityStatus.AVAILABLE
                            if record is not None
                            else CapabilityStatus.UNAVAILABLE
                        ),
                        season_record=record,
                        empty_reason=(
                            None
                            if record is not None
                            else PlayerHistoryEmptyReason.SEASON_RECORD_UNAVAILABLE
                        ),
                    ),
                ))
            if name == "get_head_to_head":
                args = GetHeadToHeadArgs.model_validate(arguments)
                first = await self._resolve_player_query(args.first_player_name, context)
                second = await self._resolve_player_query(args.second_player_name, context)
                if isinstance(first, StructuredToolResult):
                    return with_context(first)
                if isinstance(second, StructuredToolResult):
                    return with_context(second)
                results = await self._service.get_head_to_head(
                    first.id, second.id, args.limit
                )
                meetings = list(results.head_to_head.meetings) if results.head_to_head else []
                return with_context(StructuredToolResult(
                    kind="matches",
                    matches=meetings,
                    metadata={
                        "scope": "head_to_head",
                        "availability": results.availability.value,
                        "first_player_recent_count": (
                            len(results.head_to_head.first_player_recent)
                            if results.head_to_head
                            else 0
                        ),
                        "second_player_recent_count": (
                            len(results.head_to_head.second_player_recent)
                            if results.head_to_head
                            else 0
                        ),
                    },
                ))
            if name == "list_market_opportunities":
                args = ListMarketOpportunitiesArgs.model_validate(arguments)
                if self._p3_queries is None:
                    return with_context(StructuredToolResult(
                        kind="unsupported",
                        metadata={"reason": "p3_disabled"},
                    ))
                rows = await self._p3_queries.opportunities()
                limited = list(rows)[: args.limit]
                return with_context(StructuredToolResult(
                    kind="market_opportunities",
                    market_opportunities=MarketOpportunitiesPacket(
                        opportunities=limited,
                        truncated=len(rows) > len(limited),
                    ),
                ))
            if name == "get_match_decision":
                GetMatchDecisionArgs.model_validate(arguments)
                if self._p3_queries is None or context.match_id is None:
                    return with_context(StructuredToolResult(
                        kind="unsupported",
                        metadata={"reason": "p3_disabled"},
                    ))
                # The match id always comes from the frozen chat context;
                # model-provided ids are ignored.
                decision = await self._p3_queries.match_decision(context.match_id)
                return with_context(StructuredToolResult(
                    kind="match_decision",
                    match_decision=decision,
                ))
        except ValidationError as error:
            raise AppError(
                "invalid_request", "Invalid tool arguments", 422, {"tool": name}
            ) from error

        raise AppError("invalid_request", f"Unknown tool: {name}", 422)


def _answer_context(match_id: str, live_state: Any, as_of: Any) -> AnswerContext:
    return AnswerContext(
        match_id=match_id,
        state_version=live_state.state_version if live_state is not None else 0,
        as_of=as_of,
    )


def _snapshot_answer_context(snapshot: MatchSnapshot) -> AnswerContext:
    return AnswerContext(
        match_id=snapshot.match.id,
        state_version=snapshot.state_version,
        as_of=snapshot.as_of,
    )
