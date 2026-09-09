"""Opt-in API-Tennis REST smoke gate.

Run with:
    TENNIX_RUN_API_TENNIS_LIVE=1 uv run pytest -m api_tennis_live \
        tests/live/test_api_tennis_live.py -v

Reads TENNIX_API_TENNIS_API_KEY from the repository-root .env. Never prints
response bodies, and never writes the key into artifacts.
"""

import os
from datetime import datetime, timezone

import httpx
import pytest

from app.config import Settings
from app.identity import MemoryIdentityRepository
from app.providers.api_tennis import ApiTennisProvider

pytestmark = pytest.mark.api_tennis_live


def _require_enabled_key() -> tuple[Settings, str]:
    if os.environ.get("TENNIX_RUN_API_TENNIS_LIVE") != "1":
        pytest.skip("TENNIX_RUN_API_TENNIS_LIVE not set")
    settings = Settings(provider_mode="fake", llm_mode="fake")
    key = settings.api_tennis_api_key
    if key is None or not key.get_secret_value().strip():
        pytest.skip("TENNIX_API_TENNIS_API_KEY not configured")
    return settings, key.get_secret_value()


@pytest.mark.asyncio
async def test_api_tennis_rest_capability_and_canonical_shape() -> None:
    settings, api_key = _require_enabled_key()

    client = httpx.AsyncClient(base_url=settings.api_tennis_base_url, timeout=20.0)
    provider = ApiTennisProvider(
        client=client,
        identities=MemoryIdentityRepository(),
        api_key=api_key,
        now=lambda: datetime.now(timezone.utc),
    )
    try:
        # Authentication smoke: the event taxonomy call requires a valid key.
        events_payload = await provider._request("get_events", {})
        assert events_payload.get("success") == 1
        assert isinstance(events_payload.get("result"), list)

        live = await provider.get_live_matches()
        fixtures = await provider.get_fixtures()
        if not live and not fixtures:
            pytest.skip(
                "API-Tennis currently reports no live or upcoming matches; "
                "REST authentication verified"
            )

        sample = (live or fixtures)[:5]
        for match in sample:
            assert match.id.startswith("mat_")
            assert match.tournament.id.startswith("trn_")
            for player in match.players:
                assert player.id.startswith("ply_")
            if match.scheduled_at is not None:
                assert match.scheduled_at.tzinfo is not None
            assert match.freshness.provider == "api_tennis"

        dumped = "".join(match.model_dump_json() for match in sample)
        for vendor_token in (
            "event_key",
            "event_first_player",
            "first_player_key",
            "pointbypoint",
            "stat_name",
        ):
            assert vendor_token not in dumped
        assert api_key not in dumped

        if live:
            snapshot = await provider.get_match_snapshot(live[0].id)
            assert snapshot.match.id == live[0].id
            assert snapshot.state_version == (
                snapshot.match.live_state.state_version
                if snapshot.match.live_state is not None
                else 0
            )
            assert api_key not in snapshot.model_dump_json()
    finally:
        await client.aclose()
