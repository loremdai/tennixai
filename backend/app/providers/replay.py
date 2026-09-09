"""Deterministic, provider-only replay source for P2 acceptance.

Replay replaces the upstream REST/WebSocket transport while keeping the same
canonical identity, reducer, persistence, Redis and SSE path as a live
provider. Fixture records are sanitized and may contain a full initial
snapshot followed by small snapshot patches.
"""

from __future__ import annotations

import asyncio
import copy
import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.domain import (
    DataFreshness,
    DataQuality,
    HeadToHead,
    LiveMatchState,
    Match,
    MatchSnapshot,
    MatchStatus,
    Player,
    PointEvent,
    Tournament,
)
from app.errors import AppError
from app.identity import IdentityRepository, MemoryIdentityRepository
from app.providers.base import ProviderLiveEnvelope


@dataclass(frozen=True)
class _ReplayRecord:
    at_ms: int
    external_match_id: str
    kind: str
    snapshot: MatchSnapshot


class ReplayTennisProvider:
    """A deterministic REST + live-feed provider backed by sanitized JSONL."""

    provider_name = "replay"

    def __init__(
        self,
        records: tuple[dict[str, Any], ...],
        *,
        identities: IdentityRepository,
        clock: Any = None,
        speed: float = 1.0,
        identity_namespace: str = "replay",
    ) -> None:
        if speed <= 0:
            raise ValueError("replay speed must be greater than zero")
        if not identity_namespace.strip():
            raise ValueError("replay identity namespace is required")
        self._raw_records = records
        self._identities = identities
        self._clock = clock
        self._speed = speed
        self.identity_namespace = identity_namespace
        self._build_lock = asyncio.Lock()
        self._built = False
        self._records: dict[str, list[_ReplayRecord]] = {}
        self._initial: dict[str, MatchSnapshot] = {}
        self._current: dict[str, MatchSnapshot] = {}
        self._external_by_internal: dict[str, str] = {}
        self._internal_by_external: dict[str, str] = {}
        self._players: dict[str, Player] = {}
        self._stream_positions: dict[str, int] = {}
        self._stream_started: set[str] = set()
        self._last_disconnect_at_ms: dict[str, int] = {}
        self._identity_cache: dict[tuple[str, str], str] = {}
        self._point_ids: dict[str, str] = {}

        # Intentionally public diagnostics for deterministic tests and the
        # local runbook; they contain only sanitized match identifiers.
        self.opened_external_ids: list[str] = []
        self.rest_reconcile_calls: list[bool] = []

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        identities: IdentityRepository | None = None,
        clock: Any = None,
        speed: float = 1.0,
        identity_namespace: str = "replay",
    ) -> "ReplayTennisProvider":
        fixture = Path(path)
        if not fixture.is_file():
            raise FileNotFoundError(fixture)

        records: list[dict[str, Any]] = []
        last_at_ms: dict[str, int] = {}
        with fixture.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"invalid replay JSONL at line {line_number}") from error
                if not isinstance(record, dict):
                    raise ValueError(f"replay record at line {line_number} must be an object")
                at_ms = record.get("at_ms")
                external_match_id = record.get("match_id")
                kind = record.get("kind")
                payload = record.get("payload")
                if not isinstance(at_ms, int) or at_ms < 0:
                    raise ValueError(f"replay line {line_number} has invalid at_ms")
                if not isinstance(external_match_id, str) or not external_match_id:
                    raise ValueError(f"replay line {line_number} has invalid match_id")
                if not isinstance(kind, str) or not kind:
                    raise ValueError(f"replay line {line_number} has invalid kind")
                if not isinstance(payload, dict):
                    raise ValueError(f"replay line {line_number} payload must be an object")
                previous_at_ms = last_at_ms.get(external_match_id)
                if previous_at_ms is not None and at_ms < previous_at_ms:
                    raise ValueError(
                        f"replay timestamps must be monotonic for {external_match_id}"
                    )
                last_at_ms[external_match_id] = at_ms
                records.append(
                    {
                        "at_ms": at_ms,
                        "match_id": external_match_id,
                        "kind": kind,
                        "payload": payload,
                    }
                )

        if not records:
            raise ValueError("replay fixture is empty")
        return cls(
            tuple(records),
            identities=identities or MemoryIdentityRepository(),
            clock=clock,
            speed=speed,
            identity_namespace=identity_namespace,
        )

    async def _ensure_built(self) -> None:
        async with self._build_lock:
            if self._built:
                return
            previous: dict[str, dict[str, Any]] = {}
            for raw in self._raw_records:
                external_match_id = raw["match_id"]
                payload = raw["payload"]
                if "snapshot" in payload:
                    state = copy.deepcopy(payload["snapshot"])
                else:
                    if external_match_id not in previous:
                        raise ValueError(
                            f"replay match {external_match_id} must start with a snapshot"
                        )
                    state = copy.deepcopy(previous[external_match_id])
                    patch = payload.get("patch", {})
                    if not isinstance(patch, dict):
                        raise ValueError("replay patch must be an object")
                    for collection in ("points", "statistics", "momentum", "quality"):
                        if collection in patch:
                            state[collection] = copy.deepcopy(patch[collection])
                    if "match" in patch:
                        state["match"] = _merge_dict(state["match"], patch["match"])
                    if "as_of" in patch:
                        state["as_of"] = patch["as_of"]

                snapshot = MatchSnapshot.model_validate(state)
                canonical = await self._canonicalize(snapshot)
                record = _ReplayRecord(
                    at_ms=raw["at_ms"],
                    external_match_id=external_match_id,
                    kind=raw["kind"],
                    snapshot=canonical,
                )
                self._records.setdefault(external_match_id, []).append(record)
                previous[external_match_id] = state

            for external_match_id, records in self._records.items():
                if not records or records[0].kind != "snapshot":
                    raise ValueError(
                        f"replay match {external_match_id} must begin with kind=snapshot"
                    )
                self._initial[external_match_id] = records[0].snapshot
                self._current[external_match_id] = records[0].snapshot
                internal_id = records[0].snapshot.match.id
                self._internal_by_external[external_match_id] = internal_id
                self._external_by_internal[internal_id] = external_match_id
            self._built = True

    async def _canonicalize(self, snapshot: MatchSnapshot) -> MatchSnapshot:
        raw_match = snapshot.match
        match_id = await self._identity("match", raw_match.id)
        players: list[Player] = []
        for player in raw_match.players:
            player_id = await self._identity("player", player.id)
            canonical_player = player.model_copy(update={"id": player_id})
            players.append(canonical_player)
            self._players[player_id] = canonical_player
        tournament_id = await self._identity("tournament", raw_match.tournament.id)
        tournament = raw_match.tournament.model_copy(update={"id": tournament_id})

        live_state = raw_match.live_state
        if live_state is not None:
            live_state = live_state.model_copy(
                update={
                    "server_player_id": self._player_id(live_state.server_player_id),
                }
            )
        match = raw_match.model_copy(
            update={
                "id": match_id,
                "players": tuple(players),
                "tournament": tournament,
                "live_state": live_state,
                "winner_player_id": self._player_id(raw_match.winner_player_id),
                "freshness": raw_match.freshness.model_copy(
                    update={"provider": self.provider_name}
                ),
            }
        )

        points = tuple(
            point.model_copy(
                update={
                    "id": self._point_id(point.id),
                    "match_id": match_id,
                    "server_player_id": self._player_id(point.server_player_id),
                    "winner_player_id": self._player_id(point.winner_player_id),
                    "provider": self.provider_name,
                    "quality": self._quality(point.quality),
                }
            )
            for point in snapshot.points
        )
        statistics = tuple(
            statistic.model_copy(update={"match_id": match_id})
            for statistic in snapshot.statistics
        )
        momentum = tuple(
            observation.model_copy(
                update={
                    "match_id": match_id,
                    "leader_player_id": self._player_id(observation.leader_player_id),
                }
            )
            for observation in snapshot.momentum
        )
        quality = tuple(self._quality(item) for item in snapshot.quality)
        return snapshot.model_copy(
            update={
                "match": match,
                "points": points,
                "statistics": statistics,
                "momentum": momentum,
                "quality": quality,
            }
        )

    async def _identity(self, entity: str, external_id: str) -> str:
        key = (entity, str(external_id))
        internal_id = self._identity_cache.get(key)
        if internal_id is None:
            internal_id = await self._identities.get_or_create(
                entity, self.identity_namespace, str(external_id)
            )
            self._identity_cache[key] = internal_id
        return internal_id

    def _player_id(self, raw_id: str | None) -> str | None:
        if raw_id is None:
            return None
        return self._identity_cache.get(("player", str(raw_id)), raw_id)

    def _point_id(self, raw_id: str) -> str:
        raw_id = str(raw_id)
        if raw_id not in self._point_ids:
            digest = sha256(f"{self.provider_name}:{raw_id}".encode()).hexdigest()[:20]
            self._point_ids[raw_id] = f"pnt_{digest}"
        return self._point_ids[raw_id]

    def _quality(self, quality: DataQuality | None) -> DataQuality | None:
        if quality is None:
            return None
        return quality.model_copy(update={"provider": self.provider_name})

    async def _resolve_external(self, match_id: str) -> str:
        await self._ensure_built()
        if match_id in self._records:
            return match_id
        external = self._external_by_internal.get(match_id)
        if external is None:
            raise AppError("not_found", "Match not found", 404)
        return external

    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        await self._ensure_built()
        matches = [
            snapshot.match
            for snapshot in self._current.values()
            if snapshot.match.status is MatchStatus.LIVE
        ]
        return self._filter_matches(matches, player_id)

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        await self._ensure_built()
        matches = [
            snapshot.match
            for snapshot in self._current.values()
            if snapshot.match.status is MatchStatus.SCHEDULED
        ]
        return self._filter_matches(matches, player_id)

    async def search_players(self, query: str) -> list[Player]:
        await self._ensure_built()
        normalized = query.strip().casefold()
        if not normalized:
            return []
        return [
            player
            for player in self._players.values()
            if normalized in player.name.casefold()
        ]

    async def get_player(self, player_id: str) -> Player:
        await self._ensure_built()
        player = self._players.get(player_id)
        if player is None:
            raise AppError("not_found", "Player not found", 404)
        return player

    async def get_match(self, match_id: str) -> Match:
        external = await self._resolve_external(match_id)
        return self._current[external].match

    async def get_match_snapshot(self, match_id: str) -> MatchSnapshot:
        external = await self._resolve_external(match_id)
        return self._current[external]

    async def reconcile_match_snapshot(
        self, match_id: str, *, recovery: bool = False
    ) -> MatchSnapshot:
        """Return the initial or explicit recovery snapshot for the worker."""

        external = await self._resolve_external(match_id)
        self.rest_reconcile_calls.append(recovery)
        records = self._records[external]
        if recovery:
            record = next((item for item in records if item.kind == "reconcile"), None)
            if record is not None:
                disconnected_at = self._last_disconnect_at_ms.get(external)
                if disconnected_at is not None:
                    await self._sleep(
                        (record.at_ms - disconnected_at) / 1000.0 / self._speed
                    )
                self._current[external] = record.snapshot
                return record.snapshot
        if not self._stream_started.__contains__(external):
            return self._initial[external]
        return self._current[external]

    async def get_recent_results(self, player_id: str, *, limit: int) -> list[Match]:
        await self.get_player(player_id)
        return []

    async def get_head_to_head(
        self, first_player_id: str, second_player_id: str, *, limit: int
    ) -> HeadToHead:
        await self.get_player(first_player_id)
        await self.get_player(second_player_id)
        return HeadToHead(
            first_player_id=first_player_id,
            second_player_id=second_player_id,
            freshness=DataFreshness(provider=self.provider_name, observed_at=self._utcnow()),
        )

    async def get_score(self, match_id: str) -> LiveMatchState:
        match = await self.get_match(match_id)
        if match.live_state is None:
            raise AppError("not_found", "Score not available", 404)
        return match.live_state

    def stream_match(self, external_match_id: str):
        """Return a deterministic async stream, resuming after a disconnect."""

        if not isinstance(external_match_id, str) or not external_match_id:
            raise ValueError("external_match_id is required")
        self.opened_external_ids.append(external_match_id)
        self._stream_started.add(external_match_id)
        start = self._stream_positions.get(external_match_id, 0)

        async def generator():
            await self._ensure_built()
            records = self._records.get(external_match_id)
            if records is None:
                raise AppError("not_found", "Match not found", 404)
            previous_at_ms = records[start - 1].at_ms if start else records[0].at_ms
            for index in range(start, len(records)):
                record = records[index]
                delay = (record.at_ms - previous_at_ms) / 1000.0 / self._speed
                if delay > 0:
                    await self._sleep(delay)
                previous_at_ms = record.at_ms
                self._stream_positions[external_match_id] = index + 1
                self._current[external_match_id] = record.snapshot
                if record.kind == "disconnect":
                    self._last_disconnect_at_ms[external_match_id] = record.at_ms
                payload = (
                    {}
                    if record.kind == "disconnect"
                    else {"snapshot": record.snapshot.model_dump(mode="json")}
                )
                yield ProviderLiveEnvelope(
                    external_match_id=external_match_id,
                    provider=self.provider_name,
                    channel="replay",
                    kind=record.kind,
                    received_at=self._utcnow(),
                    payload=payload,
                )

        return generator()

    async def to_candidate(
        self, envelope: ProviderLiveEnvelope
    ) -> MatchSnapshot | None:
        if envelope.kind == "disconnect":
            return None
        payload = envelope.payload.get("snapshot")
        if payload is None:
            return None
        return MatchSnapshot.model_validate(payload)

    async def _sleep(self, seconds: float) -> None:
        sleeper = getattr(self._clock, "sleep", None)
        if sleeper is None:
            await asyncio.sleep(seconds)
            return
        result = sleeper(seconds)
        if inspect.isawaitable(result):
            await result

    def _utcnow(self) -> datetime:
        utcnow = getattr(self._clock, "utcnow", None)
        if callable(utcnow):
            value = utcnow()
            if value.tzinfo is None:
                raise ValueError("replay clock must return timezone-aware datetime")
            return value
        if callable(self._clock):
            value = self._clock()
            if value.tzinfo is None:
                raise ValueError("replay clock must return timezone-aware datetime")
            return value
        return datetime.now(timezone.utc)

    @staticmethod
    def _filter_matches(matches: list[Match], player_id: str | None) -> list[Match]:
        if player_id is None:
            return list(matches)
        return [
            match
            for match in matches
            if any(player.id == player_id for player in match.players)
        ]


def _merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result
