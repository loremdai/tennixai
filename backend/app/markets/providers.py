"""P3 market provider boundary.

Read-only public Polymarket data access. Implementations must never bundle a
wallet, private key, signing routine, authenticated trading channel or order
submission; P3 is market intelligence plus paper trading only.
"""

from typing import AsyncIterator, Protocol, runtime_checkable

from app.markets.models import (
    Market,
    MarketEnvelope,
    MarketResolution,
    OrderBookState,
)


@runtime_checkable
class MarketDataProvider(Protocol):
    async def list_tennis_moneylines(self) -> tuple[Market, ...]: ...

    async def get_market(self, market_id: str) -> Market: ...

    async def get_order_book(self, market_id: str) -> OrderBookState: ...

    def subscribe_order_books(
        self, market_ids: tuple[str, ...]
    ) -> AsyncIterator[MarketEnvelope]: ...

    async def get_resolution(self, market_id: str) -> MarketResolution | None: ...
