"""Narrow provider protocol for offline player catalog enumeration."""

from typing import Protocol

from app.players.models import RankingEntry, Tour


class PlayerCatalogProvider(Protocol):
    """Ranking enumeration only; realtime providers satisfy this structurally."""

    async def get_rankings(self, tour: Tour) -> tuple[RankingEntry, ...]:
        raise NotImplementedError
