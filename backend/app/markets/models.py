"""Canonical P3 market domain models.

Every model here carries internal IDs only. Provider (Polymarket Gamma/CLOB)
event, condition and token identifiers live exclusively in the private
``MarketExternalId`` mapping model and must never appear in public DTOs,
URLs, chat payloads, UI, screenshots or logs.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import AwareDatetime, Field, model_validator

from app.domain import FrozenModel


class MarketStatus(StrEnum):
    SCHEDULED = "scheduled"
    OPEN = "open"
    CLOSED = "closed"
    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class ResolutionStatus(StrEnum):
    PENDING = "pending"
    PROPOSED = "proposed"
    DISPUTED = "disputed"
    FINAL = "final"


class QuoteSide(StrEnum):
    ENTRY = "entry"
    EXIT = "exit"


class MarketEventKind(StrEnum):
    BOOK = "book"
    PRICE_CHANGE = "price_change"
    TICK_SIZE_CHANGE = "tick_size_change"
    RESOLUTION = "resolution"


class MarketOutcome(FrozenModel):
    """One side of a tennis moneyline market, identified by internal player ID."""

    player_id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class Market(FrozenModel):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    outcomes: tuple[MarketOutcome, MarketOutcome]
    status: MarketStatus
    rules_version: int = Field(ge=1)
    match_id: str | None = None
    event_start: AwareDatetime | None = None
    event_end: AwareDatetime | None = None
    provider: str = Field(min_length=1)
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_outcomes(self) -> "Market":
        first, second = self.outcomes
        if first.player_id == second.player_id:
            raise ValueError("market outcomes must reference two distinct players")
        return self


class MarketListing(FrozenModel):
    """Display-catalog row with supplier labels and optional resolved identity.

    Unlike Market, this model permits unresolved outcomes and doubles. It is
    never sufficient by itself for prediction, decision, or paper workflows.
    """

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    outcome_names: tuple[str, str]
    outcome_player_ids: tuple[str | None, str | None] = (None, None)
    status: MarketStatus
    event_start: AwareDatetime | None = None
    event_end: AwareDatetime | None = None
    provider: str = Field(min_length=1)
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_names(self) -> "MarketListing":
        if any(not name.strip() for name in self.outcome_names):
            raise ValueError("market listing outcome names must not be empty")
        return self

    def to_market(self) -> Market | None:
        first_id, second_id = self.outcome_player_ids
        if not first_id or not second_id or first_id == second_id:
            return None
        return Market(
            id=self.id,
            question=self.question,
            outcomes=(
                MarketOutcome(player_id=first_id, name=self.outcome_names[0]),
                MarketOutcome(player_id=second_id, name=self.outcome_names[1]),
            ),
            status=self.status,
            rules_version=1,
            match_id=None,
            event_start=self.event_start,
            event_end=self.event_end,
            provider=self.provider,
            observed_at=self.observed_at,
        )


class MarketListingScan(FrozenModel):
    """One complete or fail-closed Gamma catalog scan."""

    listings: tuple[MarketListing, ...]
    complete: bool


class MarketExternalId(FrozenModel):
    """PRIVATE adapter/identity-persistence mapping. Never a public DTO."""

    market_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    provider_event_id: str = Field(min_length=1)
    condition_id: str = Field(min_length=1)
    token_ids: tuple[str, str]


class MarketRules(FrozenModel):
    """Minimal audit snapshot of the market's resolution rules."""

    market_id: str = Field(min_length=1)
    rules_text: str = Field(min_length=1)
    rules_hash: str = Field(min_length=1)
    resolution_source: str = Field(min_length=1)
    edge_case_semantics: str | None = None
    fetched_at: AwareDatetime


class BookLevel(FrozenModel):
    price: Decimal = Field(gt=Decimal("0"), le=Decimal("1"))
    size: Decimal = Field(gt=Decimal("0"))


class OutcomeBook(FrozenModel):
    """Bids/asks for one outcome token. Bids strictly descending, asks strictly
    ascending, no duplicate price levels."""

    outcome_player_id: str = Field(min_length=1)
    bids: tuple[BookLevel, ...] = ()
    asks: tuple[BookLevel, ...] = ()

    @model_validator(mode="after")
    def validate_level_ordering(self) -> "OutcomeBook":
        for current, following in zip(self.bids, self.bids[1:], strict=False):
            if current.price <= following.price:
                raise ValueError("bids must be strictly descending without duplicates")
        for current, following in zip(self.asks, self.asks[1:], strict=False):
            if current.price >= following.price:
                raise ValueError("asks must be strictly ascending without duplicates")
        return self


class OrderBookState(FrozenModel):
    """Canonical book state for both independent outcome sides of one market."""

    market_id: str = Field(min_length=1)
    books: tuple[OutcomeBook, OutcomeBook]
    sequence: int = Field(ge=0)
    book_hash: str = Field(min_length=1)
    provider_timestamp: AwareDatetime
    received_at: AwareDatetime
    is_stale: bool = False

    @model_validator(mode="after")
    def validate_distinct_sides(self) -> "OrderBookState":
        first, second = self.books
        if first.outcome_player_id == second.outcome_player_id:
            raise ValueError("order book must cover two distinct outcome players")
        return self


class ExecutableQuote(FrozenModel):
    """Level-by-level executable quote for the fixed stake (or full position)."""

    market_id: str = Field(min_length=1)
    outcome_player_id: str = Field(min_length=1)
    side: QuoteSide
    stake: Decimal = Field(gt=Decimal("0"))
    shares: Decimal = Field(gt=Decimal("0"))
    average_price: Decimal = Field(gt=Decimal("0"), le=Decimal("1"))
    fee: Decimal = Field(ge=Decimal("0"))
    slippage: Decimal = Field(ge=Decimal("0"))
    is_fillable: bool
    book_hash: str = Field(min_length=1)
    book_sequence: int = Field(ge=0)
    quoted_at: AwareDatetime


class OutcomePayout(FrozenModel):
    player_id: str = Field(min_length=1)
    payout_per_share: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))


class MarketExecutionMetadata(FrozenModel):
    """Dynamic per-market execution parameters read from provider metadata.

    Tick size, minimum order size, fee curve and sports delay are never
    hardcoded; quotes and FOK simulation must consume this record.
    """

    market_id: str = Field(min_length=1)
    tick_size: Decimal = Field(gt=Decimal("0"), le=Decimal("1"))
    min_order_size: Decimal = Field(ge=Decimal("0"))
    fee_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    fee_exponent: Decimal = Field(ge=Decimal("0"))
    taker_only: bool = True
    maker_base_fee: Decimal = Field(ge=Decimal("0"))
    taker_base_fee: Decimal = Field(ge=Decimal("0"))
    sports_delay_seconds: int = Field(ge=0)
    game_start_time: AwareDatetime | None = None
    fetched_at: AwareDatetime


class MarketResolution(FrozenModel):
    """Provider-final resolution. Paper settlement only obeys this record."""

    market_id: str = Field(min_length=1)
    status: ResolutionStatus
    rules_version: int = Field(ge=1)
    payouts: tuple[OutcomePayout, ...] = ()
    confirmed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_final_resolution(self) -> "MarketResolution":
        if self.status is not ResolutionStatus.FINAL:
            return self
        if self.confirmed_at is None:
            raise ValueError("final resolution requires confirmed_at")
        if len(self.payouts) != 2:
            raise ValueError("final resolution requires payouts for both outcomes")
        first, second = self.payouts
        if first.player_id == second.player_id:
            raise ValueError("final resolution payouts must cover distinct players")
        if first.payout_per_share + second.payout_per_share != Decimal("1"):
            raise ValueError("final resolution payouts per share must sum to exactly 1")
        return self


class MarketEnvelope(FrozenModel):
    """Typed inbound market event delivered by the provider feed."""

    market_id: str = Field(min_length=1)
    kind: MarketEventKind
    received_at: AwareDatetime
    book: OrderBookState | None = None
    tick_size: Decimal | None = None
    resolution: MarketResolution | None = None

    @model_validator(mode="after")
    def validate_payload_matches_kind(self) -> "MarketEnvelope":
        if self.kind in (MarketEventKind.BOOK, MarketEventKind.PRICE_CHANGE):
            if self.book is None:
                raise ValueError(f"{self.kind.value} envelope requires book payload")
            if self.resolution is not None or self.tick_size is not None:
                raise ValueError(f"{self.kind.value} envelope carries wrong payload")
        elif self.kind is MarketEventKind.TICK_SIZE_CHANGE:
            if self.tick_size is None:
                raise ValueError("tick_size_change envelope requires tick_size payload")
            if self.book is not None or self.resolution is not None:
                raise ValueError("tick_size_change envelope carries wrong payload")
        elif self.kind is MarketEventKind.RESOLUTION:
            if self.resolution is None:
                raise ValueError("resolution envelope requires resolution payload")
            if self.book is not None or self.tick_size is not None:
                raise ValueError("resolution envelope carries wrong payload")
        return self
