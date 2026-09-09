"""Redis viewer leases, demand index and grace semantics (spec §9)."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

DEMAND_INDEX_KEY = "tnx:demand"
GRACE_FIELD = "grace_until"
DEMANDED_AT_FIELD = "demanded_at"


class DemandedMatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    match_id: str
    state: str  # "active" | "grace"


class ViewerLeaseStore:
    def __init__(
        self,
        redis,
        *,
        lease_seconds: int,
        grace_seconds: int,
        now: Callable[[], float],
    ) -> None:
        self._redis = redis
        self._lease_seconds = lease_seconds
        self._grace_seconds = grace_seconds
        self._now = now
        self._arrival_seq = 0

    def _arrival_stamp(self) -> float:
        # Strictly increasing even when the injected clock stands still, so
        # capacity precedence follows true arrival order. The epsilon must
        # exceed float ulp at epoch-second magnitudes.
        self._arrival_seq += 1
        return self._now() + self._arrival_seq * 1e-6

    @staticmethod
    def _lease_key(match_id: str, viewer_id: str) -> str:
        return f"tnx:lease:{match_id}:{viewer_id}"

    @staticmethod
    def _meta_key(match_id: str) -> str:
        return f"tnx:demand:{match_id}"

    async def acquire(self, match_id: str, viewer_id: str) -> None:
        await self._redis.set(
            self._lease_key(match_id, viewer_id), "1", ex=self._lease_seconds
        )
        await self._redis.sadd(DEMAND_INDEX_KEY, match_id)
        meta_key = self._meta_key(match_id)
        if await self._redis.hget(meta_key, DEMANDED_AT_FIELD) is None:
            await self._redis.hset(
                meta_key, key=DEMANDED_AT_FIELD, value=repr(self._arrival_stamp())
            )
        await self._redis.hset(meta_key, key=viewer_id, value="1")
        await self._redis.hdel(meta_key, GRACE_FIELD)

    async def renew(self, match_id: str, viewer_id: str) -> None:
        await self._redis.set(
            self._lease_key(match_id, viewer_id), "1", ex=self._lease_seconds
        )

    async def release(self, match_id: str, viewer_id: str) -> None:
        meta_key = self._meta_key(match_id)
        fields = await self._redis.hgetall(meta_key)
        if viewer_id not in fields:
            return
        await self._redis.hdel(meta_key, viewer_id)
        await self._redis.delete(self._lease_key(match_id, viewer_id))
        remaining = await self._redis.hgetall(meta_key)
        viewers = [
            key for key in remaining if key not in (GRACE_FIELD, DEMANDED_AT_FIELD)
        ]
        if not viewers:
            await self._redis.hset(
                meta_key,
                key=GRACE_FIELD,
                value=str(self._now() + self._grace_seconds),
            )

    async def demanded_matches(self) -> list[DemandedMatch]:
        demanded: list[DemandedMatch] = []
        members = await self._redis.smembers(DEMAND_INDEX_KEY)
        ordered: list[tuple[float, str]] = []
        for match_id in members:
            stamp = await self._redis.hget(self._meta_key(match_id), DEMANDED_AT_FIELD)
            ordered.append((float(stamp) if stamp else 0.0, match_id))
        # First-come precedence when demand exceeds the subscription budget.
        for _, match_id in sorted(ordered):
            meta_key = self._meta_key(match_id)
            fields = await self._redis.hgetall(meta_key)
            viewer_ids = [
                key for key in fields if key not in (GRACE_FIELD, DEMANDED_AT_FIELD)
            ]
            alive: list[str] = []
            for viewer_id in viewer_ids:
                if await self._redis.get(self._lease_key(match_id, viewer_id)):
                    alive.append(viewer_id)
            if alive:
                if len(alive) != len(viewer_ids):
                    for stale in set(viewer_ids) - set(alive):
                        await self._redis.hdel(meta_key, stale)
                demanded.append(DemandedMatch(match_id=match_id, state="active"))
                continue
            grace_until = float(fields.get(GRACE_FIELD, "0") or 0)
            if grace_until > self._now():
                demanded.append(DemandedMatch(match_id=match_id, state="grace"))
                continue
            await self._redis.srem(DEMAND_INDEX_KEY, match_id)
            await self._redis.delete(meta_key)
        return demanded
