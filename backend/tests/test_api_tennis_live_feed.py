"""API-Tennis WebSocket feed adapter: auth params, validation, disconnects."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import websockets
import websockets.exceptions

from app.identity import MemoryIdentityRepository
from app.providers.api_tennis_live import ApiTennisLiveFeedProvider
from app.realtime.models import FeedDisconnected

FIXTURES = Path(__file__).parent / "fixtures" / "api_tennis"
NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
API_KEY = "test-key"
CLOSE = object()


class FakeConnectionClosed(websockets.exceptions.ConnectionClosedOK):
    def __init__(self) -> None:
        super().__init__(None, None)


class FakeConnection:
    def __init__(self, frames: list) -> None:
        self._frames = list(frames)
        self.closed = False

    async def recv(self) -> str:
        while not self._frames:
            await asyncio.sleep(0.01)
        frame = self._frames.pop(0)
        if frame is CLOSE:
            raise FakeConnectionClosed()
        return frame

    async def close(self) -> None:
        self.closed = True

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *exc_info) -> bool:
        await self.close()
        return False


class FakeConnector:
    def __init__(self, frames: list) -> None:
        self.frames = frames
        self.urls: list[str] = []
        self.connections: list[FakeConnection] = []

    def __call__(self, url: str):
        self.urls.append(url)
        connection = FakeConnection(self.frames)
        self.connections.append(connection)
        return connection


def make_provider(frames: list) -> tuple[ApiTennisLiveFeedProvider, FakeConnector, MemoryIdentityRepository]:
    connector = FakeConnector(frames)
    identities = MemoryIdentityRepository()
    provider = ApiTennisLiveFeedProvider(
        api_key=API_KEY,
        identities=identities,
        now=lambda: NOW,
        websocket_factory=connector,
    )
    return provider, connector, identities


def live_row() -> dict:
    return json.loads((FIXTURES / "livescore.json").read_text())["result"][0]


@pytest.mark.asyncio
async def test_stream_connects_with_key_match_and_timezone() -> None:
    provider, connector, _ = make_provider([CLOSE])

    with pytest.raises(FeedDisconnected):
        async for _ in provider.stream_match("11997372"):
            pass

    url = connector.urls[0]
    assert "APIkey=test-key" in url
    assert "match_key=11997372" in url
    assert "timezone=GMT" in url
    assert connector.connections[0].closed is True


@pytest.mark.asyncio
async def test_valid_frames_yield_envelopes() -> None:
    row = live_row()
    external = str(row["event_key"])
    provider, connector, _ = make_provider([json.dumps(row), CLOSE])

    envelopes = []
    with pytest.raises(FeedDisconnected):
        async for envelope in provider.stream_match(external):
            envelopes.append(envelope)

    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope.provider == "api_tennis"
    assert envelope.channel == "websocket"
    assert envelope.kind == "snapshot"
    assert envelope.payload["row"] == row
    assert envelope.received_at == NOW


@pytest.mark.asyncio
async def test_batch_frames_are_filtered_to_the_requested_match() -> None:
    row = live_row()
    external = str(row["event_key"])
    other = dict(row)
    other["event_key"] = 99999999
    provider, _, _ = make_provider([json.dumps([other, row, other]), CLOSE])

    envelopes = []
    with pytest.raises(FeedDisconnected):
        async for envelope in provider.stream_match(external):
            envelopes.append(envelope)

    assert len(envelopes) == 1
    assert envelopes[0].payload["row"]["event_key"] == row["event_key"]


@pytest.mark.asyncio
async def test_malformed_frames_are_skipped_without_breaking_the_stream() -> None:
    row = live_row()
    external = str(row["event_key"])
    provider, _, _ = make_provider(["{not json", json.dumps(row), CLOSE])

    envelopes = []
    with pytest.raises(FeedDisconnected):
        async for envelope in provider.stream_match(external):
            envelopes.append(envelope)

    assert len(envelopes) == 1


@pytest.mark.asyncio
async def test_connection_close_raises_feed_disconnected_without_leaking() -> None:
    provider, connector, _ = make_provider([CLOSE])

    with pytest.raises(FeedDisconnected) as error_info:
        async for _ in provider.stream_match("11997372"):
            pass

    message = str(error_info.value)
    assert API_KEY not in message
    assert "wss://" not in message
    assert "api-tennis" not in message


@pytest.mark.asyncio
async def test_to_candidate_maps_vendor_row_to_canonical_snapshot() -> None:
    row = live_row()
    provider, _, identities = make_provider([CLOSE])
    await identities.get_or_create("match", "api_tennis", str(row["event_key"]))
    await identities.get_or_create("player", "api_tennis", str(row["first_player_key"]))
    await identities.get_or_create("player", "api_tennis", str(row["second_player_key"]))

    envelope = (await provider._envelope_from_row(row))
    candidate = await provider.to_candidate(envelope)

    assert candidate is not None
    assert candidate.state_version == 0
    assert candidate.points
    assert candidate.match.id.startswith("mat_")
    dumped = candidate.model_dump_json()
    for token in ("event_key", "event_first_player", "pointbypoint", "stat_name"):
        assert token not in dumped
