"""T54 Task 1: deterministic history capability routing.

The classifier is the single authority for which optional history tools the
model may see. It never extracts player names or fabricates tool arguments.
"""

import pytest

from app.chat.capabilities import ChatPhase, allowed_tool_names
from app.chat.history import (
    HistoryCapability,
    classify_history_capabilities,
    is_broad_history_only,
)
from app.chat.models import ChatScope


def classify(text: str, scope: ChatScope = ChatScope.GLOBAL):
    return classify_history_capabilities(text, scope=scope)


LIMITED = HistoryCapability.LIMITED_RESULTS
SEASON = HistoryCapability.SEASON_RECORD
H2H = HistoryCapability.HEAD_TO_HEAD
BROAD = HistoryCapability.BROAD_HISTORY


# ------------------------------------------------------------------ yesterday


@pytest.mark.parametrize(
    "text",
    [
        "昨天 Sinner 赢了吗？",
        "昨日 Sinner 的比赛",
        "Did Sinner win yesterday?",
        "SINNER YESTERDAY RESULT",
    ],
)
def test_yesterday_wording_maps_to_limited_results(text: str) -> None:
    assert LIMITED in classify(text)


# ----------------------------------------------------------------- last match


@pytest.mark.parametrize(
    "text",
    [
        "辛纳上一场是什么时候？",
        "辛纳上一次比赛是什么时候？",
        "辛纳上一次打了谁？",
        "Sinner 上场比赛赢了吗",
        "Sinner last match",
        "When was Sinner's previous match?",
    ],
)
def test_last_match_wording_maps_to_limited_results(text: str) -> None:
    assert LIMITED in classify(text)


# --------------------------------------------------------------------- recent


@pytest.mark.parametrize(
    "text",
    [
        "郑钦文最近赛果如何？",
        "郑钦文近期表现",
        "郑钦文赛果如何？",
        "Sinner recent results",
        "最近一场 Sinner 的比赛",
    ],
)
def test_recent_wording_maps_to_limited_results(text: str) -> None:
    assert LIMITED in classify(text)


def test_bare_result_word_is_not_a_history_signal() -> None:
    assert classify("比赛结果怎么样？", scope=ChatScope.MATCH) == frozenset()
    assert classify("结果如何？", scope=ChatScope.MATCH) == frozenset()
    assert classify("这个结果说明什么？") == frozenset()


def test_match_scope_bare_result_does_not_expose_player_history() -> None:
    capabilities = classify("当前比赛结果如何？", scope=ChatScope.MATCH)
    assert LIMITED not in capabilities


def test_home_player_match_result_is_a_limited_results_signal() -> None:
    assert LIMITED in classify("Sinner 比赛结果", scope=ChatScope.GLOBAL)


# --------------------------------------------------------------------- season


@pytest.mark.parametrize(
    "text",
    [
        "郑钦文这个赛季战绩如何？",
        "Sinner 本赛季战绩",
        "当前赛季胜率",
        "今年战绩如何",
        "Sinner 赛季战绩",
        "Sinner season record",
    ],
)
def test_season_wording_maps_to_season_record(text: str) -> None:
    assert SEASON in classify(text)


# ------------------------------------------------------------------------ h2h


@pytest.mark.parametrize(
    "text",
    [
        "Sinner 和 Alcaraz 交手记录",
        "Sinner 对战 Alcaraz",
        "Sinner vs Alcaraz H2H",
        "head-to-head record",
        "Head To Head",
    ],
)
def test_h2h_wording_maps_to_head_to_head(text: str) -> None:
    assert H2H in classify(text)


# -------------------------------------------------------------- broad history


@pytest.mark.parametrize(
    "text",
    [
        "Sinner 的全部历史",
        "Sinner 完整历史战绩",
        "Sinner 生涯战绩",
        "Sinner all-time record",
        "Sinner 的历史",
    ],
)
def test_broad_history_wording_is_broad_only(text: str) -> None:
    capabilities = classify(text)
    assert BROAD in capabilities
    assert is_broad_history_only(capabilities)


def test_broad_history_mixed_with_supported_is_not_broad_only() -> None:
    capabilities = classify("Sinner 和 Alcaraz 的历史交手")
    assert H2H in capabilities
    assert BROAD in capabilities
    assert not is_broad_history_only(capabilities)

    mixed = classify("辛纳上一次比赛和全部历史")
    assert LIMITED in mixed
    assert BROAD in mixed
    assert not is_broad_history_only(mixed)


def test_is_broad_history_only_requires_exactly_broad() -> None:
    assert is_broad_history_only(frozenset({BROAD}))
    assert not is_broad_history_only(frozenset({BROAD, LIMITED}))
    assert not is_broad_history_only(frozenset())


# ------------------------------------------------------------- normalization


def test_classifier_normalizes_case_and_whitespace() -> None:
    assert H2H in classify("  sinner   HEAD-TO-HEAD  alcaraz ")
    assert LIMITED in classify("Sinner   LAST   MATCH")
    assert LIMITED in classify("ｓｉｎｎｅｒ　ｌａｓｔ　ｍａｔｃｈ")


def test_current_match_questions_have_no_history_capabilities() -> None:
    assert classify("现在有什么比赛？") == frozenset()
    assert classify("今晚 Sinner 几点打？") == frozenset()
    assert classify("What is the score now?") == frozenset()
    assert classify("当前比分是多少？", scope=ChatScope.MATCH) == frozenset()


def test_match_player_context_phrases_keep_optional_tools_visible() -> None:
    for text in ("分析当前比赛和球员特点。", "球员背景", "两位球员的优缺点", "player strengths"):
        capabilities = classify(text, scope=ChatScope.MATCH)
        assert LIMITED in capabilities
        assert H2H in capabilities


# ------------------------------------------------------------ catalog routing


def _allowed(capabilities, scope=ChatScope.GLOBAL, phase=ChatPhase.DISCOVERY):
    return allowed_tool_names(
        scope,
        phase,
        history_capabilities=capabilities,
        has_discovered_matches=False,
    )


def test_limited_results_exposes_only_results_tool() -> None:
    names = _allowed(frozenset({LIMITED}))
    assert "get_player_results" in names
    assert "get_head_to_head" not in names
    assert "get_player_season_record" not in names


def test_season_record_exposes_only_season_tool() -> None:
    names = _allowed(frozenset({SEASON}))
    assert "get_player_season_record" in names
    assert "get_player_results" not in names


def test_head_to_head_exposes_only_h2h_tool() -> None:
    names = _allowed(frozenset({H2H}))
    assert "get_head_to_head" in names
    assert "get_player_results" not in names


def test_no_capabilities_expose_no_optional_tools() -> None:
    names = _allowed(frozenset())
    assert "get_player_results" not in names
    assert "get_head_to_head" not in names
    assert "get_player_season_record" not in names
    assert {"find_player_matches", "get_live_matches"} <= set(names)


def test_multi_capability_prompt_exposes_every_relevant_tool() -> None:
    names = _allowed(frozenset({LIMITED, SEASON, H2H}))
    assert {"get_player_results", "get_player_season_record", "get_head_to_head"} <= set(
        names
    )


def test_match_scope_optional_tools_follow_capabilities() -> None:
    # Match scope starts in CONTEXT (intelligence only); optional history
    # tools appear in ENRICHMENT exactly when the capability is present.
    context_names = _allowed(
        frozenset({LIMITED}), scope=ChatScope.MATCH, phase=ChatPhase.CONTEXT
    )
    assert "get_match_intelligence" in context_names
    assert "get_player_results" not in context_names

    enrichment_names = _allowed(
        frozenset({LIMITED}), scope=ChatScope.MATCH, phase=ChatPhase.ENRICHMENT
    )
    assert "get_player_results" in enrichment_names

    enrichment_without = _allowed(
        frozenset(), scope=ChatScope.MATCH, phase=ChatPhase.ENRICHMENT
    )
    assert "get_player_results" not in enrichment_without
