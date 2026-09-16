from dataclasses import dataclass
from enum import StrEnum

from app.chat.history import HistoryCapability
from app.chat.models import ChatScope, ToolRequiredness


class ChatPhase(StrEnum):
    DISCOVERY = "discovery"
    CONTEXT = "context"
    ENRICHMENT = "enrichment"


@dataclass(frozen=True)
class ToolCapability:
    name: str
    allowed_scopes: frozenset[ChatScope]
    phases: frozenset[ChatPhase]
    requires: frozenset[str]
    parallel_safe: bool
    requiredness: ToolRequiredness
    timeout_seconds: float = 8.0


_CAPABILITIES = {
    "find_player_matches": ToolCapability(
        name="find_player_matches",
        allowed_scopes=frozenset({ChatScope.GLOBAL}),
        phases=frozenset({ChatPhase.DISCOVERY}),
        requires=frozenset({"player_identity"}),
        parallel_safe=True,
        requiredness=ToolRequiredness.CORE,
    ),
    "get_live_matches": ToolCapability(
        name="get_live_matches",
        allowed_scopes=frozenset({ChatScope.GLOBAL}),
        phases=frozenset({ChatPhase.DISCOVERY}),
        requires=frozenset(),
        parallel_safe=True,
        requiredness=ToolRequiredness.CORE,
    ),
    "get_match": ToolCapability(
        name="get_match",
        allowed_scopes=frozenset({ChatScope.GLOBAL, ChatScope.MATCH}),
        phases=frozenset({ChatPhase.ENRICHMENT, ChatPhase.CONTEXT}),
        requires=frozenset({"resolved_match_id"}),
        parallel_safe=False,
        requiredness=ToolRequiredness.CORE,
    ),
    "get_match_intelligence": ToolCapability(
        name="get_match_intelligence",
        allowed_scopes=frozenset({ChatScope.MATCH}),
        phases=frozenset({ChatPhase.CONTEXT}),
        requires=frozenset({"snapshot"}),
        parallel_safe=True,
        requiredness=ToolRequiredness.CORE,
    ),
    "get_player_results": ToolCapability(
        name="get_player_results",
        allowed_scopes=frozenset({ChatScope.GLOBAL, ChatScope.MATCH}),
        phases=frozenset({ChatPhase.DISCOVERY, ChatPhase.ENRICHMENT}),
        requires=frozenset({"player_identity"}),
        parallel_safe=True,
        requiredness=ToolRequiredness.OPTIONAL,
    ),
    "get_player_season_record": ToolCapability(
        name="get_player_season_record",
        allowed_scopes=frozenset({ChatScope.GLOBAL, ChatScope.MATCH}),
        phases=frozenset({ChatPhase.DISCOVERY, ChatPhase.ENRICHMENT}),
        requires=frozenset({"player_identity"}),
        parallel_safe=True,
        requiredness=ToolRequiredness.OPTIONAL,
    ),
    "get_head_to_head": ToolCapability(
        name="get_head_to_head",
        allowed_scopes=frozenset({ChatScope.GLOBAL, ChatScope.MATCH}),
        phases=frozenset({ChatPhase.DISCOVERY, ChatPhase.ENRICHMENT}),
        requires=frozenset({"player_identity"}),
        parallel_safe=True,
        requiredness=ToolRequiredness.OPTIONAL,
    ),
    "list_market_opportunities": ToolCapability(
        name="list_market_opportunities",
        allowed_scopes=frozenset({ChatScope.GLOBAL}),
        phases=frozenset({ChatPhase.DISCOVERY, ChatPhase.ENRICHMENT}),
        requires=frozenset(),
        parallel_safe=True,
        requiredness=ToolRequiredness.CORE,
    ),
    "get_match_decision": ToolCapability(
        name="get_match_decision",
        allowed_scopes=frozenset({ChatScope.MATCH}),
        phases=frozenset({ChatPhase.CONTEXT, ChatPhase.ENRICHMENT}),
        requires=frozenset(),
        parallel_safe=True,
        requiredness=ToolRequiredness.CORE,
    ),
}

TOOL_ORDER = tuple(_CAPABILITIES)

# Optional history tools are visible only when the deterministic capability
# classifier found the matching intent in the latest user message.
OPTIONAL_TOOL_CAPABILITY = {
    "get_player_results": HistoryCapability.LIMITED_RESULTS,
    "get_player_season_record": HistoryCapability.SEASON_RECORD,
    "get_head_to_head": HistoryCapability.HEAD_TO_HEAD,
}


def capability_for(name: str) -> ToolCapability | None:
    return _CAPABILITIES.get(name)


def allowed_tool_names(
    scope: ChatScope,
    phase: ChatPhase,
    *,
    history_capabilities: frozenset[HistoryCapability],
    has_discovered_matches: bool,
) -> tuple[str, ...]:
    names: list[str] = []
    for name in TOOL_ORDER:
        capability = _CAPABILITIES[name]
        phase_allowed = phase in capability.phases or (
            scope is ChatScope.GLOBAL
            and phase is ChatPhase.ENRICHMENT
            and name in {"find_player_matches", "get_live_matches"}
        )
        if scope not in capability.allowed_scopes or not phase_allowed:
            continue
        if capability.requiredness is ToolRequiredness.OPTIONAL:
            required = OPTIONAL_TOOL_CAPABILITY.get(name)
            if required is None or required not in history_capabilities:
                continue
        if name == "get_match" and scope is ChatScope.MATCH:
            continue
        if name == "get_match" and scope is ChatScope.GLOBAL and not has_discovered_matches:
            continue
        names.append(name)
    return tuple(names)


__all__ = [
    "ChatPhase",
    "ToolCapability",
    "ToolRequiredness",
    "TOOL_ORDER",
    "allowed_tool_names",
    "capability_for",
]
