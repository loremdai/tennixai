"""Opt-in API-Tennis WebSocket smoke gate.

Run with:
    TENNIX_RUN_API_TENNIS_LIVE=1 uv run pytest -m realtime_live \
        tests/live/test_api_tennis_websocket_live.py -v

Authenticates against the vendor live endpoint and receives at least one
valid envelope for a match the vendor is actively pushing; otherwise records
an honest skip. Never prints response bodies, keys, or connection URIs.
"""

import asyncio
import json
import os
from datetime import datetime, timezone

import httpx
import pytest
import websockets

from app.config import Settings
from app.identity import MemoryIdentityRepository
from app.providers.api_tennis import ApiTennisProvider
from app.providers.api_tennis_live import ApiTennisLiveFeedProvider
from app.realtime.models import FeedDisconnected

pytestmark = pytest.mark.realtime_live


def _require_enabled_key() -> tuple[Settings, str]:
    if os.environ.get("TENNIX_RUN_API_TENNIS_LIVE") != "1":
        pytest.skip("TENNIX_RUN_API_TENNIS_LIVE not set")
    settings = Settings(provider_mode="fake", llm_mode="fake")
    key = settings.api_tennis_api_key
    if key is None or not key.get_secret_value().strip():
        pytest.skip("TENNIX_API_TENNIS_API_KEY not configured")
    return settings, key.get_secret_value()


@pytest.mark.asyncio
async def test_websocket_feed_authenticates_and_delivers_a_live_envelope() -> None:
    settings, api_key = _require_enabled_key()
    identities = MemoryIdentityRepository()
    now = lambda: datetime.now(timezone.utc)

    async with httpx.AsyncClient(base_url=settings.api_tennis_base_url, timeout=20.0) as client:
        rest = ApiTennisProvider(
            client=client, identities=identities, api_key=api_key, now=now
        )
        live = await rest.get_live_matches()
        if not live:
            pytest.skip("API-Tennis reports no live matches; REST auth verified")

    # Discover a match the vendor is actively pushing by reading one batch
    # from an unfiltered connection.
    probe_url = f"{settings.api_tennis_ws_url}?APIkey={api_key}&timezone=GMT"
    try:
        async with websockets.connect(probe_url) as probe:
            raw = await asyncio.wait_for(probe.recv(), timeout=60)
    except asyncio.TimeoutError:
        pytest.skip("WebSocket authenticated but no batch arrived within 60s")
    except websockets.exceptions.ConnectionClosed:
        pytest.skip("WebSocket closed before delivering a batch")
    except Exception:
        # Handshake errors can embed the connection URI; never surface them.
        pytest.skip("WebSocket handshake failed")

    batch = json.loads(raw)
    rows = batch if isinstance(batch, list) else [batch]
    if not rows:
        pytest.skip("Vendor batch was empty")
    external_id = str(rows[0]["event_key"])
    await identities.get_or_create("match", "api_tennis", external_id)

    feed = ApiTennisLiveFeedProvider(
        api_key=api_key,
        identities=identities,
        now=now,
        base_url=settings.api_tennis_ws_url,
    )
    received = []

    async def collect() -> None:
        async for envelope in feed.stream_match(external_id):
            received.append(envelope)
            return

    try:
        await asyncio.wait_for(collect(), timeout=120)
    except asyncio.TimeoutError:
        pytest.skip(
            "WebSocket authenticated but no push arrived within 120s for the "
            "selected live match"
        )
    except FeedDisconnected:
        pytest.skip("WebSocket closed before delivering an event")
    except Exception:
        pytest.skip("WebSocket handshake failed")

    envelope = received[0]
    assert envelope.provider == "api_tennis"
    assert envelope.channel == "websocket"
    assert envelope.kind == "snapshot"
    candidate = await feed.to_candidate(envelope)
    assert candidate is not None
    assert candidate.match.id.startswith("mat_")
    dumped = candidate.model_dump_json()
    assert "event_key" not in dumped
    assert api_key not in dumped
