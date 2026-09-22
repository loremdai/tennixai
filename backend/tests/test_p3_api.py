"""Read-only P3 REST contract tests (T66).

Canonical enum filters/pagination, internal IDs only, ordered
opportunity/all/paper/pulse results, honest empty and degraded states, and
zero provider/wallet/private-key material in bodies, headers or errors.
"""

import json
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.schemas import (
    DecisionSnapshotDto,
    MarketPageDto,
    MarketQuoteDto,
    MarketSummaryDto,
    OpportunityDto,
    PaperPositionDto,
    PulseRowDto,
)
from app.config import Settings
from app.main import create_app

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)

FORBIDDEN_FRAGMENTS = (
    "0xfake",
    "990001112223334445551",
    "condition_id",
    "token_id",
    "wallet",
    "private_key",
    "clobTokenIds",
)


class FakeP3Queries:
    def __init__(self) -> None:
        self.opportunities_rows = [
            OpportunityDto(
                match_id="mat_live",
                market_id="mkt_live",
                phase="live",
                action="buy",
                target_player_id="ply_a",
                player_names=("Alpha One", "Beta Two"),
                model_probability=0.62,
                executable_probability=0.55,
                conservative_net_edge="0.07",
                max_acceptable_price=None,
                tournament_tier="atp",
                tournament_name="Test Open",
                as_of=NOW,
            ),
            OpportunityDto(
                match_id="mat_soon",
                market_id="mkt_soon",
                phase="upcoming",
                action="wait",
                target_player_id="ply_b",
                player_names=("Gamma Three", "Delta Four"),
                model_probability=0.58,
                executable_probability=0.57,
                conservative_net_edge=None,
                max_acceptable_price="0.5500",
                tournament_tier="wta",
                tournament_name="Test Trophy",
                as_of=NOW,
            ),
        ]
        self.market_rows = [
            MarketSummaryDto(
                market_id="mkt_live",
                match_id="mat_live",
                question="Alpha One vs. Beta Two: Match Winner",
                status="open",
                tier="atp",
                gender="men",
                phase="live",
                model_availability="available",
                decision_action="buy",
                reason_code=None,
                quote=MarketQuoteDto(
                    state="snapshot",
                    source="snapshot",
                    as_of=NOW,
                    outcome_bids=("0.55", "0.43"),
                    outcome_asks=("0.57", "0.45"),
                    best_bid=("ply_a", "0.55"),
                    best_ask=("ply_a", "0.57"),
                ),
                as_of=NOW,
            ),
            MarketSummaryDto(
                market_id="mkt_chall",
                match_id=None,
                question="Challenger Moneyline",
                status="open",
                tier="challenger",
                gender="men",
                phase="upcoming",
                model_availability="out_of_scope",
                decision_action=None,
                reason_code=None,
                quote=MarketQuoteDto(
                    state="unavailable",
                    source=None,
                    as_of=None,
                ),
                as_of=NOW,
            ),
        ]
        self.positions = [
            PaperPositionDto(
                position_id="pos_1",
                match_id="mat_pos",
                market_id="mkt_pos",
                outcome_player_id="ply_a",
                player_names=("Alpha One", "Beta Two"),
                status="open",
                entry_cost="10.00",
                shares="19.05",
                current_exit_value="11.40",
                net_pnl=None,
                freshness_as_of=NOW,
            )
        ]
        self.decision = DecisionSnapshotDto(
            match_id="mat_live",
            market_id="mkt_live",
            action="buy",
            reason_code=None,
            observation_version=4,
            model_probabilities={"ply_a": 0.62, "ply_b": 0.38},
            model_availability="available",
            quote_average_price="0.55",
            quote_side="entry",
            conservative_net_edge="0.07",
            position=None,
            lifecycle=(),
            is_stale=False,
            has_gap=False,
            lock_profit_available=False,
            as_of=NOW,
        )

    async def opportunities(self):
        return self.opportunities_rows

    async def opportunity_view(self):
        from app.api.schemas import OpportunityAvailabilityDto

        rows = list(self.opportunities_rows)
        return rows, OpportunityAvailabilityDto(
            reason="HAS_OPPORTUNITIES" if rows else "NO_ELIGIBLE_ACTION",
            model_status="unknown",
        )

    async def markets(
        self, *, tier=None, gender=None, phase=None, page=1, page_size=20
    ):
        rows = self.market_rows
        if tier is not None:
            rows = [row for row in rows if row.tier == tier]
        if gender is not None:
            rows = [row for row in rows if row.gender == gender]
        if phase is not None:
            rows = [row for row in rows if row.phase == phase]
        total = len(rows)
        start = (page - 1) * page_size
        return MarketPageDto(
            markets=rows[start : start + page_size],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def paper_positions(self):
        return {"open": self.positions, "recent": []}

    async def pulse(self):
        rows = [
            PulseRowDto(
                match_id="mat_pos",
                market_id="mkt_pos",
                kind="position",
                action="hold",
                player_names=("Alpha One", "Beta Two"),
                model_probability=0.6,
                executable_probability=0.57,
                as_of=NOW,
            )
        ]
        return {"data": rows[:3], "has_open_position": True}

    async def match_decision(self, match_id: str):
        if match_id != "mat_live":
            return None
        return self.decision


@pytest.fixture()
async def client():
    app = create_app(Settings(_env_file=None, fixed_now="2026-09-16T12:00:00Z"))
    app.state.p3_queries = FakeP3Queries()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.fixture()
async def disabled_client():
    app = create_app(Settings(_env_file=None))
    app.state.p3_queries = None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


def assert_no_forbidden(payload_text: str) -> None:
    for fragment in FORBIDDEN_FRAGMENTS:
        assert fragment not in payload_text


async def test_opportunities_are_ordered_live_buy_first(client):
    response = await client.get("/api/v1/markets/opportunities")

    assert response.status_code == 200
    body = response.json()
    rows = body["data"]
    assert [row["match_id"] for row in rows] == ["mat_live", "mat_soon"]
    assert rows[0]["action"] == "buy"
    assert rows[1]["action"] == "wait"
    assert rows[1]["max_acceptable_price"] == "0.5500"
    # The empty-state explanation travels with the list, as a reason code.
    assert body["availability"]["reason"] in {
        "HAS_OPPORTUNITIES",
        "ELIGIBLE_UNPROMOTED",
        "NO_ELIGIBLE_ACTION",
        "NO_COVERED_MARKET",
        "DECISION_GAP",
    }
    assert_no_forbidden(response.text)


async def test_markets_list_supports_canonical_filters_and_pagination(client):
    response = await client.get(
        "/api/v1/markets", params={"tier": "atp", "page": 1, "page_size": 10}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["data"][0]["market_id"] == "mkt_live"
    assert_no_forbidden(response.text)


async def test_markets_list_rejects_unknown_enum(client):
    response = await client.get("/api/v1/markets", params={"tier": "futures"})
    assert response.status_code == 422


async def test_challenger_rows_show_market_data_without_negative_labels(client):
    response = await client.get("/api/v1/markets", params={"tier": "challenger"})

    rows = response.json()["data"]
    assert len(rows) == 1
    row = rows[0]
    assert row["model_availability"] == "out_of_scope"
    assert row["decision_action"] is None
    assert row["reason_code"] is None  # no "uncovered"-style negative label
    assert_no_forbidden(response.text)


async def test_paper_positions_open_first(client):
    response = await client.get("/api/v1/paper/positions")

    body = response.json()
    assert [row["status"] for row in body["open"]] == ["open"]
    assert body["recent"] == []
    assert_no_forbidden(response.text)


async def test_pulse_caps_rows_and_flags_open_position(client):
    response = await client.get("/api/v1/markets/pulse")

    body = response.json()
    assert body["has_open_position"] is True
    assert len(body["data"]) <= 3
    assert_no_forbidden(response.text)


async def test_match_decision_snapshot(client):
    response = await client.get("/api/v1/matches/mat_live/decision")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["action"] == "buy"
    assert body["observation_version"] == 4
    assert body["model_probabilities"] == {"ply_a": 0.62, "ply_b": 0.38}
    assert_no_forbidden(response.text)


async def test_match_decision_unknown_match_is_not_found(client):
    response = await client.get("/api/v1/matches/mat_missing/decision")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert_no_forbidden(response.text)


async def test_empty_states_are_honest(client):
    client._transport.app.state.p3_queries.opportunities_rows = []

    response = await client.get("/api/v1/markets/opportunities")

    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/markets/opportunities",
        "/api/v1/markets",
        "/api/v1/paper/positions",
        "/api/v1/markets/pulse",
        "/api/v1/matches/mat_live/decision",
    ],
)
async def test_p3_endpoints_are_disabled_without_p3_mode(disabled_client, path):
    response = await disabled_client.get(path)

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "p3_disabled"
    assert_no_forbidden(response.text)


async def test_headers_never_leak_provider_material(client):
    response = await client.get("/api/v1/markets/opportunities")
    header_blob = json.dumps(dict(response.headers)).lower()
    for fragment in ("0x", "token", "wallet", "private"):
        assert fragment not in header_blob
