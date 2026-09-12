import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.chat.models import ChatEvent, ChatEventType
from app.config import Settings
from app.main import create_app

FIXED_NOW = "2026-09-08T10:00:00Z"


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for frame in text.split("\n\n"):
        if not frame.strip():
            continue
        lines = frame.split("\n")
        assert lines[0].startswith("event: ")
        assert lines[1].startswith("data: ")
        events.append((lines[0][len("event: "):], json.loads(lines[1][len("data: "):])))
    return events


@pytest.fixture()
async def client() -> AsyncClient:
    app = create_app(Settings(_env_file=None, fixed_now=FIXED_NOW))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.mark.asyncio
async def test_chat_stream_returns_ordered_sse_events(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/chat/stream",
        json={
            "scope": "global",
            "messages": [{"role": "user", "content": "今晚 Sinner 几点打？"}],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"

    events = parse_sse(response.text)
    types = [event_type for event_type, _ in events]
    assert types[0] == "status"
    assert types[-1] == "done"
    assert "data" in types
    assert "text_delta" in types

    data = next(payload for event_type, payload in events if event_type == "data")
    assert data["kind"] == "matches"
    assert data["matches"][0]["id"].startswith("mat_")
    assert "fake-" not in response.text


@pytest.mark.asyncio
async def test_chat_stream_match_scope_uses_context(client: AsyncClient) -> None:
    listing = await client.get("/api/v1/matches", params={"status": "live"})
    match_id = listing.json()["data"][0]["id"]

    response = await client.post(
        "/api/v1/chat/stream",
        json={
            "scope": "match",
            "match_id": match_id,
            "messages": [{"role": "user", "content": "谁在发球？"}],
        },
    )

    events = parse_sse(response.text)
    data = next(payload for event_type, payload in events if event_type == "data")
    assert data["kind"] == "intelligence"
    assert data["packet"]["match_id"] == match_id
    assert data["answer_context"]["match_id"] == match_id
    assert events[-1][0] == "done"


@pytest.mark.asyncio
async def test_chat_stream_routes_supported_historical_queries(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/chat/stream",
        json={
            "scope": "global",
            "messages": [{"role": "user", "content": "昨天 Sinner 赢了吗？"}],
        },
    )

    events = parse_sse(response.text)
    assert [event_type for event_type, _ in events] == [
        "status",
        "status",
        "status",
        "data",
        "status",
        "status",
        "text_delta",
        "done",
    ]
    data = next(payload for event_type, payload in events if event_type == "data")
    text = next(payload for event_type, payload in events if event_type == "text_delta")
    assert data["kind"] == "matches"
    assert data["metadata"]["scope"] == "yesterday"
    assert text["delta"] == "当前没有查到符合条件的比赛。"


@pytest.mark.asyncio
async def test_chat_stream_rejects_broad_historical_queries(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/chat/stream",
        json={
            "scope": "global",
            "messages": [{"role": "user", "content": "Sinner 的全部历史战绩"}],
        },
    )

    events = parse_sse(response.text)
    assert [event_type for event_type, _ in events] == ["data", "text_delta", "done"]
    assert events[0][1]["kind"] == "unsupported"
    assert events[1][1]["delta"] == "P2 暂不支持大范围历史查询。"


@pytest.mark.asyncio
async def test_chat_stream_validates_request_body(client: AsyncClient) -> None:
    response = await client.post("/api/v1/chat/stream", json={"scope": "global", "messages": []})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_request"
    assert body["request_id"]


@pytest.mark.asyncio
async def test_chat_stream_frames_end_with_two_newlines(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/chat/stream",
        json={
            "scope": "global",
            "messages": [{"role": "user", "content": "现在有什么比赛？"}],
        },
    )

    text = response.text
    assert text.endswith("\n\n")
    assert "\n\n\n" not in text
    for frame in text.split("\n\n"):
        if frame.strip():
            assert frame.startswith("event: ")


@pytest.mark.asyncio
async def test_chat_stream_preserves_warning_events() -> None:
    class WarningOrchestrator:
        async def stream(self, payload):
            yield ChatEvent(
                type=ChatEventType.WARNING,
                payload={
                    "code": "optional_data_unavailable",
                    "message": "部分辅助资料暂未提供。",
                    "details": {},
                },
            )
            yield ChatEvent(type=ChatEventType.DONE, payload={"ok": True})

    app = create_app(
        Settings(_env_file=None, fixed_now=FIXED_NOW),
        chat_orchestrator=WarningOrchestrator(),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        response = await http_client.post(
            "/api/v1/chat/stream",
            json={
                "scope": "global",
                "messages": [{"role": "user", "content": "现在有什么比赛？"}],
            },
        )

    events = parse_sse(response.text)
    assert [event_type for event_type, _ in events] == ["warning", "done"]
    assert events[0][1]["code"] == "optional_data_unavailable"
