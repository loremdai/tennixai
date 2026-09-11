"""The P2 business tools and the deterministic historical guard.

Tools return canonical domain data only. The historical guard lives in the
chat layer because deterministic REST has no history endpoint; it never
calls the provider or the model.
"""

import re
from typing import Any

from pydantic import ValidationError

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
    StructuredToolResult,
)
from app.domain import MatchSnapshot, Player
from app.errors import AppError
from app.intelligence import build_intelligence_packet
from app.service import TennisService

DESCRIPTIONS = {
    "find_player_matches": "Find a player's matches for today, tonight, or their next scheduled match.",
    "get_live_matches": "List matches that are live now, optionally filtered by player name.",
    "get_match": "Get trusted details for one Tennix internal match ID.",
    "get_match_intelligence": "Get compact, topic-scoped canonical facts for the current match.",
    "get_player_results": "Get a player's bounded yesterday or recent match results.",
    "get_head_to_head": "Get bounded head-to-head meetings for two players.",
}

TOOL_NAMES = (
    "find_player_matches",
    "get_live_matches",
    "get_match",
    "get_match_intelligence",
    "get_player_results",
    "get_head_to_head",
)

ARGS_MODELS = {
    "find_player_matches": FindPlayerMatchesArgs,
    "get_live_matches": GetLiveMatchesArgs,
    "get_match": GetMatchArgs,
    "get_match_intelligence": GetMatchIntelligenceArgs,
    "get_player_results": GetPlayerResultsArgs,
    "get_head_to_head": GetHeadToHeadArgs,
}

HISTORICAL_PHRASES = (
    "昨天",
    "昨日",
    "上一场",
    "最近一场",
    "历史",
    "yesterday",
    "last match",
    "previous match",
    "history",
)


def is_historical_query(text: str) -> bool:
    normalized = text.casefold()
    return any(phrase in normalized for phrase in HISTORICAL_PHRASES)


UNSUPPORTED_HISTORY_PHRASES = (
    "全部历史",
    "完整历史",
    "所有历史",
    "历史战绩",
    "all-time",
    "all time",
    "entire history",
    "career history",
)


def is_unsupported_historical_query(text: str) -> bool:
    normalized = text.casefold()
    if any(phrase in normalized for phrase in UNSUPPORTED_HISTORY_PHRASES):
        return True
    if any(
        phrase in normalized
        for phrase in ("交手", "对战", "h2h", "head-to-head", "head to head")
    ):
        return False
    return "历史" in normalized or "history" in normalized


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
    def __init__(self, service: TennisService) -> None:
        self._service = service

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": DESCRIPTIONS[name],
                    "parameters": _inline_schema(ARGS_MODELS[name].model_json_schema()),
                },
            }
            for name in TOOL_NAMES
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
                matches = await self._service.find_player_matches(args.player_name, args.time_scope)
                return with_context(StructuredToolResult(kind="matches", matches=matches))
            if name == "get_live_matches":
                args = GetLiveMatchesArgs.model_validate(arguments)
                matches = await self._service.list_matches("live", args.player_name)
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
                player = _context_player(context, args.player_name)
                results = (
                    await self._service.get_player_results(
                        player.id, args.scope.value, args.limit
                    )
                    if player is not None
                    else await self._service.get_player_results_by_name(
                        args.player_name, args.scope, args.limit
                    )
                )
                return with_context(StructuredToolResult(
                    kind="matches",
                    matches=list(results.matches),
                    metadata={
                        "scope": results.scope.value,
                        "availability": results.availability.value,
                    },
                ))
            if name == "get_head_to_head":
                args = GetHeadToHeadArgs.model_validate(arguments)
                first_player = _context_player(context, args.first_player_name)
                second_player = _context_player(context, args.second_player_name)
                results = (
                    await self._service.get_head_to_head(
                        first_player.id, second_player.id, args.limit
                    )
                    if first_player is not None and second_player is not None
                    else await self._service.get_head_to_head_by_name(
                        args.first_player_name, args.second_player_name, args.limit
                    )
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


def _context_player(context: ChatContext, query: str) -> Player | None:
    snapshot = context.snapshot
    if context.scope is not ChatScope.MATCH or snapshot is None:
        return None

    normalized_query = query.strip().casefold()
    if not normalized_query:
        return None
    players = list(snapshot.match.players)
    exact = [player for player in players if player.name.strip().casefold() == normalized_query]
    if len(exact) == 1:
        return exact[0]

    def tokens(value: str) -> list[str]:
        return re.findall(r"[a-z]+", value.casefold())

    query_tokens = tokens(query)
    candidates = []
    for player in players:
        player_tokens = tokens(player.name)
        if not query_tokens or not player_tokens:
            continue
        if query_tokens[-1] != player_tokens[-1]:
            continue
        if query_tokens[0][0] == player_tokens[0][0]:
            candidates.append(player)
    return candidates[0] if len(candidates) == 1 else None
