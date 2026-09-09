"""Provider contracts.

`TennisDataProvider` is the P2 query contract (spec §6). The P1 legacy
`get_score` remains available on concrete adapters and is covered by the P1
regression suite, but new P2 code consumes `get_match_snapshot`.

`ProviderLiveEnvelope` is the private adapter→reducer DTO. It may carry full
vendor snapshots and must never reach API responses or Chat.
"""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Protocol

from pydantic import field_validator

from app.domain import (
    FrozenModel,
    HeadToHead,
    LiveMatchState,
    Match,
    MatchSnapshot,
    Player,
)


class ProviderLiveEnvelope(FrozenModel):
    external_match_id: str
    provider: str
    channel: str
    kind: str
    received_at: datetime
    payload: dict[str, Any]

    @field_validator("received_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class TennisDataProvider(Protocol):
    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        raise NotImplementedError

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        raise NotImplementedError

    async def search_players(self, query: str) -> list[Player]:
        raise NotImplementedError

    async def get_player(self, player_id: str) -> Player:
        raise NotImplementedError

    async def get_match(self, match_id: str) -> Match:
        raise NotImplementedError

    async def get_match_snapshot(self, match_id: str) -> MatchSnapshot:
        raise NotImplementedError

    async def get_recent_results(self, player_id: str, *, limit: int) -> list[Match]:
        raise NotImplementedError

    async def get_head_to_head(
        self, first_player_id: str, second_player_id: str, *, limit: int
    ) -> HeadToHead:
        raise NotImplementedError

    # P1 legacy: kept on adapters for the existing score path and regression
    # suite; superseded by get_match_snapshot in P2.
    async def get_score(self, match_id: str) -> LiveMatchState:
        raise NotImplementedError


class TennisLiveFeedProvider(Protocol):
    def stream_match(self, external_match_id: str) -> AsyncIterator[ProviderLiveEnvelope]:
        raise NotImplementedError
