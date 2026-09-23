"""Bounded coverage-lane snapshot job (T86).

Every round ranks the canonical open/scheduled markets fairly, takes at most
`max_markets`, batches their private tokens, calls the public CLOB
`POST /books` sequentially and writes the canonical result into the shared
latest-quote projection. A 429 ends the round and suppresses the following
rounds until the server-provided instant — never a busy retry.

This lane has exactly one job: fill display quotes. It never subscribes a
market WebSocket, never calls the LLM, and never touches prediction,
decision or paper.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.domain import CircuitTier, MatchStatus
from app.errors import AppError
from app.markets.quote_snapshot import batch_tokens, record_raw_batch
from app.markets.quotes import QuoteState, build_quote_snapshot, display_quote
from app.runtime.models import MarketQuoteCoverage

TIER_RANK: dict[CircuitTier, int] = {
    CircuitTier.ATP: 0,
    CircuitTier.WTA: 0,
    CircuitTier.CHALLENGER: 1,
    CircuitTier.ITF: 2,
    CircuitTier.OTHER: 3,
}

STATE_BUCKETS: dict[QuoteState, str] = {
    QuoteState.SNAPSHOT: "fresh_snapshot",
    QuoteState.PARTIAL: "partial",
    QuoteState.NO_LIQUIDITY: "no_liquidity",
    QuoteState.UNAVAILABLE: "unavailable",
    QuoteState.STALE: "stale",
    QuoteState.LIMITED: "limited",
}

ELIGIBLE_MARKET_STATUSES = frozenset({"open", "scheduled"})
DEFAULT_RETRY_AFTER_SECONDS = 60
MAX_RETRY_AFTER_SECONDS = 900


def retry_after_seconds(error: AppError) -> int:
    """Bounded, server-provided backoff; never an unbounded sleep."""
    raw = (error.details or {}).get("retry_after")
    try:
        seconds = int(str(raw))
    except (TypeError, ValueError):
        return DEFAULT_RETRY_AFTER_SECONDS
    return max(1, min(seconds, MAX_RETRY_AFTER_SECONDS))


@dataclass(frozen=True)
class SnapshotCandidate:
    market_id: str
    tokens: tuple[str, str]
    player_ids: tuple[str | None, str | None]
    sort_key: tuple


class MarketQuoteSnapshotJob:
    """One bounded coverage round per call. No scheduler of its own."""

    def __init__(
        self,
        *,
        markets,
        projections,
        provider,
        raw,
        catalog,
        hot_books,
        clock: Callable[[], datetime],
        max_markets: int = 500,
        token_batch_size: int = 500,
        quote_fresh_seconds: int = 300,
        realtime_fresh_seconds: int = 5,
        on_quotes_changed=None,
    ) -> None:
        self._markets = markets
        self._projections = projections
        self._provider = provider
        self._raw = raw
        self._catalog = catalog
        self._hot_books = hot_books
        self._clock = clock
        self._max_markets = max_markets
        self._token_batch_size = token_batch_size
        self._quote_fresh_seconds = quote_fresh_seconds
        self._realtime_fresh_seconds = realtime_fresh_seconds
        self._on_quotes_changed = on_quotes_changed
        self._retry_after_until: datetime | None = None
        self._last_successful_batch_at: datetime | None = None
        self._rotation_offset = 0

    @property
    def retry_after_until(self) -> datetime | None:
        return self._retry_after_until

    async def run_once(self) -> MarketQuoteCoverage:
        now = self._clock()
        backoff_active = (
            self._retry_after_until is not None and now < self._retry_after_until
        )
        candidates = await self._candidates()
        if candidates:
            start = self._rotation_offset % len(candidates)
            candidates = candidates[start:] + candidates[:start]
        selected = candidates[: self._max_markets]
        beyond = candidates[self._max_markets :]
        if selected and not backoff_active:
            self._rotation_offset = (start + len(selected)) % len(candidates)
        changed = 0
        if beyond:
            changed += await self._projections.mark_limited(
                [candidate.market_id for candidate in beyond],
                now=now,
                expires_at=now + timedelta(seconds=self._quote_fresh_seconds),
            )
        written: dict[str, object] = {}
        attempted: list[str] = []
        batch_failures = 0
        rate_limited = False
        if not backoff_active:
            for index, group in enumerate(self._batches(selected)):
                tokens = batch_tokens([candidate.tokens for candidate in group])
                try:
                    batch = await self._provider.get_order_books(tokens)
                except AppError as exc:
                    if exc.code == "rate_limited":
                        rate_limited = True
                        self._retry_after_until = now + timedelta(
                            seconds=retry_after_seconds(exc)
                        )
                        break
                    batch_failures += 1
                    continue
                await record_raw_batch(
                    self._raw, observed_at=now, batch=batch, batch_index=index
                )
                self._last_successful_batch_at = now
                for candidate in group:
                    record = build_quote_snapshot(
                        market_id=candidate.market_id,
                        token_ids=candidate.tokens,
                        player_ids=candidate.player_ids,
                        batch=batch,
                        observed_at=now,
                        expires_at=now + timedelta(seconds=self._quote_fresh_seconds),
                    )
                    changed += int(await self._projections.upsert(record))
                    written[candidate.market_id] = record
                    attempted.append(candidate.market_id)
        coverage = await self._coverage(
            now,
            candidates=candidates,
            attempted=attempted,
            written=written,
            batch_failures=batch_failures,
            rate_limited=rate_limited or backoff_active,
        )
        if changed and self._on_quotes_changed is not None:
            await self._on_quotes_changed(count=changed)
        return coverage

    # ------------------------------------------------------------------
    # Candidate selection and fair rotation
    # ------------------------------------------------------------------

    async def _candidates(self) -> list[SnapshotCandidate]:
        """Canonical open/scheduled listings with private token pairs.

        Stable priority is live first, then scheduled start time, then
        ATP/WTA before Challenger/ITF. A per-process round-robin offset moves
        the protection window across the ordered catalog each round.
        """
        overviews = await self._markets.list_market_overviews()
        eligible = [row for row in overviews if row.status in ELIGIBLE_MARKET_STATUSES]
        if not eligible:
            return []
        externals = await self._markets.list_external_ids(
            [row.market_id for row in eligible]
        )
        ranks = await self._match_ranks()
        candidates: list[SnapshotCandidate] = []
        for row in eligible:
            external = externals.get(row.market_id)
            if (
                external is None
                or not external.token_ids[0]
                or not external.token_ids[1]
            ):
                # No private token target yet: never invent one.
                continue
            is_live, tier = ranks.get(
                row.active_match_id or "", (False, CircuitTier.OTHER)
            )
            candidates.append(
                SnapshotCandidate(
                    market_id=row.market_id,
                    tokens=external.token_ids,
                    player_ids=(row.outcome_a_player_id, row.outcome_b_player_id),
                    sort_key=(
                        0 if is_live else 1,
                        row.event_start or datetime.max.replace(tzinfo=UTC),
                        TIER_RANK.get(tier, TIER_RANK[CircuitTier.OTHER]),
                        row.market_id,
                    ),
                )
            )
        candidates.sort(key=lambda candidate: candidate.sort_key)
        return candidates

    async def _match_ranks(self) -> dict[str, tuple[bool, CircuitTier]]:
        live = await self._catalog.list_matches(MatchStatus.LIVE)
        upcoming = await self._catalog.list_matches(MatchStatus.SCHEDULED)
        ranks = {match.id: (False, match.tournament.circuit) for match in upcoming}
        ranks.update({match.id: (True, match.tournament.circuit) for match in live})
        return ranks

    def _batches(
        self, candidates: Sequence[SnapshotCandidate]
    ) -> Iterator[Sequence[SnapshotCandidate]]:
        """Sequential batches bounded by the configured token budget."""
        per_batch = max(1, self._token_batch_size // 2)
        for start in range(0, len(candidates), per_batch):
            yield candidates[start : start + per_batch]

    # ------------------------------------------------------------------
    # Coverage aggregation
    # ------------------------------------------------------------------

    async def _coverage(
        self,
        now: datetime,
        *,
        candidates: Sequence[SnapshotCandidate],
        attempted: Sequence[str],
        written,
        batch_failures: int,
        rate_limited: bool,
    ) -> MarketQuoteCoverage:
        """Aggregate counts over every candidate.

        Each candidate is counted once through the same `display_quote` rule
        the pages use, so the buckets sum to `candidate` and a market that
        was never reached still reports the state its stored quote implies.
        """
        ids = [candidate.market_id for candidate in candidates]
        stored = dict(await self._projections.load_many(ids)) if ids else {}
        stored.update(written)
        try:
            hot = await self._hot_books.get_hot_books(tuple(ids))
        except Exception:  # noqa: BLE001 - coverage must never break the round
            hot = {}
        buckets = {
            "fresh_realtime": 0,
            "fresh_snapshot": 0,
            "partial": 0,
            "no_liquidity": 0,
            "unavailable": 0,
            "stale": 0,
            "limited": 0,
        }
        for market_id in ids:
            quote = display_quote(
                hot_book=hot.get(market_id),
                snapshot=stored.get(market_id),
                now=now,
                realtime_fresh_seconds=self._realtime_fresh_seconds,
                snapshot_fresh_seconds=self._quote_fresh_seconds,
            )
            if quote.state is QuoteState.REALTIME:
                buckets["fresh_realtime"] += 1
            else:
                buckets[STATE_BUCKETS[quote.state]] += 1
        return MarketQuoteCoverage(
            generated_at=now,
            candidate=len(ids),
            attempted=len(attempted),
            batch_failures=batch_failures,
            rate_limited=rate_limited,
            retry_after_until=self._retry_after_until,
            last_successful_batch_at=self._last_successful_batch_at,
            **buckets,
        )


__all__ = [
    "ELIGIBLE_MARKET_STATUSES",
    "MarketQuoteSnapshotJob",
    "SnapshotCandidate",
    "retry_after_seconds",
]
