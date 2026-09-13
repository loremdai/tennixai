"""Deterministic history capability routing (T54).

This module is the single authority for deciding which optional
player-history business tools the model may see. It only controls catalog
visibility: it never extracts player names, fabricates tool arguments, or
answers questions. The LLM remains responsible for splitting natural-language
clauses and choosing one call per player.
"""

import re
import unicodedata
from enum import StrEnum

from app.chat.models import ChatScope


class HistoryCapability(StrEnum):
    LIMITED_RESULTS = "limited_results"
    SEASON_RECORD = "season_record"
    HEAD_TO_HEAD = "head_to_head"
    BROAD_HISTORY = "broad_history"


_LIMITED_RESULTS_PHRASES = (
    # yesterday
    "昨天",
    "昨日",
    "yesterday",
    # last match
    "上一场",
    "上一次",
    "上场比赛",
    "最近一场",
    "last match",
    "previous match",
    # recent results; bare 赛果 means recent
    "最近",
    "近期",
    "赛果",
    "recent",
)

# `比赛结果` combined with a player identity is a limited-results signal in
# Home scope; in Match scope the same wording describes the current match.
_GLOBAL_LIMITED_RESULTS_PHRASES = (
    "比赛结果",
    "比赛成绩",
)

_SEASON_RECORD_PHRASES = (
    "本赛季",
    "这个赛季",
    "当前赛季",
    "今年",
    "赛季战绩",
    "赛季",
    "season record",
    "this season",
    "season",
)

_HEAD_TO_HEAD_PHRASES = (
    "交手",
    "对战",
    "h2h",
    "head-to-head",
    "head to head",
)

_BROAD_HISTORY_PHRASES = (
    "全部历史",
    "完整历史",
    "所有历史",
    "历史战绩",
    "生涯战绩",
    "生涯",
    "all-time",
    "all time",
    "entire history",
    "career history",
    "career",
    "历史",
    "history",
)

# Legacy Match-scope player-context wording: keeps the optional player tools
# visible exactly as the previous boolean gate did.
_PLAYER_CONTEXT_PHRASES = (
    "球员特点",
    "球员背景",
    "近期状态",
    "近期表现",
    "优缺点",
    "strengths",
    "weaknesses",
)

_WHITESPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return _WHITESPACE.sub(" ", normalized)


def _contains_any(normalized: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in normalized for phrase in phrases)


def classify_history_capabilities(
    text: str, *, scope: ChatScope
) -> frozenset[HistoryCapability]:
    normalized = _normalize(text)
    capabilities: set[HistoryCapability] = set()

    limited_phrases = _LIMITED_RESULTS_PHRASES
    if scope is ChatScope.GLOBAL:
        limited_phrases = limited_phrases + _GLOBAL_LIMITED_RESULTS_PHRASES
    if _contains_any(normalized, limited_phrases):
        capabilities.add(HistoryCapability.LIMITED_RESULTS)
    if _contains_any(normalized, _SEASON_RECORD_PHRASES):
        capabilities.add(HistoryCapability.SEASON_RECORD)
    if _contains_any(normalized, _HEAD_TO_HEAD_PHRASES):
        capabilities.add(HistoryCapability.HEAD_TO_HEAD)
    if _contains_any(normalized, _BROAD_HISTORY_PHRASES):
        capabilities.add(HistoryCapability.BROAD_HISTORY)
    if _contains_any(normalized, _PLAYER_CONTEXT_PHRASES):
        capabilities.add(HistoryCapability.LIMITED_RESULTS)
        capabilities.add(HistoryCapability.HEAD_TO_HEAD)

    return frozenset(capabilities)


def is_broad_history_only(capabilities: frozenset[HistoryCapability]) -> bool:
    return capabilities == frozenset({HistoryCapability.BROAD_HISTORY})


__all__ = [
    "HistoryCapability",
    "classify_history_capabilities",
    "is_broad_history_only",
]
