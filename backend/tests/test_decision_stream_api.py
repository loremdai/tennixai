"""Independent decision-stream reconnect semantics (T66).

The decision stream is snapshot-first with its own version cursor: a
reconnect carrying Last-Event-ID still receives the latest ready snapshot
so the client can detect a gap and refetch only decision state. The P2
match stream regression lives in test_match_stream_api.py and must stay
byte-compatible.
"""

import asyncio
import json
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.api.schemas import DecisionSnapshotDto
from app.config import Settings
from app.main import create_app
from test_market_stream_api import FakeP3Redis, _frames

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


class DecisionQueries:
    def __init__(self) -> None:
        self.decision = DecisionSnapshotDto(
            match_id="mat_9",
            market_id="mkt_9",
            action="hold",
            reason_code=None,
            observation_version=7,
            model_probabilities={"ply_a": 0.55, "ply_b": 0.45},
            model_availability="available",
            quote_average_price=None,
            quote_side=None,
            conservative_net_edge=None,
            position=None,
            lifecycle=("entry_pending", "filled"),
            is_stale=False,
            has_gap=False,
            lock_profit_available=False,
            as_of=NOW,
        )

    async def match_decision(self, match_id: str):
        return self.decision if match_id == "mat_9" else None

    async def markets_snapshot(self):
        return {"markets": 0, "opportunities": 0, "open_positions": 0}


@pytest.fixture()
async def env():
    app = create_app(
        Settings(
            _env_file=None,
            fixed_now="2026-09-16T12:00:00Z",
            sse_heartbeat_seconds=1,
        )
    )
    app.state.p3_redis = FakeP3Redis()
    app.state.p3_queries = DecisionQueries()

    # SSE needs a real streaming server; httpx ASGITransport buffers.
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=8125, log_level="error")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    try:
        async with AsyncClient(
            base_url="http://127.0.0.1:8125", trust_env=False
        ) as client:
            yield client, app
    finally:
        server.should_exit = True
        await serve_task


async def test_reconnect_with_last_event_id_is_snapshot_first(env):
    client, _ = env

    async def consume() -> str:
        chunks: list[str] = []
        async with client.stream(
            "GET",
            "/api/v1/matches/mat_9/decision/stream",
            headers={"Last-Event-ID": "2"},
        ) as response:
            assert response.status_code == 200
            async for chunk in response.aiter_text():
                chunks.append(chunk)
                if "event: ready" in "".join(chunks):
                    break
        return "".join(chunks)

    text = await asyncio.wait_for(consume(), timeout=5)
    frames = _frames(text)
    assert frames[0][0] == "ready"
    payload = frames[0][1]
    # The ready frame carries the durable latest version so a client at
    # version 2 can detect the gap and refetch decision state only.
    assert payload["observation_version"] == 7
    assert payload["action"] == "hold"


async def test_decision_stream_unknown_match_still_streams_ready(env):
    client, _ = env

    async def consume() -> str:
        chunks: list[str] = []
        async with client.stream(
            "GET", "/api/v1/matches/mat_missing/decision/stream"
        ) as response:
            async for chunk in response.aiter_text():
                chunks.append(chunk)
                if "event: ready" in "".join(chunks):
                    break
        return "".join(chunks)

    text = await asyncio.wait_for(consume(), timeout=5)
    frames = _frames(text)
    assert frames[0][0] == "ready"
    assert frames[0][1]["decision"] is None
    assert frames[0][1]["match_id"] == "mat_missing"


async def test_decision_stream_frames_end_with_double_newline(env):
    client, _ = env

    async def consume() -> str:
        chunks: list[str] = []
        async with client.stream(
            "GET", "/api/v1/matches/mat_9/decision/stream"
        ) as response:
            async for chunk in response.aiter_text():
                chunks.append(chunk)
                if "event: ready" in "".join(chunks):
                    break
        return "".join(chunks)

    text = await asyncio.wait_for(consume(), timeout=5)
    assert text.endswith("\n\n")
    assert json.dumps(_frames(text)[0][1])  # data payloads are valid JSON
