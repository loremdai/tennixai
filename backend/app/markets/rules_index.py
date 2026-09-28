"""Fresh, complete-scan rule state used to authorize decision actions."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class RuleAuthorization:
    rules_hash: str
    version: int

    @property
    def rules_changed(self) -> bool:
        # Until a deterministic rules parser is introduced, a subsequent
        # version remains action-blocked even if text later returns to A.
        return self.version > 1


class MarketRulesIndex:
    """In-memory projection refreshed only by a complete successful scan.

    An incomplete/failed scan invalidates the whole projection. This keeps a
    stale database snapshot from authorizing a BUY or SELL after the runtime
    can no longer confirm current provider rules.
    """

    def __init__(self, *, now: Callable[[], datetime], max_age: timedelta) -> None:
        if max_age <= timedelta(0):
            raise ValueError("max_age must be positive")
        self._now = now
        self._max_age = max_age
        self._as_of: datetime | None = None
        self._rules: dict[str, RuleAuthorization] = {}

    def invalidate(self) -> None:
        self._as_of = None
        self._rules = {}

    def publish(self, rules: Mapping[str, RuleAuthorization]) -> None:
        self._rules = dict(rules)
        self._as_of = self._now()

    def get(self, market_id: str) -> RuleAuthorization | None:
        if self._as_of is None:
            return None
        age = self._now() - self._as_of
        if age < timedelta(0) or age > self._max_age:
            self.invalidate()
            return None
        return self._rules.get(market_id)
