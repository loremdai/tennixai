"""Redis hot snapshots and per-match pub/sub (spec §8)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime

from app.domain import MatchSnapshot
from app.realtime.models import LiveReduction


def match_channel(match_id: str) -> str:
    return f"tnx:match:{match_id}"


def hot_key(match_id: str) -> str:
    return f"tnx:hot:{match_id}"


class RealtimePublisher:
    def __init__(self, redis, *, now: Callable[[], datetime]) -> None:
        self._redis = redis
        self._now = now
        self.events: list[dict] = []

    async def publish_delta(self, reduction: LiveReduction) -> None:
        snapshot = reduction.snapshot
        event = {
            "type": "match_delta",
            "match_id": reduction.match_id,
            "state_version": snapshot.state_version,
            "as_of": snapshot.as_of.isoformat(),
            "changes": [change.value for change in reduction.events],
            "snapshot": json.loads(snapshot.model_dump_json()),
        }
        await self._redis.set(hot_key(reduction.match_id), snapshot.model_dump_json())
        await self._redis.publish(match_channel(reduction.match_id), json.dumps(event))
        self.events.append(event)

    async def publish_match_ended(
        self, match_id: str, state_version: int, as_of: datetime
    ) -> None:
        event = {
            "type": "match_ended",
            "match_id": match_id,
            "state_version": state_version,
            "as_of": as_of.isoformat(),
        }
        await self._redis.publish(match_channel(match_id), json.dumps(event))
        self.events.append(event)

    async def publish_connection(
        self, match_id: str, connection_status: str, as_of: datetime
    ) -> None:
        event = {
            "type": "match_delta",
            "match_id": match_id,
            "state_version": None,
            "as_of": as_of.isoformat(),
            "changes": ["connection_updated"],
            "connection_status": connection_status,
        }
        await self._redis.publish(match_channel(match_id), json.dumps(event))
        self.events.append(event)

    async def get_hot_snapshot(self, match_id: str) -> MatchSnapshot | None:
        raw = await self._redis.get(hot_key(match_id))
        if raw is None:
            return None
        return MatchSnapshot.model_validate_json(raw)


# ---------------------------------------------------------------------------
# P3 decision stream: an independent namespace and version cursor. A decision
# gap never touches the P2 sports stream and vice versa.
# ---------------------------------------------------------------------------


def decision_channel(match_id: str) -> str:
    return f"tnx:p3:decision:{match_id}"


def decision_hot_key(match_id: str) -> str:
    return f"tnx:p3:decision:hot:{match_id}"


class DecisionPublisher:
    def __init__(self, redis, *, now_fn=None) -> None:
        self._redis = redis
        self._now_fn = now_fn
        self.events: list[dict] = []

    async def publish_decision(self, observation) -> None:
        import json as _json

        event = {
            "type": "decision_delta",
            "match_id": observation.match_id,
            "observation_version": observation.observation_version,
            "action": observation.action.value,
            "as_of": observation.as_of.isoformat(),
        }
        await self._redis.set(
            decision_hot_key(observation.match_id),
            observation.model_dump_json(),
        )
        await self._redis.publish(
            decision_channel(observation.match_id), _json.dumps(event)
        )
        self.events.append(event)

    async def get_latest_decision(self, match_id: str):
        from app.decision.models import DecisionObservation

        raw = await self._redis.get(decision_hot_key(match_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return DecisionObservation.model_validate_json(raw)
