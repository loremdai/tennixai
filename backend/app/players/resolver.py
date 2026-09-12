"""Runtime deterministic player resolution.

The resolver only reads the local alias directory: no translation LLM, no
vendor text search. `ambiguous` and `not_found` are ordinary domain results;
callers decide whether to surface candidates or ask for more detail.
"""

from collections.abc import Awaitable, Callable

from app.errors import AppError
from app.players.models import (
    PlayerAliasKind,
    PlayerCandidate,
    PlayerResolution,
    PlayerResolutionStatus,
)
from app.players.normalization import normalize_player_name
from app.players.repository import PlayerDirectoryRepository


class PlayerResolver:
    def __init__(
        self,
        repository: PlayerDirectoryRepository,
        *,
        seeder: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._repository = repository
        self._seeder = seeder
        self._seeded = seeder is None

    async def resolve(
        self,
        query: str,
        *,
        context_player_ids: tuple[str, ...] = (),
        limit: int = 5,
    ) -> PlayerResolution:
        if not self._seeded:
            self._seeded = True
            await self._seeder()
        text = (query or "").strip()
        if not text:
            raise AppError("invalid_request", "Player query is required", 422)

        if text.startswith("ply_"):
            directory_player = await self._repository.get_player(text)
            if directory_player is None:
                return PlayerResolution(
                    status=PlayerResolutionStatus.NOT_FOUND, query=text
                )
            candidate = PlayerCandidate(
                player=directory_player.player,
                matched_alias=text,
                alias_kind=PlayerAliasKind.PREFERRED,
                current_rank=directory_player.player.ranking,
            )
            return PlayerResolution(
                status=PlayerResolutionStatus.RESOLVED,
                query=text,
                player=directory_player.player,
                candidates=(candidate,),
            )

        normalized = normalize_player_name(text)
        matches = await self._repository.find_aliases(normalized, limit=max(limit, 5))
        best_per_player: dict[str, PlayerCandidate] = {}
        for match in matches:
            best_per_player.setdefault(
                match.player.player.id,
                PlayerCandidate(
                    player=match.player.player,
                    matched_alias=match.alias.alias,
                    alias_kind=match.alias.kind,
                    current_rank=match.current_rank,
                ),
            )
        candidates = tuple(best_per_player.values())

        if len(candidates) == 1:
            return PlayerResolution(
                status=PlayerResolutionStatus.RESOLVED,
                query=text,
                player=candidates[0].player,
                candidates=candidates,
            )
        if context_player_ids:
            in_context = tuple(
                candidate
                for candidate in candidates
                if candidate.player.id in set(context_player_ids)
            )
            if len(in_context) == 1:
                return PlayerResolution(
                    status=PlayerResolutionStatus.RESOLVED,
                    query=text,
                    player=in_context[0].player,
                    candidates=candidates,
                )
        if len(candidates) > 1:
            obvious = self._obvious_short_alias_candidate(candidates)
            if obvious is not None:
                return PlayerResolution(
                    status=PlayerResolutionStatus.RESOLVED,
                    query=text,
                    player=obvious.player,
                    candidates=candidates,
                )
        if not candidates:
            return PlayerResolution(status=PlayerResolutionStatus.NOT_FOUND, query=text)
        return PlayerResolution(
            status=PlayerResolutionStatus.AMBIGUOUS,
            query=text,
            candidates=candidates[:limit],
        )

    @staticmethod
    def _obvious_short_alias_candidate(
        candidates: tuple[PlayerCandidate, ...],
    ) -> PlayerCandidate | None:
        """Spec §8.3: a short alias may resolve when one candidate is obvious.

        Only applies when nobody matched an identity-grade alias (preferred/
        full/provider). Exactly one candidate inside the published Top 200
        window while every other candidate sits outside it is obvious; any
        same-window conflict stays ambiguous.
        """
        identity_kinds = {
            PlayerAliasKind.PREFERRED,
            PlayerAliasKind.FULL,
            PlayerAliasKind.PROVIDER,
        }
        if any(candidate.alias_kind in identity_kinds for candidate in candidates):
            return None
        inside = [
            candidate
            for candidate in candidates
            if candidate.current_rank is not None and candidate.current_rank <= 200
        ]
        if len(inside) != 1:
            return None
        outside = [
            candidate
            for candidate in candidates
            if candidate.current_rank is None or candidate.current_rank > 200
        ]
        if len(outside) != len(candidates) - 1:
            return None
        return inside[0]
