"""The three P1 business tools and the deterministic historical guard.

Tools return canonical domain data only. The historical guard lives in the
chat layer because deterministic REST has no history endpoint; it never
calls the provider or the model.
"""

from typing import Any

from pydantic import ValidationError

from app.chat.models import (
    ChatContext,
    ChatScope,
    FindPlayerMatchesArgs,
    GetLiveMatchesArgs,
    GetMatchArgs,
    StructuredToolResult,
)
from app.errors import AppError
from app.service import TennisService

DESCRIPTIONS = {
    "find_player_matches": "Find a player's matches for today, tonight, or their next scheduled match.",
    "get_live_matches": "List matches that are live now, optionally filtered by player name.",
    "get_match": "Get trusted details for one Tennix internal match ID.",
}

TOOL_NAMES = ("find_player_matches", "get_live_matches", "get_match")

ARGS_MODELS = {
    "find_player_matches": FindPlayerMatchesArgs,
    "get_live_matches": GetLiveMatchesArgs,
    "get_match": GetMatchArgs,
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

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: ChatContext,
    ) -> StructuredToolResult:
        try:
            if name == "find_player_matches":
                args = FindPlayerMatchesArgs.model_validate(arguments)
                matches = await self._service.find_player_matches(args.player_name, args.time_scope)
                return StructuredToolResult(kind="matches", matches=matches)
            if name == "get_live_matches":
                args = GetLiveMatchesArgs.model_validate(arguments)
                matches = await self._service.list_matches("live", args.player_name)
                return StructuredToolResult(kind="matches", matches=matches)
            if name == "get_match":
                args = GetMatchArgs.model_validate(arguments)
                match_id = context.match_id if context.scope is ChatScope.MATCH else args.match_id
                if match_id is None:
                    raise AppError("invalid_request", "match_id is required", 422)
                return StructuredToolResult(kind="match", matches=[await self._service.get_match(match_id)])
        except ValidationError as error:
            raise AppError(
                "invalid_request", "Invalid tool arguments", 422, {"tool": name}
            ) from error

        raise AppError("invalid_request", f"Unknown tool: {name}", 422)
