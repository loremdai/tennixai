"""Permissive Polymarket vendor DTOs (Gamma + CLOB).

These models mirror the public wire format and tolerate unknown fields. They
are imported ONLY by the Polymarket adapter; provider event, condition and
token identifiers never leave the adapter/identity-persistence boundary.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VendorModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class GammaFeeScheduleDto(VendorModel):
    rate: float | None = None
    exponent: float | None = None
    takerOnly: bool | None = None  # noqa: N815 - vendor wire name
    rebateRate: float | None = None  # noqa: N815 - vendor wire name


class GammaTagDto(VendorModel):
    id: str | int | None = None
    slug: str | None = None
    label: str | None = None


class GammaMarketDto(VendorModel):
    """One Gamma market. `outcomes`, `outcomePrices` and `clobTokenIds` may
    arrive as stringified JSON arrays; the validator normalizes both shapes."""

    id: str | int | None = None
    question: str | None = None
    conditionId: str | None = None  # noqa: N815 - vendor wire name
    slug: str | None = None
    outcomes: Any = None
    outcomePrices: Any = None  # noqa: N815 - vendor wire name
    clobTokenIds: Any = None  # noqa: N815 - vendor wire name
    active: bool | None = None
    closed: bool | None = None
    closedTime: str | None = None  # noqa: N815 - vendor wire name
    acceptingOrders: bool | None = None  # noqa: N815 - vendor wire name
    sportsMarketType: str | None = None  # noqa: N815 - vendor wire name
    gameStartTime: str | None = None  # noqa: N815 - vendor wire name
    startDate: str | None = None  # noqa: N815 - vendor wire name
    endDate: str | None = None  # noqa: N815 - vendor wire name
    secondsDelay: int | None = None  # noqa: N815 - vendor wire name
    orderPriceMinTickSize: float | None = None  # noqa: N815 - vendor wire name
    orderMinSize: float | None = None  # noqa: N815 - vendor wire name
    makerBaseFee: float | None = None  # noqa: N815 - vendor wire name
    takerBaseFee: float | None = None  # noqa: N815 - vendor wire name
    feesEnabled: bool | None = None  # noqa: N815 - vendor wire name
    feeSchedule: GammaFeeScheduleDto | None = None  # noqa: N815 - vendor wire name
    umaResolutionStatus: str | None = None  # noqa: N815 - vendor wire name
    automaticallyResolved: bool | None = None  # noqa: N815 - vendor wire name
    negRisk: bool | None = None  # noqa: N815 - vendor wire name
    enableOrderBook: bool | None = None  # noqa: N815 - vendor wire name
    rules: str | None = None
    resolvedBy: str | None = None  # noqa: N815 - vendor wire name

    @field_validator("outcomes", "outcomePrices", "clobTokenIds", mode="before")
    @classmethod
    def parse_stringified_list(cls, value: Any) -> Any:
        if isinstance(value, str):
            import json

            try:
                parsed = json.loads(value)
            except ValueError:
                return None
            return parsed if isinstance(parsed, list) else None
        return value

    def outcome_names(self) -> tuple[str, ...]:
        values = self.outcomes if isinstance(self.outcomes, list) else []
        return tuple(str(value) for value in values)

    def outcome_prices(self) -> tuple[str, ...]:
        values = self.outcomePrices if isinstance(self.outcomePrices, list) else []
        return tuple(str(value) for value in values)

    def token_ids(self) -> tuple[str, ...]:
        values = self.clobTokenIds if isinstance(self.clobTokenIds, list) else []
        return tuple(str(value) for value in values)


class GammaEventDto(VendorModel):
    id: str | int | None = None
    slug: str | None = None
    title: str | None = None
    startDate: str | None = None  # noqa: N815 - vendor wire name
    endDate: str | None = None  # noqa: N815 - vendor wire name
    active: bool | None = None
    closed: bool | None = None
    tags: list[GammaTagDto] = Field(default_factory=list)
    markets: list[GammaMarketDto] = Field(default_factory=list)


class GammaEventsKeysetPageDto(VendorModel):
    events: list[GammaEventDto]
    next_cursor: str | None = None


class ClobFeeDetailsDto(VendorModel):
    """CLOB V2 compact fee details: rate, exponent, takerOnly."""

    r: float | None = None
    e: float | None = None
    to: bool | None = None


class ClobTokenDto(VendorModel):
    """CLOB V2 compact token entry: tokenID, outcome."""

    t: str | None = None
    o: str | None = None


class ClobMarketInfoDto(VendorModel):
    """CLOB V2 compact market info (post 2026-04-28 migration)."""

    gst: str | None = None
    t: list[ClobTokenDto] = Field(default_factory=list)
    mos: float | None = None
    mts: float | None = None
    mbf: float | None = None
    tbf: float | None = None
    rfqe: bool | None = None
    itode: bool | None = None
    ibce: bool | None = None
    fd: ClobFeeDetailsDto | None = None
    oas: float | None = None


class BookLevelDto(VendorModel):
    price: str | float | None = None
    size: str | float | None = None


class BookDto(VendorModel):
    """CLOB `GET /book?token_id=` snapshot. Vendor ordering is bids ascending
    / asks descending; the adapter normalizes to canonical order."""

    market: str | None = None
    asset_id: str | None = None
    timestamp: str | int | None = None
    hash: str | None = None
    bids: list[BookLevelDto] = Field(default_factory=list)
    asks: list[BookLevelDto] = Field(default_factory=list)


class FeeRateDto(VendorModel):
    """Optional dynamic fee-rate lookup; permissive because the endpoint may
    be absent, in which case the adapter falls back to the fee schedule."""

    fee_rate_bps: float | int | None = None
    rate: float | None = None
    takerOnly: bool | None = None  # noqa: N815 - vendor wire name
