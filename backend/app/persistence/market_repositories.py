"""P3 market-side repositories (T58).

Narrow, explicit row access for market identity, private provider mapping,
immutable rules evidence, exact match links and versioned prediction/decision
observations. Provider identifiers are written only to
``market_external_ids``; canonical reads return internal-ID domain models.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.decision.models import DecisionObservation
from app.markets.models import (
    Market,
    MarketExternalId,
    MarketOutcome,
    MarketRules,
    MarketStatus,
    OutcomeBook,
)
from app.markets.quotes import (
    QuoteSnapshotRecord,
    QuoteSource,
    QuoteState,
    decide_quote_write,
)
from app.persistence.database import Database
from app.persistence.models import (
    DecisionObservationRow,
    MarketExternalIdRow,
    MarketMatchLinkRow,
    MarketObservationRow,
    MarketQuoteSnapshotRow,
    MarketRow,
    MarketRuleRow,
    PaperOrderIntentRow,
    PredictionSnapshotRow,
)
from app.prediction.models import PredictionSnapshot


class LinkFrozenError(Exception):
    """Raised when a market/match link would change after an intent exists."""


@dataclass(frozen=True)
class MarketOverviewRow:
    """One market joined to its ACTIVE match link (T84).

    `active_match_id` comes exclusively from `market_match_links` with
    `status='active'`; the legacy `markets.match_id` column is historical
    compatibility only and is never read as market→match truth. The row
    carries internal IDs only.
    """

    market_id: str
    question: str | None
    status: str
    rules_version: int
    observed_at: datetime | None
    event_start: datetime | None
    updated_at: datetime
    outcome_a_player_id: str | None
    outcome_a_name: str | None
    outcome_b_player_id: str | None
    outcome_b_name: str | None
    active_match_id: str | None
    link_evidence_available: bool


def _parse_observed_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


class MarketRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_or_create_market_id(
        self,
        *,
        provider: str,
        provider_event_id: str,
        condition_id: str,
        token_ids: tuple[str, str] | None = None,
    ) -> str:
        """Concurrent creators converge on one internal `mkt_` id via
        insert-on-conflict plus a read retry (same pattern as P2 identity)."""
        token_a, token_b = token_ids or ("", "")
        for attempt in range(3):
            async with self._database.session() as session:
                try:
                    async with session.begin():
                        existing = await session.scalar(
                            select(MarketExternalIdRow.market_id).where(
                                MarketExternalIdRow.provider == provider,
                                MarketExternalIdRow.condition_id == condition_id,
                            )
                        )
                        if existing is not None:
                            return existing
                        internal_id = f"mkt_{uuid4().hex}"
                        session.add(MarketRow(id=internal_id, provider=provider))
                        # Flush first: no ORM relationship orders the mapping
                        # insert after its FK target automatically.
                        await session.flush()
                        session.add(
                            MarketExternalIdRow(
                                market_id=internal_id,
                                provider=provider,
                                provider_event_id=provider_event_id,
                                condition_id=condition_id,
                                token_a_id=token_a,
                                token_b_id=token_b,
                            )
                        )
                    return internal_id
                except IntegrityError:
                    if attempt == 2:
                        raise
                    # A concurrent creator won the race; loop and read its ID.
        raise AssertionError("unreachable")  # pragma: no cover

    async def save_external_id(self, mapping: MarketExternalId) -> None:
        """Upsert the private mapping (tokens may become known later)."""
        token_a, token_b = mapping.token_ids
        statement = pg_insert(MarketExternalIdRow).values(
            market_id=mapping.market_id,
            provider=mapping.provider,
            provider_event_id=mapping.provider_event_id,
            condition_id=mapping.condition_id,
            token_a_id=token_a,
            token_b_id=token_b,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["provider", "condition_id"],
            set_={
                "market_id": statement.excluded.market_id,
                "provider_event_id": statement.excluded.provider_event_id,
                "token_a_id": statement.excluded.token_a_id,
                "token_b_id": statement.excluded.token_b_id,
            },
        )
        async with self._database.session() as session:
            async with session.begin():
                await session.execute(statement)

    async def get_external_id(self, market_id: str) -> MarketExternalId | None:
        async with self._database.session() as session:
            row = await session.scalar(
                select(MarketExternalIdRow).where(
                    MarketExternalIdRow.market_id == market_id
                )
            )
        if row is None:
            return None
        return MarketExternalId(
            market_id=row.market_id,
            provider=row.provider,
            provider_event_id=row.provider_event_id,
            condition_id=row.condition_id,
            token_ids=(row.token_a_id, row.token_b_id),
        )

    async def list_external_ids(
        self, market_ids: Sequence[str]
    ) -> dict[str, MarketExternalId]:
        """PRIVATE mapping for many markets in ONE query (no per-row reads).

        The returned model carries provider identity; callers must keep it
        inside the adapter/runtime boundary.
        """
        ids = {market_id for market_id in market_ids if market_id}
        if not ids:
            return {}
        async with self._database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(MarketExternalIdRow).where(
                            MarketExternalIdRow.market_id.in_(ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
        return {
            row.market_id: MarketExternalId(
                market_id=row.market_id,
                provider=row.provider,
                provider_event_id=row.provider_event_id,
                condition_id=row.condition_id,
                token_ids=(row.token_a_id, row.token_b_id),
            )
            for row in rows
        }

    async def save_market(self, market: Market) -> None:
        first, second = market.outcomes
        values: dict[str, Any] = {
            "id": market.id,
            "question": market.question,
            "outcome_a_player_id": first.player_id,
            "outcome_a_name": first.name,
            "outcome_b_player_id": second.player_id,
            "outcome_b_name": second.name,
            "status": market.status.value,
            "rules_version": market.rules_version,
            "match_id": market.match_id,
            "event_start": market.event_start,
            "event_end": market.event_end,
            "provider": market.provider,
            "observed_at": market.observed_at,
            "updated_at": datetime.now(UTC),
        }
        statement = pg_insert(MarketRow).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=["id"],
            set_={key: statement.excluded[key] for key in values if key != "id"},
        )
        async with self._database.session() as session:
            async with session.begin():
                await session.execute(statement)

    async def get_market(self, market_id: str) -> Market | None:
        async with self._database.session() as session:
            row = await session.get(MarketRow, market_id)
        if row is None or row.question is None:
            return None
        return Market(
            id=row.id,
            question=row.question,
            outcomes=(
                MarketOutcome(
                    player_id=row.outcome_a_player_id or "",
                    name=row.outcome_a_name or "",
                ),
                MarketOutcome(
                    player_id=row.outcome_b_player_id or "",
                    name=row.outcome_b_name or "",
                ),
            ),
            status=MarketStatus(row.status),
            rules_version=row.rules_version,
            match_id=row.match_id,
            event_start=row.event_start,
            event_end=row.event_end,
            provider=row.provider,
            observed_at=row.observed_at or row.updated_at,
        )

    async def save_rules(self, rules: MarketRules) -> int:
        """Store an immutable rules snapshot; returns its per-market version.
        Re-saving the same hash is idempotent."""
        async with self._database.session() as session:
            async with session.begin():
                existing = await session.scalar(
                    select(MarketRuleRow.version).where(
                        MarketRuleRow.market_id == rules.market_id,
                        MarketRuleRow.rules_hash == rules.rules_hash,
                    )
                )
                if existing is not None:
                    return int(existing)
                next_version = (
                    await session.scalar(
                        select(func.coalesce(func.max(MarketRuleRow.version), 0)).where(
                            MarketRuleRow.market_id == rules.market_id
                        )
                    )
                    or 0
                ) + 1
                session.add(
                    MarketRuleRow(
                        market_id=rules.market_id,
                        version=next_version,
                        rules_text=rules.rules_text,
                        rules_hash=rules.rules_hash,
                        resolution_source=rules.resolution_source,
                        edge_case_semantics=rules.edge_case_semantics,
                        fetched_at=rules.fetched_at,
                    )
                )
                await session.execute(
                    update(MarketRow)
                    .where(MarketRow.id == rules.market_id)
                    .values(rules_version=next_version, updated_at=datetime.now(UTC))
                )
                return next_version

    async def get_current_rules(self, market_id: str) -> tuple[MarketRules, int] | None:
        async with self._database.session() as session:
            row = await session.scalar(
                select(MarketRuleRow)
                .where(MarketRuleRow.market_id == market_id)
                .order_by(MarketRuleRow.version.desc())
                .limit(1)
            )
        if row is None:
            return None
        return (
            MarketRules(
                market_id=row.market_id,
                rules_text=row.rules_text,
                rules_hash=row.rules_hash,
                resolution_source=row.resolution_source,
                edge_case_semantics=row.edge_case_semantics,
                fetched_at=row.fetched_at,
            ),
            row.version,
        )

    async def link_match(
        self, *, market_id: str, match_id: str, evidence: dict[str, Any]
    ) -> None:
        """Create or replace the exact market-to-match link.

        Exactly one `active` link per match (partial unique index) and one row
        per market. Once any paper intent references the match or the market,
        the relationship is frozen: identical re-links are a no-op and any
        change raises ``LinkFrozenError``.
        """
        now = datetime.now(UTC)
        async with self._database.session() as session:
            async with session.begin():
                current = await session.scalar(
                    select(MarketMatchLinkRow).where(
                        MarketMatchLinkRow.market_id == market_id
                    )
                )
                if (
                    current is not None
                    and current.match_id == match_id
                    and current.status == "active"
                ):
                    return
                frozen = await session.scalar(
                    select(func.count())
                    .select_from(PaperOrderIntentRow)
                    .where(
                        (PaperOrderIntentRow.match_id == match_id)
                        | (PaperOrderIntentRow.market_id == market_id)
                    )
                )
                if frozen:
                    raise LinkFrozenError(
                        "market/match link is frozen after intent creation"
                    )
                await session.execute(
                    update(MarketMatchLinkRow)
                    .where(
                        MarketMatchLinkRow.match_id == match_id,
                        MarketMatchLinkRow.status == "active",
                        MarketMatchLinkRow.market_id != market_id,
                    )
                    .values(status="replaced")
                )
                statement = pg_insert(MarketMatchLinkRow).values(
                    market_id=market_id,
                    match_id=match_id,
                    status="active",
                    evidence=evidence,
                    linked_at=now,
                )
                statement = statement.on_conflict_do_update(
                    index_elements=["market_id"],
                    set_={
                        "match_id": statement.excluded.match_id,
                        "status": "active",
                        "evidence": statement.excluded.evidence,
                        "linked_at": statement.excluded.linked_at,
                    },
                )
                await session.execute(statement)

    async def active_link_for_match(self, match_id: str) -> MarketMatchLinkRow | None:
        async with self._database.session() as session:
            return await session.scalar(
                select(MarketMatchLinkRow).where(
                    MarketMatchLinkRow.match_id == match_id,
                    MarketMatchLinkRow.status == "active",
                )
            )

    async def save_observation(
        self,
        *,
        market_id: str,
        match_id: str | None,
        kind: str,
        payload: dict[str, Any],
        observed_at: datetime,
    ) -> int:
        """Append-only decision-relevant observation / bounded sample."""
        row = MarketObservationRow(
            market_id=market_id,
            match_id=match_id,
            kind=kind,
            payload=payload,
            observed_at=observed_at,
        )
        async with self._database.session() as session:
            async with session.begin():
                session.add(row)
                await session.flush()
        return int(row.id)

    async def save_observations(self, batch: Sequence[dict[str, Any]]) -> None:
        """Bulk append pre-shaped observation entries from the market worker.

        Each entry: market_id, match_id, kind, payload, observed_at (ISO).
        """
        if not batch:
            return
        rows = [
            MarketObservationRow(
                market_id=entry["market_id"],
                match_id=entry.get("match_id"),
                kind=entry["kind"],
                payload=entry.get("payload", {}),
                observed_at=_parse_observed_at(entry["observed_at"]),
            )
            for entry in batch
        ]
        async with self._database.session() as session:
            async with session.begin():
                session.add_all(rows)

    async def record_tracking_gap(
        self,
        *,
        market_id: str,
        match_id: str | None,
        reason: str,
        started_at: datetime,
        ended_at: datetime,
    ) -> int:
        """Explicit offline/gap interval. Never backfills signals or fills."""
        return await self.save_observation(
            market_id=market_id,
            match_id=match_id,
            kind="tracking_gap",
            payload={
                "reason": reason,
                "started_at": started_at.isoformat(),
                "ended_at": ended_at.isoformat(),
            },
            observed_at=ended_at,
        )

    async def list_active_links(self) -> list[MarketMatchLinkRow]:
        async with self._database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(MarketMatchLinkRow).where(
                            MarketMatchLinkRow.status == "active"
                        )
                    )
                )
                .scalars()
                .all()
            )
        return list(rows)

    async def save_prediction(self, snapshot: PredictionSnapshot) -> None:
        """Idempotent per (match, model, input state version); evidence is
        immutable once written."""
        statement = pg_insert(PredictionSnapshotRow).values(
            match_id=snapshot.match_id,
            model_version=snapshot.model_version,
            calibration_version=snapshot.calibration_version,
            data_version=snapshot.data_version,
            input_state_version=snapshot.input_state_version,
            availability=snapshot.availability.value,
            abstain_reason=snapshot.abstain_reason,
            payload=snapshot.model_dump(mode="json"),
            as_of=snapshot.as_of,
        )
        statement = statement.on_conflict_do_nothing(
            index_elements=["match_id", "model_version", "input_state_version"]
        )
        async with self._database.session() as session:
            async with session.begin():
                await session.execute(statement)

    async def save_decision_observation(self, observation: DecisionObservation) -> None:
        """Idempotent per decision-stream version; first write wins."""
        statement = pg_insert(DecisionObservationRow).values(
            match_id=observation.match_id,
            market_id=observation.market_id,
            observation_version=observation.observation_version,
            action=observation.action.value,
            is_stale=observation.is_stale,
            has_gap=observation.has_gap,
            payload=observation.model_dump(mode="json"),
            as_of=observation.as_of,
        )
        statement = statement.on_conflict_do_nothing(
            index_elements=["match_id", "observation_version"]
        )
        async with self._database.session() as session:
            async with session.begin():
                await session.execute(statement)

    async def latest_decision_observation(
        self, match_id: str
    ) -> DecisionObservation | None:
        async with self._database.session() as session:
            row = await session.scalar(
                select(DecisionObservationRow)
                .where(DecisionObservationRow.match_id == match_id)
                .order_by(DecisionObservationRow.observation_version.desc())
                .limit(1)
            )
        if row is None:
            return None
        return DecisionObservation.model_validate(row.payload)

    async def latest_observation_version(self, match_id: str) -> int:
        """Durable decision-stream cursor for restart recovery."""
        async with self._database.session() as session:
            version = await session.scalar(
                select(func.max(DecisionObservationRow.observation_version)).where(
                    DecisionObservationRow.match_id == match_id
                )
            )
        return int(version or 0)

    # -- read-only query paths for the P3 API layer (T66) -------------------

    async def list_market_overviews(self) -> list[MarketOverviewRow]:
        """Every known market with its ACTIVE match link, most recent first.

        ONE query: `market_match_links` is joined on `status='active'` as
        part of the join condition, so replaced/inactive links can never leak
        a match identity into the read model. Callers must load match facts,
        quotes and prediction/decision evidence in bulk — never per row
        (T84 forbids N+1 SQL/Redis on this path).
        """
        statement = (
            select(
                MarketRow.id,
                MarketRow.question,
                MarketRow.status,
                MarketRow.rules_version,
                MarketRow.observed_at,
                MarketRow.event_start,
                MarketRow.updated_at,
                MarketRow.outcome_a_player_id,
                MarketRow.outcome_a_name,
                MarketRow.outcome_b_player_id,
                MarketRow.outcome_b_name,
                MarketMatchLinkRow.match_id,
                MarketMatchLinkRow.evidence,
            )
            .select_from(MarketRow)
            .outerjoin(
                MarketMatchLinkRow,
                (MarketMatchLinkRow.market_id == MarketRow.id)
                & (MarketMatchLinkRow.status == "active"),
            )
            .order_by(MarketRow.updated_at.desc())
        )
        async with self._database.session() as session:
            rows = (await session.execute(statement)).all()
        return [
            MarketOverviewRow(
                market_id=row[0],
                question=row[1],
                status=row[2],
                rules_version=int(row[3]),
                observed_at=row[4],
                event_start=row[5],
                updated_at=row[6],
                outcome_a_player_id=row[7],
                outcome_a_name=row[8],
                outcome_b_player_id=row[9],
                outcome_b_name=row[10],
                active_match_id=row[11],
                link_evidence_available=bool(row[11]) and bool(row[12]),
            )
            for row in rows
        ]

    async def latest_decision_observations(self) -> list[DecisionObservation]:
        """The newest decision observation per match, newest decision first."""
        async with self._database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(DecisionObservationRow)
                        .distinct(DecisionObservationRow.match_id)
                        .order_by(
                            DecisionObservationRow.match_id,
                            DecisionObservationRow.observation_version.desc(),
                        )
                    )
                )
                .scalars()
                .all()
            )
        observations = [
            DecisionObservation.model_validate(row.payload) for row in rows
        ]
        observations.sort(key=lambda item: item.as_of, reverse=True)
        return observations

    async def latest_prediction(self, match_id: str) -> PredictionSnapshot | None:
        """Most recent prediction evidence for one match."""
        async with self._database.session() as session:
            row = await session.scalar(
                select(PredictionSnapshotRow)
                .where(PredictionSnapshotRow.match_id == match_id)
                .order_by(
                    PredictionSnapshotRow.as_of.desc(), PredictionSnapshotRow.id.desc()
                )
                .limit(1)
            )
        if row is None:
            return None
        return PredictionSnapshot.model_validate(row.payload)

    async def latest_predictions_for_matches(
        self, match_ids: Sequence[str]
    ) -> dict[str, PredictionSnapshot]:
        """Newest prediction evidence per match in ONE query (no N+1).

        Same ordering contract as `latest_prediction`: newest `as_of`, then
        newest row id for identical timestamps.
        """
        ids = {match_id for match_id in match_ids if match_id}
        if not ids:
            return {}
        statement = (
            select(PredictionSnapshotRow)
            .where(PredictionSnapshotRow.match_id.in_(ids))
            .distinct(PredictionSnapshotRow.match_id)
            .order_by(
                PredictionSnapshotRow.match_id,
                PredictionSnapshotRow.as_of.desc(),
                PredictionSnapshotRow.id.desc(),
            )
        )
        async with self._database.session() as session:
            rows = (await session.execute(statement)).scalars().all()
        return {
            row.match_id: PredictionSnapshot.model_validate(row.payload) for row in rows
        }


def _quote_record(market_id: str, row: MarketQuoteSnapshotRow) -> QuoteSnapshotRecord:
    levels = None
    payload = row.payload or {}
    books = payload.get("books")
    if isinstance(books, list) and len(books) == 2:
        levels = (
            OutcomeBook.model_validate(books[0]),
            OutcomeBook.model_validate(books[1]),
        )
    best_bid = None
    best_ask = None
    if levels is not None:
        first_player = levels[0].outcome_player_id
        best_bid = (first_player, row.outcome_a_bid) if row.outcome_a_bid else None
        best_ask = (first_player, row.outcome_a_ask) if row.outcome_a_ask else None
    return QuoteSnapshotRecord(
        market_id=market_id,
        source=QuoteSource(row.source),
        state=QuoteState(row.quote_state),
        book_hash=row.book_hash,
        as_of=row.as_of,
        expires_at=row.expires_at,
        levels=levels,
        outcome_bids=(row.outcome_a_bid, row.outcome_b_bid),
        outcome_asks=(row.outcome_a_ask, row.outcome_b_ask),
        best_bid=best_bid,
        best_ask=best_ask,
        spread=row.spread,
        depth_usd=row.depth_usd,
    )


def _quote_values(record: QuoteSnapshotRecord) -> dict[str, Any]:
    return {
        "source": record.source.value,
        "quote_state": record.state.value,
        "book_hash": record.book_hash,
        "as_of": record.as_of,
        "expires_at": record.expires_at,
        "outcome_a_bid": record.outcome_bids[0],
        "outcome_a_ask": record.outcome_asks[0],
        "outcome_b_bid": record.outcome_bids[1],
        "outcome_b_ask": record.outcome_asks[1],
        "spread": record.spread,
        "depth_usd": record.depth_usd,
        "payload": (
            {"books": [side.model_dump(mode="json") for side in record.levels]}
            if record.levels is not None
            else None
        ),
        "updated_at": datetime.now(UTC),
    }


class MarketQuoteSnapshotRepository:
    """Durable latest-quote projection: at most one row per market (T85).

    Single-writer by design (the runtime role): the coverage lane and the
    realtime mirror both come through `upsert`, which enforces the shared
    precedence rule inside one transaction. The API role only reads.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def upsert(self, record: QuoteSnapshotRecord) -> bool:
        """True when a row was written or replaced; False when the incoming
        quote is older, lower-precedence or byte-identical (idempotent)."""
        async with self._database.session() as session:
            async with session.begin():
                current = await session.get(
                    MarketQuoteSnapshotRow, record.market_id, with_for_update=True
                )
                existing = (
                    _quote_record(record.market_id, current)
                    if current is not None
                    else None
                )
                if not decide_quote_write(existing, record):
                    return False
                values = _quote_values(record)
                if current is None:
                    session.add(
                        MarketQuoteSnapshotRow(market_id=record.market_id, **values)
                    )
                else:
                    for key, value in values.items():
                        setattr(current, key, value)
                return True

    async def load(self, market_id: str) -> QuoteSnapshotRecord | None:
        async with self._database.session() as session:
            row = await session.get(MarketQuoteSnapshotRow, market_id)
        return _quote_record(market_id, row) if row is not None else None

    async def load_many(
        self, market_ids: Sequence[str]
    ) -> dict[str, QuoteSnapshotRecord]:
        """Every requested market's stored quote in ONE query (no N+1)."""
        ids = {market_id for market_id in market_ids if market_id}
        if not ids:
            return {}
        async with self._database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(MarketQuoteSnapshotRow).where(
                            MarketQuoteSnapshotRow.market_id.in_(ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
        return {row.market_id: _quote_record(row.market_id, row) for row in rows}


__all__ = [
    "LinkFrozenError",
    "MarketOverviewRow",
    "MarketQuoteSnapshotRepository",
    "MarketRepository",
]
