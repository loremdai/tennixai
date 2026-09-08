"""Opt-in live provider gate: real LiveTennisAPI with fake LLM-free assertions.

Run with: uv run pytest -m provider_live
Requires TENNIX_LIVETENNIS_API_KEY in the environment.
"""

import os
from datetime import datetime, timezone

import httpx
import pytest

from app.identity import MemoryIdentityRepository
from app.providers.livetennis import LiveTennisProvider

pytestmark = pytest.mark.provider_live


def _build_provider() -> LiveTennisProvider:
    api_key = os.environ.get("TENNIX_LIVETENNIS_API_KEY", "")
    if not api_key.strip():
        pytest.skip("TENNIX_LIVETENNIS_API_KEY not configured")
    client = httpx.AsyncClient(
        base_url=os.environ.get(
            "TENNIX_LIVETENNIS_BASE_URL", "https://api.livetennisapi.com/api/public/v1"
        ),
        timeout=10.0,
    )
    return LiveTennisProvider(
        client=client,
        identities=MemoryIdentityRepository(),
        api_key=api_key,
        now=lambda: datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_live_provider_returns_canonical_current_matches() -> None:
    provider = _build_provider()
    try:
        players = await provider.search_players("Sinner")
        assert players
        assert players[0].id.startswith("ply_")

        live = await provider.get_live_matches()
        upcoming = await provider.get_fixtures()
        if not live and not upcoming:
            pytest.skip("LiveTennisAPI currently reports no live or upcoming matches")

        matches = live or upcoming
        match = matches[0]
        assert match.id.startswith("mat_")
        assert match.tournament.id.startswith("trn_")
        for player in match.players:
            assert player.id.startswith("ply_")
        if match.scheduled_at is not None:
            assert match.scheduled_at.tzinfo is not None

        dumped = match.model_dump_json()
        assert "event_key" not in dumped
        assert "event_first_player" not in dumped
        assert "tournament_id" not in dumped
        assert "scheduled_time" not in dumped
    finally:
        await provider._client.aclose()
