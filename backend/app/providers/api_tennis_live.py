"""API-Tennis per-match WebSocket feed adapter (spec §3.1, §12).

Connects to the vendor live endpoint with the match filter, validates frames
into private envelopes, and maps them to canonical snapshots through the same
mapping helpers as the REST adapter. Disconnects surface as
`FeedDisconnected` whose reason never contains credentials or URIs.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from urllib.parse import urlencode

import websockets
import websockets.exceptions

from app.domain import MatchSnapshot
from app.identity import IdentityRepository
from app.providers.api_tennis import map_livescore_row_to_snapshot
from app.providers.api_tennis_dtos import MatchDto
from app.providers.base import ProviderLiveEnvelope
from app.realtime.models import FeedDisconnected

PROVIDER_NAME = "api_tennis"
DEFAULT_WS_URL = "wss://wss.api-tennis.com/live"


class ApiTennisLiveFeedProvider:
    def __init__(
        self,
        *,
        api_key: str,
        identities: IdentityRepository,
        now: Callable[[], datetime],
        base_url: str = DEFAULT_WS_URL,
        timezone: str = "GMT",
        websocket_factory: Callable[[str], object] | None = None,
    ) -> None:
        self._api_key = api_key
        self._identities = identities
        self._now = now
        self._base_url = base_url
        self._timezone = timezone
        self._connect = websocket_factory or websockets.connect

    def _build_url(self, external_match_id: str) -> str:
        params = urlencode(
            {
                "APIkey": self._api_key,
                "match_key": external_match_id,
                "timezone": self._timezone,
            }
        )
        return f"{self._base_url}?{params}"

    def stream_match(self, external_match_id: str) -> AsyncIterator[ProviderLiveEnvelope]:
        provider = self

        async def generator() -> AsyncIterator[ProviderLiveEnvelope]:
            url = provider._build_url(external_match_id)
            async with provider._connect(url) as connection:  # type: ignore[operator]
                while True:
                    try:
                        raw = await connection.recv()
                    except websockets.exceptions.ConnectionClosed as error:
                        raise FeedDisconnected("connection_closed") from error
                    try:
                        parsed = json.loads(raw)
                    except ValueError:
                        continue
                    # The vendor pushes batches of full live objects; keep
                    # only rows for this match (client-side safety net).
                    rows = parsed if isinstance(parsed, list) else [parsed]
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        if str(row.get("event_key", "")) != external_match_id:
                            continue
                        yield ProviderLiveEnvelope(
                            external_match_id=external_match_id,
                            provider=PROVIDER_NAME,
                            channel="websocket",
                            kind="snapshot",
                            received_at=provider._now(),
                            payload={"row": row},
                        )
            raise FeedDisconnected("stream_ended")

        return generator()

    async def _envelope_from_row(self, row: dict) -> ProviderLiveEnvelope:
        return ProviderLiveEnvelope(
            external_match_id=str(row.get("event_key", "")),
            provider=PROVIDER_NAME,
            channel="websocket",
            kind="snapshot",
            received_at=self._now(),
            payload={"row": row},
        )

    async def to_candidate(self, envelope: ProviderLiveEnvelope) -> MatchSnapshot | None:
        row = envelope.payload.get("row")
        if not isinstance(row, dict):
            return None
        try:
            dto = MatchDto.model_validate(row)
        except Exception:
            return None
        return await map_livescore_row_to_snapshot(dto, self._identities, self._now)
