"""Narrow provider protocols for offline player catalog enumeration."""

from datetime import date
from typing import Protocol

from app.players.models import (
    PlayerProfileData,
    RankingEntry,
    Tour,
)


class PlayerCatalogProvider(Protocol):
    """Ranking enumeration only; realtime providers satisfy this structurally."""

    async def get_rankings(self, tour: Tour) -> tuple[RankingEntry, ...]:
        raise NotImplementedError


class PlayerProfileProvider(Protocol):
    """Season statistics and bounded historical results per player."""

    async def get_player_profile(self, player_id: str) -> PlayerProfileData:
        raise NotImplementedError

    async def get_player_results_for_period(
        self, player_id: str, *, start: date, end: date
    ) -> tuple:
        raise NotImplementedError
