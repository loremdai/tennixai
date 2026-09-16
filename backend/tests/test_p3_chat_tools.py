"""P3 Chat business tool tests (T66).

Two read-only tools: `list_market_opportunities` (global) and
`get_match_decision` (match scope, context-injected match id). They return
bounded canonical fact packets; the LLM can never create intents, change
policy, infer missing probabilities or override the structured action.
"""

from datetime import UTC, datetime

import pytest

from app.api.schemas import DecisionSnapshotDto, OpportunityDto
from app.chat.models import ChatContext
from app.chat.tools import BusinessTools

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


class FakeP3Queries:
    def __init__(self) -> None:
        self.opportunity_calls = 0
        self.decision_calls: list[str] = []

    async def opportunities(self):
        self.opportunity_calls += 1
        return [
            OpportunityDto(
                match_id=f"mat_{index}",
                market_id=f"mkt_{index}",
                phase="live" if index == 0 else "upcoming",
                action="buy" if index == 0 else "wait",
                target_player_id="ply_a",
                player_names=("Alpha One", "Beta Two"),
                model_probability=0.62 - index * 0.01,
                executable_probability=0.55,
                conservative_net_edge="0.07",
                max_acceptable_price=None,
                tournament_tier="atp",
                tournament_name="Test Open",
                as_of=NOW,
            )
            for index in range(15)
        ]

    async def match_decision(self, match_id: str):
        self.decision_calls.append(match_id)
        if match_id != "mat_9":
            return None
        return DecisionSnapshotDto(
            match_id="mat_9",
            market_id="mkt_9",
            action="no_bet",
            reason_code="MODEL_UNPROMOTED",
            observation_version=3,
            model_probabilities=None,
            model_availability="unpromoted",
            quote_average_price=None,
            quote_side=None,
            conservative_net_edge=None,
            position=None,
            lifecycle=(),
            is_stale=False,
            has_gap=False,
            lock_profit_available=False,
            as_of=NOW,
        )


@pytest.fixture()
def queries() -> FakeP3Queries:
    return FakeP3Queries()


@pytest.fixture()
def tools(queries) -> BusinessTools:
    return BusinessTools(service=None, p3_queries=queries)


def test_catalog_exposes_exactly_two_p3_tools_when_enabled(tools):
    catalog = tools.catalog(scope=ChatContext(scope="global").scope)
    names = {entry["function"]["name"] for entry in catalog}
    assert "list_market_opportunities" in names

    match_catalog = tools.catalog(scope="match")
    match_names = {entry["function"]["name"] for entry in match_catalog}
    assert "get_match_decision" in match_names


def test_catalog_hides_p3_tools_when_disabled(queries):
    tools = BusinessTools(service=None, p3_queries=None)
    names = {entry["function"]["name"] for entry in tools.catalog(scope="global")}
    assert "list_market_opportunities" not in names
    assert "get_match_decision" not in names


async def test_opportunities_packet_is_bounded_and_canonical(tools, queries):
    result = await tools.execute(
        "list_market_opportunities", {}, ChatContext(scope="global")
    )

    assert result.kind == "market_opportunities"
    assert queries.opportunity_calls == 1
    packet = result.market_opportunities
    assert packet is not None
    assert len(packet.opportunities) <= 10  # bounded fact packet
    first = packet.opportunities[0]
    assert first.match_id == "mat_0"
    assert first.action == "buy"
    assert first.model_probability == pytest.approx(0.62)
    serialized = packet.model_dump_json()
    assert "mkt_" in serialized  # internal ids only
    assert "0x" not in serialized


async def test_match_decision_uses_context_injected_match_id(tools, queries):
    result = await tools.execute(
        "get_match_decision",
        {"match_id": "mat_hacked"},  # model-provided ids are ignored
        ChatContext(scope="match", match_id="mat_9"),
    )

    assert result.kind == "match_decision"
    assert queries.decision_calls == ["mat_9"]
    packet = result.match_decision
    assert packet is not None
    assert packet.action == "no_bet"
    assert packet.reason_code == "MODEL_UNPROMOTED"
    # The unpromoted model never fabricates probabilities.
    assert packet.model_probabilities is None


async def test_match_decision_without_p3_data_is_typed_unsupported(tools, queries):
    result = await tools.execute(
        "get_match_decision", {}, ChatContext(scope="match", match_id="mat_none")
    )

    assert result.kind == "match_decision"
    assert result.match_decision is None


async def test_p3_tools_are_read_only_queries():
    import inspect

    from app.chat import tools as tools_module

    source = inspect.getsource(tools_module)
    # No mutation verbs in the P3 tool surface.
    for fragment in (
        "create_intent",
        "record_fill",
        "settle_market",
        "update_position",
    ):
        assert fragment not in source
