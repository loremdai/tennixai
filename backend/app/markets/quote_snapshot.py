"""Coverage-lane snapshot plumbing (T85).

Turns a private token batch into durable latest-quote rows and keeps the raw
batch material in the existing 14-day raw store. Nothing here may touch the
realtime WebSocket lane, the prediction service, the decision worker or the
paper ledger: this lane only fills display quotes for the market pages.
"""

from collections.abc import Sequence
from datetime import datetime

from app.markets.quotes import ClobBooksBatch

RAW_CHANNEL = "market"
RAW_KIND = "clob_books_batch"


async def record_raw_batch(
    raw_repo,
    *,
    observed_at: datetime,
    batch: ClobBooksBatch,
    batch_index: int,
) -> None:
    """Persist one raw batch response (never per token) for diagnostics.

    The payload is private diagnostic material under the existing 14-day
    retention; it never reaches a public DTO, log or page. `match_id` and
    `external_match_id` stay None because a batch spans several markets.
    """
    if not batch.raw:
        return
    await raw_repo.append(
        provider="polymarket",
        channel=RAW_CHANNEL,
        kind=RAW_KIND,
        payload={"batch_index": int(batch_index), "books": list(batch.raw)},
        observed_at=observed_at,
    )


def batch_tokens(token_pairs: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    """Flatten, de-duplicate and stable-order the private tokens of many
    markets (one market contributes exactly two tokens)."""
    seen: dict[str, None] = {}
    for token_a, token_b in token_pairs:
        for token in (token_a, token_b):
            if token:
                seen.setdefault(token, None)
    return tuple(seen)


__all__ = ["RAW_CHANNEL", "RAW_KIND", "batch_tokens", "record_raw_batch"]
