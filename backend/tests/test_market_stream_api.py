"""P3 SSE contract tests (T66).

`markets/stream` publishes ready/market/decision/paper/resolution deltas and
heartbeats over the independent P3 namespace; `decision/stream` carries its
own version cursor; the P2 match stream contract is untouched.
"""

import asyncio
import json
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.main import create_app

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


class FakePubSub:
    def __init__(self, redis: "FakeP3Redis") -> None:
        self._redis = redis
        self._patterns: list[str] = []
        self._queue: asyncio.Queue = asyncio.Queue()

    async def psubscribe(self, *patterns: str) -> None:
        for pattern in patterns:
            self._patterns.append(pattern)
            self._redis.listeners.setdefault(pattern, []).append(self._queue)

    async def get_message(self, ignore_subscribe_messages=True, timeout=None):
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except (asyncio.TimeoutError, TimeoutError):
            return None

    async def aclose(self) -> None:
        for pattern in self._patterns:
            queues = self._redis.listeners.get(pattern, [])
            if self._queue in queues:
                queues.remove(self._queue)
        self._patterns = []


class FakeP3Redis:
    """Pattern-publish fake for the independent P3 namespace."""

    def __init__(self) -> None:
        self.listeners: dict[str, list[asyncio.Queue]] = {}
        self.published: list[tuple[str, dict]] = []

    def pubsub(self) -> FakePubSub:
        return FakePubSub(self)

    async def publish_pattern(self, pattern: str, event: dict) -> None:
        self.published.append((pattern, event))
        for queue in list(self.listeners.get(pattern, [])):
            await queue.put({"pattern": pattern, "data": json.dumps(event)})

    async def get(self, key: str) -> str | None:
        return None


@pytest.fixture()
async def env():
    app = create_app(
        Settings(
            _env_file=None,
            fixed_now="2026-09-16T12:00:00Z",
            sse_heartbeat_seconds=1,
        )
    )
    redis = FakeP3Redis()
    app.state.p3_redis = redis
    app.state.p3_queries = _MinimalQueries()

    # SSE needs a real streaming server; httpx ASGITransport buffers.
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=8124, log_level="error")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    try:
        async with AsyncClient(base_url="http://127.0.0.1:8124") as client:
            yield client, redis
    finally:
        server.should_exit = True
        await serve_task


class _MinimalQueries:
    async def match_decision(self, match_id: str):
        return None

    async def markets_snapshot(self):
        return {
            "markets": 2,
            "opportunities": 1,
            "open_positions": 0,
            "availability": "HAS_OPPORTUNITIES",
        }


def _frames(text: str) -> list[tuple[str, dict, str | None]]:
    frames = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event = None
        data = None
        frame_id = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
            elif line.startswith("id: "):
                frame_id = line[len("id: ") :]
        if event is not None:
            frames.append((event, data or {}, frame_id))
    return frames


async def test_markets_stream_emits_ready_then_typed_deltas(env):
    client, redis = env

    async def consume() -> str:
        chunks: list[str] = []
        async with client.stream("GET", "/api/v1/markets/stream") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            async for chunk in response.aiter_text():
                chunks.append(chunk)
                if sum("event: " in part for part in chunks) >= 3:
                    break
        return "".join(chunks)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    await redis.publish_pattern(
        "tnx:p3:market:*",
        {
            "type": "market_delta",
            "market_id": "mkt_1",
            "sequence": 12,
            "book_hash": "h12",
        },
    )
    await redis.publish_pattern(
        "tnx:p3:decision:*",
        {
            "type": "decision_delta",
            "match_id": "mat_1",
            "observation_version": 5,
            "action": "wait",
        },
    )
    text = await asyncio.wait_for(task, timeout=5)

    frames = _frames(text)
    events = [frame[0] for frame in frames]
    assert events[0] == "ready"
    assert frames[0][1]["availability"] == "HAS_OPPORTUNITIES"
    assert "market_delta" in events
    assert "decision_delta" in events
    market_frame = next(frame for frame in frames if frame[0] == "market_delta")
    assert market_frame[2] == "12"  # event id from the market's own cursor
    decision_frame = next(frame for frame in frames if frame[0] == "decision_delta")
    assert decision_frame[2] == "5"  # decision cursor stays independent


async def test_decision_stream_ready_carries_own_version_cursor(env):
    client, redis = env

    async def consume() -> str:
        chunks: list[str] = []
        async with client.stream(
            "GET", "/api/v1/matches/mat_9/decision/stream"
        ) as response:
            assert response.status_code == 200
            async for chunk in response.aiter_text():
                chunks.append(chunk)
                if sum("event: " in part for part in chunks) >= 2:
                    break
        return "".join(chunks)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    await redis.publish_pattern(
        "tnx:p3:decision:*",
        {
            "type": "decision_delta",
            "match_id": "mat_9",
            "observation_version": 2,
            "action": "hold",
        },
    )
    text = await asyncio.wait_for(task, timeout=5)

    frames = _frames(text)
    assert frames[0][0] == "ready"
    assert frames[0][1]["match_id"] == "mat_9"
    delta = next(frame for frame in frames if frame[0] == "decision_delta")
    assert delta[2] == "2"


async def test_decision_stream_filters_other_matches(env):
    client, redis = env

    async def consume() -> str:
        chunks: list[str] = []
        async with client.stream(
            "GET", "/api/v1/matches/mat_9/decision/stream"
        ) as response:
            async for chunk in response.aiter_text():
                chunks.append(chunk)
                if "heartbeat" in "".join(chunks):
                    break
        return "".join(chunks)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    # Another match's decision must never reach this stream.
    await redis.publish_pattern(
        "tnx:p3:decision:*",
        {
            "type": "decision_delta",
            "match_id": "mat_other",
            "observation_version": 9,
            "action": "buy",
        },
    )
    text = await asyncio.wait_for(task, timeout=10)
    assert "mat_other" not in text
