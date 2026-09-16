"""Read-only public Polymarket REST adapter (T59).

Uses only public Gamma and CLOB read endpoints. This module never imports a
trading SDK, never requests a wallet or private key, never signs anything and
never submits or cancels an order. Provider event/condition/token identifiers
stop at this adapter and the private identity mapping; every returned model is
canonical and internal-ID only. Error messages never contain URLs, keys or
provider identifiers.
"""

import hashlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from pydantic import ValidationError

from app.errors import AppError
from app.markets.models import (
    BookLevel,
    Market,
    MarketEnvelope,
    MarketExecutionMetadata,
    MarketExternalId,
    MarketOutcome,
    MarketResolution,
    MarketRules,
    MarketStatus,
    OrderBookState,
    OutcomeBook,
    OutcomePayout,
    ResolutionStatus,
)
from app.markets.polymarket_dtos import (
    BookDto,
    ClobMarketInfoDto,
    FeeRateDto,
    GammaEventDto,
    GammaMarketDto,
)
from app.players.models import PlayerResolutionStatus
from app.players.resolver import PlayerResolver

PROVIDER_NAME = "polymarket"
TENNIS_TAG_SLUG = "tennis"
MONEYLINE_TYPE = "moneyline"
EVENTS_LIMIT = 200

Registrar = Callable[[str, str, tuple[str, str]], Awaitable[str]]
ExternalLookup = Callable[[str], Awaitable[MarketExternalId | None]]


class MarketSkip:
    """Typed skip diagnostic for one malformed/out-of-scope vendor market.

    Adapter-internal only: never rendered in public DTOs, chat or UI.
    """

    __slots__ = ("slug", "reason", "quality_code")

    def __init__(self, *, slug: str, reason: str, quality_code: str) -> None:
        self.slug = slug
        self.reason = reason
        self.quality_code = quality_code

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"MarketSkip(reason={self.reason!r}, quality_code={self.quality_code!r})"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


class PolymarketProvider:
    """Canonical `MarketDataProvider` over public read-only endpoints."""

    def __init__(
        self,
        *,
        gamma_base_url: str,
        clob_base_url: str,
        resolver: PlayerResolver,
        registrar: Registrar | None = None,
        external_lookup: ExternalLookup | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._gamma = httpx.AsyncClient(
            base_url=gamma_base_url, transport=transport, timeout=timeout
        )
        self._clob = httpx.AsyncClient(
            base_url=clob_base_url, transport=transport, timeout=timeout
        )
        self._resolver = resolver
        self._registrar = registrar
        self._external_lookup = external_lookup
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._skipped: list[MarketSkip] = []
        # condition_id -> resolved internal player ids, in outcome order.
        self._outcome_players: dict[str, tuple[str, str]] = {}

    @property
    def skipped(self) -> tuple[MarketSkip, ...]:
        return tuple(self._skipped)

    async def aclose(self) -> None:
        await self._gamma.aclose()
        await self._clob.aclose()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status = response.status_code
        if status == 404:
            raise AppError("not_found", "Polymarket resource not found", 404)
        if status == 429:
            raise AppError(
                "rate_limited",
                "Polymarket rate limit reached",
                429,
                {"retry_after": response.headers.get("Retry-After")},
            )
        if status >= 400:
            raise AppError("provider_unavailable", "Polymarket request failed", 503)

    async def _get_json(
        self, client: httpx.AsyncClient, path: str, params: dict | None = None
    ) -> Any:
        try:
            response = await client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise AppError(
                "provider_unavailable", "Polymarket request failed", 503
            ) from exc
        self._raise_for_status(response)
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise AppError(
                "provider_invalid_response",
                "Polymarket response was not valid JSON",
                502,
            ) from exc

    async def _resolve_outcome_players(
        self, dto: GammaMarketDto
    ) -> tuple[str, str] | None:
        names = dto.outcome_names()
        if len(names) != 2:
            return None
        player_ids: list[str] = []
        for name in names:
            resolution = await self._resolver.resolve(name)
            if resolution.status is not PlayerResolutionStatus.RESOLVED:
                return None
            assert resolution.player is not None  # noqa: S101 - RESOLVED implies player
            player_ids.append(resolution.player.id)
        return (player_ids[0], player_ids[1])

    async def _external(self, market_id: str) -> MarketExternalId:
        if self._external_lookup is None:
            raise AppError("not_found", "Unknown market", 404)
        mapping = await self._external_lookup(market_id)
        if mapping is None:
            raise AppError("not_found", "Unknown market", 404)
        return mapping

    async def _gamma_market_by_condition(self, condition_id: str) -> GammaMarketDto:
        payload = await self._get_json(
            self._gamma, "/markets", params={"condition_ids": condition_id}
        )
        if not isinstance(payload, list) or not payload:
            raise AppError("not_found", "Polymarket resource not found", 404)
        try:
            return GammaMarketDto.model_validate(payload[0])
        except ValidationError as exc:
            raise AppError(
                "provider_invalid_response",
                "Polymarket market payload was malformed",
                502,
            ) from exc

    def _canonical_market(
        self, *, market_id: str, dto: GammaMarketDto, player_ids: tuple[str, str]
    ) -> Market:
        names = dto.outcome_names()
        closed = bool(dto.closed)
        accepting = dto.acceptingOrders is not False
        if closed:
            status = (
                MarketStatus.RESOLVED
                if dto.umaResolutionStatus == "resolved"
                else MarketStatus.CLOSED
            )
        elif accepting:
            status = MarketStatus.OPEN
        else:
            status = MarketStatus.SCHEDULED
        return Market(
            id=market_id,
            question=dto.question or "",
            outcomes=(
                MarketOutcome(player_id=player_ids[0], name=names[0]),
                MarketOutcome(player_id=player_ids[1], name=names[1]),
            ),
            status=status,
            rules_version=1,
            match_id=None,
            event_start=_parse_iso(dto.gameStartTime) or _parse_iso(dto.startDate),
            event_end=_parse_iso(dto.endDate),
            provider=PROVIDER_NAME,
            observed_at=self._now_fn(),
        )

    # ------------------------------------------------------------------
    # MarketDataProvider protocol
    # ------------------------------------------------------------------

    async def list_tennis_moneylines(self) -> tuple[Market, ...]:
        if self._registrar is None:
            raise RuntimeError(
                "list_tennis_moneylines requires a market registrar binding"
            )
        payload = await self._get_json(
            self._gamma,
            "/events",
            params={
                "tag_slug": TENNIS_TAG_SLUG,
                "active": "true",
                "closed": "false",
                "limit": EVENTS_LIMIT,
            },
        )
        if not isinstance(payload, list):
            raise AppError(
                "provider_invalid_response",
                "Polymarket events payload was malformed",
                502,
            )
        self._skipped = []
        markets: list[Market] = []
        for raw_event in payload:
            if not isinstance(raw_event, dict):
                continue
            try:
                event = GammaEventDto.model_validate(raw_event)
            except ValidationError:
                self._skipped.append(
                    MarketSkip(
                        slug="",
                        reason="malformed_event",
                        quality_code="MALFORMED_EVENT",
                    )
                )
                continue
            for dto in event.markets:
                market = await self._market_from_listing(dto, event)
                if market is not None:
                    markets.append(market)
        return tuple(markets)

    async def _market_from_listing(
        self, dto: GammaMarketDto, event: GammaEventDto
    ) -> Market | None:
        slug = dto.slug or event.slug or ""
        if dto.closed or dto.active is False or dto.acceptingOrders is False:
            self._skipped.append(
                MarketSkip(slug=slug, reason="closed", quality_code="MARKET_CLOSED")
            )
            return None
        if (dto.sportsMarketType or "").casefold() != MONEYLINE_TYPE:
            self._skipped.append(
                MarketSkip(
                    slug=slug, reason="not_moneyline", quality_code="NOT_MONEYLINE"
                )
            )
            return None
        if len(dto.outcome_names()) != 2:
            self._skipped.append(
                MarketSkip(
                    slug=slug,
                    reason="malformed_outcomes",
                    quality_code="MALFORMED_OUTCOMES",
                )
            )
            return None
        token_ids = dto.token_ids()
        if len(token_ids) != 2 or not dto.conditionId:
            self._skipped.append(
                MarketSkip(
                    slug=slug,
                    reason="malformed_tokens",
                    quality_code="MALFORMED_TOKENS",
                )
            )
            return None
        player_ids = await self._resolve_outcome_players(dto)
        if player_ids is None:
            self._skipped.append(
                MarketSkip(
                    slug=slug,
                    reason="unresolved_player",
                    quality_code="UNRESOLVED_PLAYER",
                )
            )
            return None
        assert self._registrar is not None  # noqa: S101 - checked by caller
        internal_id = await self._registrar(
            str(event.id or ""), dto.conditionId, (token_ids[0], token_ids[1])
        )
        self._outcome_players[dto.conditionId] = player_ids
        return self._canonical_market(
            market_id=internal_id, dto=dto, player_ids=player_ids
        )

    async def get_market(self, market_id: str) -> Market:
        external = await self._external(market_id)
        dto = await self._gamma_market_by_condition(external.condition_id)
        player_ids = await self._player_ids_for(external, dto)
        return self._canonical_market(
            market_id=market_id, dto=dto, player_ids=player_ids
        )

    async def _player_ids_for(
        self, external: MarketExternalId, dto: GammaMarketDto
    ) -> tuple[str, str]:
        cached = self._outcome_players.get(external.condition_id)
        if cached is not None:
            return cached
        player_ids = await self._resolve_outcome_players(dto)
        if player_ids is None:
            raise AppError(
                "provider_invalid_response",
                "Polymarket market outcomes could not be resolved",
                502,
            )
        self._outcome_players[external.condition_id] = player_ids
        return player_ids

    async def get_order_book(self, market_id: str) -> OrderBookState:
        external = await self._external(market_id)
        dto = await self._gamma_market_by_condition(external.condition_id)
        player_ids = await self._player_ids_for(external, dto)
        books: list[OutcomeBook] = []
        hashes: list[str] = []
        timestamps: list[datetime] = []
        for token_id, player_id in zip(external.token_ids, player_ids, strict=True):
            payload = await self._get_json(
                self._clob, "/book", params={"token_id": token_id}
            )
            try:
                book_dto = BookDto.model_validate(payload)
            except ValidationError as exc:
                raise AppError(
                    "provider_invalid_response",
                    "Polymarket book payload was malformed",
                    502,
                ) from exc
            bids = self._canonical_levels(book_dto.bids, descending=True)
            asks = self._canonical_levels(book_dto.asks, descending=False)
            books.append(OutcomeBook(outcome_player_id=player_id, bids=bids, asks=asks))
            hashes.append(book_dto.hash or "")
            timestamp = book_dto.timestamp
            if timestamp is not None:
                try:
                    epoch_ms = int(str(timestamp))
                    timestamps.append(datetime.fromtimestamp(epoch_ms / 1000, tz=UTC))
                except (ValueError, OSError, OverflowError):
                    pass
        combined = hashlib.sha256(":".join(hashes).encode("utf-8")).hexdigest()
        now = self._now_fn()
        return OrderBookState(
            market_id=market_id,
            books=(books[0], books[1]),
            sequence=0,
            book_hash=combined,
            provider_timestamp=max(timestamps) if timestamps else now,
            received_at=now,
        )

    @staticmethod
    def _canonical_levels(levels: list, *, descending: bool) -> tuple[BookLevel, ...]:
        parsed: list[BookLevel] = []
        seen: set[Decimal] = set()
        for level in levels:
            price = _parse_decimal(level.price)
            size = _parse_decimal(level.size)
            if price is None or size is None or price <= 0 or size <= 0:
                raise AppError(
                    "provider_invalid_response",
                    "Polymarket book payload was malformed",
                    502,
                )
            if price in seen:
                raise AppError(
                    "provider_invalid_response",
                    "Polymarket book payload was malformed",
                    502,
                )
            seen.add(price)
            parsed.append(BookLevel(price=price, size=size))
        parsed.sort(key=lambda item: item.price, reverse=descending)
        return tuple(parsed)

    async def get_execution_metadata(self, market_id: str) -> MarketExecutionMetadata:
        external = await self._external(market_id)
        info_payload = await self._get_json(
            self._clob, f"/clob-markets/{external.condition_id}"
        )
        try:
            info = ClobMarketInfoDto.model_validate(info_payload)
        except ValidationError as exc:
            raise AppError(
                "provider_invalid_response",
                "Polymarket market info payload was malformed",
                502,
            ) from exc
        dto = await self._gamma_market_by_condition(external.condition_id)

        tick_size = _parse_decimal(info.mts) or _parse_decimal(
            dto.orderPriceMinTickSize
        )
        min_order_size = _parse_decimal(info.mos) or _parse_decimal(dto.orderMinSize)
        if tick_size is None or min_order_size is None:
            raise AppError(
                "provider_invalid_response",
                "Polymarket execution metadata was incomplete",
                502,
            )

        fee_rate: Decimal | None = None
        try:
            fee_payload = await self._get_json(
                self._clob, f"/fee-rate/{external.token_ids[0]}"
            )
            fee_dto = FeeRateDto.model_validate(fee_payload)
            if fee_dto.fee_rate_bps is not None:
                fee_rate = Decimal(str(fee_dto.fee_rate_bps)) / Decimal(10000)
            elif fee_dto.rate is not None:
                fee_rate = _parse_decimal(fee_dto.rate)
        except AppError as exc:
            if exc.code != "not_found":
                raise
        if fee_rate is None and info.fd is not None and info.fd.r is not None:
            fee_rate = _parse_decimal(info.fd.r)
        if fee_rate is None and dto.feeSchedule is not None:
            fee_rate = _parse_decimal(dto.feeSchedule.rate)
        if fee_rate is None:
            fee_rate = Decimal("0")

        fee_exponent = Decimal("1")
        if info.fd is not None and info.fd.e is not None:
            fee_exponent = _parse_decimal(info.fd.e) or Decimal("1")
        elif dto.feeSchedule is not None and dto.feeSchedule.exponent is not None:
            fee_exponent = _parse_decimal(dto.feeSchedule.exponent) or Decimal("1")

        taker_only = True
        if info.fd is not None and info.fd.to is not None:
            taker_only = bool(info.fd.to)
        elif dto.feeSchedule is not None and dto.feeSchedule.takerOnly is not None:
            taker_only = bool(dto.feeSchedule.takerOnly)

        return MarketExecutionMetadata(
            market_id=market_id,
            tick_size=tick_size,
            min_order_size=min_order_size,
            fee_rate=fee_rate,
            fee_exponent=fee_exponent,
            taker_only=taker_only,
            maker_base_fee=_parse_decimal(info.mbf) or Decimal("0"),
            taker_base_fee=_parse_decimal(info.tbf) or Decimal("0"),
            sports_delay_seconds=int(dto.secondsDelay or 0),
            game_start_time=_parse_iso(info.gst) or _parse_iso(dto.gameStartTime),
            fetched_at=self._now_fn(),
        )

    async def get_rules(self, market_id: str) -> MarketRules:
        external = await self._external(market_id)
        dto = await self._gamma_market_by_condition(external.condition_id)
        rules_text = (dto.rules or "").strip()
        if not rules_text:
            raise AppError("not_found", "Market rules unavailable", 404)
        source = f"polymarket-{dto.resolvedBy}" if dto.resolvedBy else "polymarket"
        return MarketRules(
            market_id=market_id,
            rules_text=rules_text,
            rules_hash=hashlib.sha256(rules_text.encode("utf-8")).hexdigest(),
            resolution_source=source,
            edge_case_semantics=None,
            fetched_at=self._now_fn(),
        )

    async def get_resolution(self, market_id: str) -> MarketResolution | None:
        external = await self._external(market_id)
        try:
            dto = await self._gamma_market_by_condition(external.condition_id)
        except AppError as exc:
            if exc.code == "not_found":
                return None
            raise
        uma_status = (dto.umaResolutionStatus or "").casefold()
        if uma_status == "resolved":
            prices = dto.outcome_prices()
            if len(prices) != 2:
                raise AppError(
                    "provider_invalid_response",
                    "Polymarket resolution payload was malformed",
                    502,
                )
            payouts_raw = [_parse_decimal(price) for price in prices]
            if any(value is None for value in payouts_raw):
                raise AppError(
                    "provider_invalid_response",
                    "Polymarket resolution payload was malformed",
                    502,
                )
            payouts_values = [value for value in payouts_raw if value is not None]
            if sum(payouts_values) != Decimal("1"):
                raise AppError(
                    "provider_invalid_response",
                    "Polymarket resolution payouts do not sum to one",
                    502,
                )
            player_ids = await self._player_ids_for(external, dto)
            confirmed_at = (
                _parse_iso(dto.closedTime) or _parse_iso(dto.endDate) or self._now_fn()
            )
            return MarketResolution(
                market_id=market_id,
                status=ResolutionStatus.FINAL,
                rules_version=1,
                payouts=(
                    OutcomePayout(
                        player_id=player_ids[0], payout_per_share=payouts_values[0]
                    ),
                    OutcomePayout(
                        player_id=player_ids[1], payout_per_share=payouts_values[1]
                    ),
                ),
                confirmed_at=confirmed_at,
            )
        if uma_status == "disputed":
            status = ResolutionStatus.DISPUTED
        elif uma_status == "proposed":
            status = ResolutionStatus.PROPOSED
        else:
            status = ResolutionStatus.PENDING
        return MarketResolution(
            market_id=market_id,
            status=status,
            rules_version=1,
            payouts=(),
            confirmed_at=None,
        )

    def subscribe_order_books(
        self, market_ids: tuple[str, ...]
    ) -> AsyncIterator[MarketEnvelope]:
        """Public market WebSocket feed; implemented by the T60 realtime task."""
        raise NotImplementedError(
            "market websocket subscription arrives with the T60 realtime pipeline"
        )
        yield  # pragma: no cover - makes this function a generator
