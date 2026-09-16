"""P2 PostgreSQL schema (spec §7).

Canonical observations are long-lived; raw provider payloads are purged after
the configured retention window. Vendor payloads only ever land in
`raw_provider_events.payload`; canonical tables store internal IDs and
canonical domain shapes.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PlayerRow(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    localized_name: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(String(8))
    ranking: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    birth_date: Mapped[date | None] = mapped_column(Date)
    image_url: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PlayerAliasRow(Base):
    """Display/lookup aliases per player. The same normalized alias may point
    at several players; ambiguity is data, never a uniqueness conflict."""

    __tablename__ = "player_aliases"
    __table_args__ = (
        UniqueConstraint("player_id", "locale", "normalized_alias", "kind"),
        Index("ix_player_aliases_normalized_alias", "normalized_alias"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(
        ForeignKey("players.id"), nullable=False, index=True
    )
    locale: Mapped[str] = mapped_column(String(16), nullable=False)
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_alias: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(191))
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PlayerRankingRow(Base):
    """Bounded ranking snapshots per tour and ranking date."""

    __tablename__ = "player_rankings"
    __table_args__ = (
        UniqueConstraint("tour", "ranking_date", "rank"),
        UniqueConstraint("tour", "ranking_date", "player_id"),
        Index("ix_player_rankings_lookup", "tour", "ranking_date", "rank"),
        Index("ix_player_rankings_player", "player_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(
        ForeignKey("players.id"), nullable=False, index=True
    )
    tour: Mapped[str] = mapped_column(String(8), nullable=False)
    ranking_date: Mapped[date] = mapped_column(Date, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    movement: Mapped[str] = mapped_column(String(16), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TournamentRow(Base):
    __tablename__ = "tournaments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    tour: Mapped[str | None] = mapped_column(String(32))
    circuit: Mapped[str] = mapped_column(String(16), nullable=False, default="other")
    gender: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    discipline: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MatchRow(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str | None] = mapped_column(String(16))
    player1_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"))
    player2_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"))
    tournament_id: Mapped[str | None] = mapped_column(ForeignKey("tournaments.id"))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    round: Mapped[str | None] = mapped_column(Text)
    surface: Mapped[str | None] = mapped_column(String(32))
    indoor: Mapped[bool | None] = mapped_column(Boolean)
    format: Mapped[str | None] = mapped_column(String(16))
    winner_player_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PlayerExternalIdRow(Base):
    __tablename__ = "player_external_ids"
    __table_args__ = (
        UniqueConstraint("provider", "external_id"),
        UniqueConstraint("internal_id", "provider"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    internal_id: Mapped[str] = mapped_column(
        ForeignKey("players.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(191), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TournamentExternalIdRow(Base):
    __tablename__ = "tournament_external_ids"
    __table_args__ = (
        UniqueConstraint("provider", "external_id"),
        UniqueConstraint("internal_id", "provider"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    internal_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(191), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MatchExternalIdRow(Base):
    __tablename__ = "match_external_ids"
    __table_args__ = (
        UniqueConstraint("provider", "external_id"),
        UniqueConstraint("internal_id", "provider"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    internal_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(191), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MatchStateSnapshotRow(Base):
    """Current canonical live state per match; history lives in observations."""

    __tablename__ = "match_state_snapshots"

    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id"), primary_key=True
    )
    state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    connection_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unavailable"
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quality: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PointEventRow(Base):
    __tablename__ = "point_events"
    __table_args__ = (UniqueConstraint("match_id", "sequence"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    game_number: Mapped[int] = mapped_column(Integer, nullable=False)
    point_number: Mapped[int] = mapped_column(Integer, nullable=False)
    server_player_id: Mapped[str | None] = mapped_column(String(64))
    winner_player_id: Mapped[str | None] = mapped_column(String(64))
    score_before: Mapped[dict | None] = mapped_column(JSONB)
    score_after: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_break_point: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_set_point: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_match_point: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    quality: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PointEventRevisionRow(Base):
    """Append-only correction history for points."""

    __tablename__ = "point_event_revisions"
    __table_args__ = (UniqueConstraint("point_event_id", "revision"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    point_event_id: Mapped[str] = mapped_column(
        ForeignKey("point_events.id"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    before_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    after_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    revised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(64))


class MatchStatisticRow(Base):
    __tablename__ = "match_statistics"
    __table_args__ = (UniqueConstraint("match_id", "name", "period"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(48), nullable=False)
    period: Mapped[str] = mapped_column(String(24), nullable=False, default="match")
    player1_value: Mapped[float | None] = mapped_column(Float)
    player2_value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(24))
    provenance: Mapped[str] = mapped_column(String(24), nullable=False, default="provider")
    availability: Mapped[str] = mapped_column(String(16), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StatisticObservationRow(Base):
    """Append-only statistic change log; written only when a value changes."""

    __tablename__ = "statistic_observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(48), nullable=False)
    period: Mapped[str] = mapped_column(String(24), nullable=False, default="match")
    player1_value: Mapped[float | None] = mapped_column(Float)
    player2_value: Mapped[float | None] = mapped_column(Float)
    availability: Mapped[str] = mapped_column(String(16), nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MomentumObservationRow(Base):
    __tablename__ = "momentum_observations"
    __table_args__ = (
        UniqueConstraint("match_id", "algorithm_version", "point_sequence"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id"), nullable=False, index=True
    )
    point_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    leader_player_id: Mapped[str | None] = mapped_column(String(64))
    is_provisional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")


class RawProviderEventRow(Base):
    """Diagnostic payloads; purged after the retention window. `match_id` has
    no FK because events may arrive before identity mapping exists."""

    __tablename__ = "raw_provider_events"
    __table_args__ = (
        Index("ix_raw_provider_events_external_match_id", "external_match_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[str | None] = mapped_column(String(64))
    external_match_id: Mapped[str | None] = mapped_column(String(191))
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


# ---------------------------------------------------------------------------
# P3 market, prediction evidence and paper ledger rows (spec §4, T58).
# Provider identifiers live only in `market_external_ids`; every public row
# stores internal IDs. Rules used by intents and all ledger rows are long-lived
# canonical evidence and are never touched by raw-payload retention cleanup.
# ---------------------------------------------------------------------------


class MarketRow(Base):
    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    question: Mapped[str | None] = mapped_column(Text)
    outcome_a_player_id: Mapped[str | None] = mapped_column(String(64))
    outcome_a_name: Mapped[str | None] = mapped_column(Text)
    outcome_b_player_id: Mapped[str | None] = mapped_column(String(64))
    outcome_b_name: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown", server_default="unknown"
    )
    rules_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    match_id: Mapped[str | None] = mapped_column(String(64))
    event_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="polymarket", server_default="polymarket"
    )
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MarketExternalIdRow(Base):
    """PRIVATE provider identity mapping. Never exposed in public DTOs."""

    __tablename__ = "market_external_ids"
    __table_args__ = (
        UniqueConstraint("market_id"),
        UniqueConstraint("provider", "condition_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(
        ForeignKey("markets.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(191), nullable=False)
    condition_id: Mapped[str] = mapped_column(String(191), nullable=False)
    token_a_id: Mapped[str] = mapped_column(String(191), nullable=False)
    token_b_id: Mapped[str] = mapped_column(String(191), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MarketRuleRow(Base):
    """Immutable per-version rules audit snapshot; evidence for decisions."""

    __tablename__ = "market_rules"
    __table_args__ = (
        UniqueConstraint("market_id", "version"),
        UniqueConstraint("market_id", "rules_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(
        ForeignKey("markets.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_text: Mapped[str] = mapped_column(Text, nullable=False)
    rules_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    resolution_source: Mapped[str] = mapped_column(String(64), nullable=False)
    edge_case_semantics: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketMatchLinkRow(Base):
    """Exact market-to-match link. One row per market; exactly one `active`
    link per match (partial unique index). Frozen once an intent exists."""

    __tablename__ = "market_match_links"
    __table_args__ = (
        UniqueConstraint("market_id"),
        Index(
            "ix_market_match_links_active_match",
            "match_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(
        ForeignKey("markets.id"), nullable=False, index=True
    )
    match_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketObservationRow(Base):
    """Append-only decision-relevant market observations and bounded samples."""

    __tablename__ = "market_observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(
        ForeignKey("markets.id"), nullable=False, index=True
    )
    match_id: Mapped[str | None] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PredictionSnapshotRow(Base):
    """Versioned prediction evidence; idempotent per input state version."""

    __tablename__ = "prediction_snapshots"
    __table_args__ = (
        UniqueConstraint("match_id", "model_version", "input_state_version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id"), nullable=False, index=True
    )
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    calibration_version: Mapped[str] = mapped_column(String(64), nullable=False)
    data_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    availability: Mapped[str] = mapped_column(String(16), nullable=False)
    abstain_reason: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DecisionObservationRow(Base):
    """Versioned decision evidence; one row per decision stream version."""

    __tablename__ = "decision_observations"
    __table_args__ = (UniqueConstraint("match_id", "observation_version"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id"), nullable=False, index=True
    )
    market_id: Mapped[str] = mapped_column(
        ForeignKey("markets.id"), nullable=False, index=True
    )
    observation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_gap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    as_of: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class PaperOrderIntentRow(Base):
    """One-shot FOK intent. Unique idempotency key plus one entry and one
    exit intent per match."""

    __tablename__ = "paper_order_intents"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        UniqueConstraint("match_id", "side"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id"), nullable=False, index=True
    )
    market_id: Mapped[str] = mapped_column(
        ForeignKey("markets.id"), nullable=False, index=True
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    idempotency_key: Mapped[str] = mapped_column(String(191), nullable=False)
    outcome_player_id: Mapped[str] = mapped_column(String(64), nullable=False)
    stake: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rules_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    quote: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    no_fill_reason: Mapped[str | None] = mapped_column(String(64))


class PaperFillRow(Base):
    """Exactly one FOK fill/no-fill record per intent."""

    __tablename__ = "paper_fills"
    __table_args__ = (UniqueConstraint("intent_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    intent_id: Mapped[str] = mapped_column(
        ForeignKey("paper_order_intents.id"), nullable=False, index=True
    )
    filled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    shares: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    average_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    reason: Mapped[str | None] = mapped_column(String(64))
    executed_book_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaperPositionRow(Base):
    """The single main paper position per match."""

    __tablename__ = "paper_positions"
    __table_args__ = (UniqueConstraint("match_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id"), nullable=False, index=True
    )
    market_id: Mapped[str] = mapped_column(
        ForeignKey("markets.id"), nullable=False, index=True
    )
    outcome_player_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_cost: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    shares: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open", server_default="open"
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaperTrackResultRow(Base):
    """EV main track or counterfactual track result; one row per track."""

    __tablename__ = "paper_track_results"
    __table_args__ = (UniqueConstraint("position_id", "track"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id"), nullable=False, index=True
    )
    position_id: Mapped[str] = mapped_column(
        ForeignKey("paper_positions.id"), nullable=False, index=True
    )
    track: Mapped[str] = mapped_column(String(24), nullable=False)
    exit_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    shares: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    exit_average_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    payout_per_share: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    gross_payout: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    net_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketResolutionRow(Base):
    """Current provider resolution state per market; FINAL is terminal."""

    __tablename__ = "market_resolutions"

    market_id: Mapped[str] = mapped_column(
        ForeignKey("markets.id"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    rules_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payouts: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
