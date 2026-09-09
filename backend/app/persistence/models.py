"""P2 PostgreSQL schema (spec §7).

Canonical observations are long-lived; raw provider payloads are purged after
the configured retention window. Vendor payloads only ever land in
`raw_provider_events.payload`; canonical tables store internal IDs and
canonical domain shapes.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PlayerRow(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(String(8))
    ranking: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


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
