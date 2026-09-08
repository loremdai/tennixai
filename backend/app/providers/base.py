from typing import Protocol

from app.domain import LiveMatchState, Match, Player


class TennisDataProvider(Protocol):
    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        raise NotImplementedError

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        raise NotImplementedError

    async def search_players(self, query: str) -> list[Player]:
        raise NotImplementedError

    async def get_match(self, match_id: str) -> Match:
        raise NotImplementedError

    async def get_score(self, match_id: str) -> LiveMatchState:
        raise NotImplementedError
