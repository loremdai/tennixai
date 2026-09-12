"""Player directory repository contract and deterministic memory implementation.

The PostgreSQL implementation lives in `app.persistence.player_directory`; both
share these exact semantics (idempotent alias writes, ambiguity-preserving
lookups, bounded ranking snapshots, atomic localized-name batches).
"""

from datetime import date
from typing import Protocol

from app.domain import Gender, Player
from app.errors import AppError
from app.players.models import (
    AliasMatch,
    DirectoryPlayer,
    LocalizedNameUpdate,
    PlayerAlias,
    RankingEntry,
    Tour,
)

# Resolver-friendly ordering: identity-grade aliases first, loose surnames last.
ALIAS_KIND_PRIORITY = {
    "preferred": 0,
    "full": 1,
    "provider": 2,
    "reordered": 3,
    "abbreviated": 4,
    "transliterated": 5,
    "surname": 6,
}


class PlayerDirectoryRepository(Protocol):
    async def save_ranking_snapshot(self, entries: tuple[RankingEntry, ...]) -> None:
        raise NotImplementedError

    async def upsert_aliases(self, aliases: tuple[PlayerAlias, ...]) -> int:
        raise NotImplementedError

    async def save_localized_names(self, updates: tuple[LocalizedNameUpdate, ...]) -> int:
        raise NotImplementedError

    async def get_player(self, player_id: str) -> DirectoryPlayer | None:
        raise NotImplementedError

    async def get_rankings(
        self,
        tour: Tour,
        *,
        page: int,
        page_size: int,
        country_code: str | None,
    ) -> tuple[tuple[RankingEntry, ...], int]:
        raise NotImplementedError

    async def find_aliases(self, normalized_query: str, *, limit: int) -> tuple[AliasMatch, ...]:
        raise NotImplementedError

    async def list_players_missing_localized_name(
        self, *, limit: int
    ) -> tuple[DirectoryPlayer, ...]:
        raise NotImplementedError

    async def list_players_for_alias_sync(
        self, *, limit: int, after_id: str | None = None
    ) -> tuple[DirectoryPlayer, ...]:
        raise NotImplementedError

    async def prune_ranking_snapshots(self, *, keep_per_tour: int = 8) -> int:
        raise NotImplementedError

    async def directory_counts(self) -> dict[str, int]:
        raise NotImplementedError


class _RankingRow:
    __slots__ = ("entry",)

    def __init__(self, entry: RankingEntry) -> None:
        self.entry = entry


class MemoryPlayerDirectoryRepository:
    """Deterministic fake/test implementation of the directory protocol."""

    def __init__(self) -> None:
        self._players: dict[str, DirectoryPlayer] = {}
        self._aliases: list[PlayerAlias] = []
        self._rankings: list[RankingEntry] = []

    async def save_ranking_snapshot(self, entries: tuple[RankingEntry, ...]) -> None:
        for entry in entries:
            existing = self._players.get(entry.player.id)
            localized = existing.player.localized_name if existing else None
            gender = existing.gender if existing else Gender.UNKNOWN
            birth_date = existing.birth_date if existing else None
            image_url = existing.image_url if existing else None
            self._players[entry.player.id] = DirectoryPlayer(
                player=Player(
                    id=entry.player.id,
                    name=entry.player.name,
                    localized_name=localized,
                    country_code=entry.player.country_code,
                    ranking=entry.rank,
                ),
                gender=gender,
                birth_date=birth_date,
                image_url=image_url,
            )
        tours_dates = {(entry.tour, entry.ranking_date) for entry in entries}
        self._rankings = [
            row
            for row in self._rankings
            if (row.tour, row.ranking_date) not in tours_dates
        ]
        # Supplier standings can report tied ranks; one row per rank, first
        # player in (rank, player id) order wins, every player stays discoverable.
        unique: dict[tuple[Tour, object, int], RankingEntry] = {}
        for entry in sorted(entries, key=lambda item: (item.rank, item.player.id)):
            unique.setdefault((entry.tour, entry.ranking_date, entry.rank), entry)
        self._rankings.extend(unique.values())

    async def upsert_aliases(self, aliases: tuple[PlayerAlias, ...]) -> int:
        inserted = 0
        for alias in aliases:
            if any(
                existing.player_id == alias.player_id
                and existing.locale == alias.locale
                and existing.normalized_alias == alias.normalized_alias
                and existing.kind is alias.kind
                for existing in self._aliases
            ):
                continue
            self._aliases.append(alias)
            inserted += 1
        return inserted

    async def save_localized_names(self, updates: tuple[LocalizedNameUpdate, ...]) -> int:
        for update in updates:
            if update.player_id not in self._players:
                raise AppError(
                    "invalid_request",
                    "Localized name batch references an unknown player",
                    422,
                    {"player_id": update.player_id},
                )
        for update in updates:
            directory_player = self._players[update.player_id]
            self._players[update.player_id] = DirectoryPlayer(
                player=Player(
                    id=directory_player.player.id,
                    name=directory_player.player.name,
                    localized_name=update.localized_name,
                    country_code=directory_player.player.country_code,
                    ranking=directory_player.player.ranking,
                ),
                gender=directory_player.gender,
                birth_date=directory_player.birth_date,
                image_url=directory_player.image_url,
            )
            await self.upsert_aliases(update.aliases)
        return len(updates)

    async def get_player(self, player_id: str) -> DirectoryPlayer | None:
        return self._players.get(player_id)

    async def get_rankings(
        self,
        tour: Tour,
        *,
        page: int,
        page_size: int,
        country_code: str | None,
    ) -> tuple[tuple[RankingEntry, ...], int]:
        latest = self._latest_date(tour)
        rows = [
            entry
            for entry in self._rankings
            if entry.tour is tour and entry.ranking_date == latest
        ]
        if country_code is not None:
            rows = [entry for entry in rows if entry.player.country_code == country_code]
        rows.sort(key=lambda entry: (entry.rank, entry.player.id))
        start = (max(1, page) - 1) * page_size
        return tuple(rows[start : start + page_size]), len(rows)

    async def find_aliases(self, normalized_query: str, *, limit: int) -> tuple[AliasMatch, ...]:
        matches: list[AliasMatch] = []
        for alias in self._aliases:
            if alias.normalized_alias != normalized_query:
                continue
            directory_player = self._players.get(alias.player_id)
            if directory_player is None:
                continue
            matches.append(
                AliasMatch(
                    player=directory_player,
                    alias=alias,
                    current_rank=directory_player.player.ranking,
                )
            )
        matches.sort(
            key=lambda match: (
                ALIAS_KIND_PRIORITY[match.alias.kind.value],
                match.current_rank is None,
                match.current_rank if match.current_rank is not None else 0,
                match.player.player.id,
            )
        )
        return tuple(matches[:limit])

    async def list_players_missing_localized_name(
        self, *, limit: int
    ) -> tuple[DirectoryPlayer, ...]:
        missing = [
            player
            for player in self._players.values()
            if player.player.localized_name is None and player.player.name
        ]
        missing.sort(key=lambda player: player.player.id)
        return tuple(missing[:limit])

    async def list_players_for_alias_sync(
        self, *, limit: int, after_id: str | None = None
    ) -> tuple[DirectoryPlayer, ...]:
        players = [
            player
            for player in self._players.values()
            if player.player.name and (after_id is None or player.player.id > after_id)
        ]
        players.sort(key=lambda player: player.player.id)
        return tuple(players[:limit])

    async def prune_ranking_snapshots(self, *, keep_per_tour: int = 8) -> int:
        removed = 0
        for tour in Tour:
            dates = sorted(
                {entry.ranking_date for entry in self._rankings if entry.tour is tour},
                reverse=True,
            )
            keep = set(dates[:keep_per_tour])
            before = len(self._rankings)
            self._rankings = [
                entry
                for entry in self._rankings
                if entry.tour is not tour or entry.ranking_date in keep
            ]
            removed += before - len(self._rankings)
        return removed

    async def directory_counts(self) -> dict[str, int]:
        atp, _ = await self.get_rankings(Tour.ATP, page=1, page_size=10_000, country_code=None)
        wta, _ = await self.get_rankings(Tour.WTA, page=1, page_size=10_000, country_code=None)
        return {
            "players": len(self._players),
            "localized": sum(
                1 for player in self._players.values() if player.player.localized_name
            ),
            "aliases": len(self._aliases),
            "ranked_atp": len(atp),
            "ranked_wta": len(wta),
        }

    def _latest_date(self, tour: Tour) -> date | None:
        dates = [entry.ranking_date for entry in self._rankings if entry.tour is tour]
        return max(dates) if dates else None
