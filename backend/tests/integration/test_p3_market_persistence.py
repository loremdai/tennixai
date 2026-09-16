"""P3 market persistence integration against the compose PostgreSQL (T58).

Requires: `docker compose up -d --wait postgres redis` and
`uv run alembic upgrade head`. Skips honestly when either is missing.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from app.config import Settings
from app.decision.models import DecisionAction
from app.persistence.database import Database
from app.persistence.market_repositories import (
    LinkFrozenError,
    MarketRepository,
)
from app.persistence.models import (
    DecisionObservationRow,
    MarketMatchLinkRow,
    MarketRow,
    MarketRuleRow,
    PredictionSnapshotRow,
    RawProviderEventRow,
)
from app.persistence.paper_repositories import PaperLedgerRepository
from app.persistence.repositories import (
    PostgresIdentityRepository,
    RawProviderEventRepository,
)
from p3_fakes import (
    NOW,
    make_intent,
    make_market,
    make_observation,
    make_prediction,
    make_rules,
)

pytestmark = pytest.mark.infrastructure


@pytest.fixture()
async def database():
    settings = Settings(_env_file=None)
    db = Database(settings.database_url)
    try:
        async with db.engine.connect() as connection:
            result = await connection.execute(
                text("SELECT to_regclass('public.markets')")
            )
            mapped = result.scalar()
    except Exception as exc:  # pragma: no cover - environment dependent
        await db.dispose()
        pytest.skip(
            "PostgreSQL not reachable at TENNIX_DATABASE_URL "
            f"({type(exc).__name__}); start compose services"
        )
    if mapped is None:
        await db.dispose()
        pytest.skip("P3 schema not migrated; run `uv run alembic upgrade head`")
    try:
        yield db
    finally:
        await db.dispose()


@pytest.fixture()
async def match_id(database: Database) -> str:
    identity = PostgresIdentityRepository(database)
    return await identity.get_or_create("match", "itest-p3", uuid4().hex[:10])


async def test_concurrent_market_registration_converges_to_one_internal_id(
    database: Database,
) -> None:
    repository = MarketRepository(database)
    condition_id = f"0x{uuid4().hex}"

    results = await asyncio.gather(
        *(
            repository.get_or_create_market_id(
                provider="polymarket",
                provider_event_id="ev_itest_1",
                condition_id=condition_id,
            )
            for _ in range(20)
        )
    )

    internal_id = results[0]
    assert set(results) == {internal_id}
    assert internal_id.startswith("mkt_")
    assert condition_id not in internal_id
    async with database.session() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(MarketRow)
            .where(MarketRow.id == internal_id)
        )
    assert count == 1


async def test_save_and_reload_market_round_trips_canonical_shape(
    database: Database,
) -> None:
    repository = MarketRepository(database)
    internal_id = await repository.get_or_create_market_id(
        provider="polymarket",
        provider_event_id="ev_itest_2",
        condition_id=f"0x{uuid4().hex}",
    )
    market = make_market(internal_id, match_id="mat_itest")
    await repository.save_market(market)

    reloaded = await repository.get_market(internal_id)
    assert reloaded == market

    # Provider identifiers stay in the private mapping row only.
    mapping = await repository.get_external_id(internal_id)
    assert mapping is not None
    assert mapping.provider_event_id == "ev_itest_2"
    reloaded_public = reloaded.model_dump()
    assert "condition_id" not in reloaded_public
    assert "token_ids" not in reloaded_public


async def test_rules_are_hashed_versioned_and_idempotent(
    database: Database, match_id: str
) -> None:
    repository = MarketRepository(database)
    internal_id = await repository.get_or_create_market_id(
        provider="polymarket",
        provider_event_id="ev_itest_3",
        condition_id=f"0x{uuid4().hex}",
    )
    await repository.save_market(make_market(internal_id))

    first = await repository.save_rules(make_rules(internal_id, rules_hash="hash_a"))
    repeated = await repository.save_rules(make_rules(internal_id, rules_hash="hash_a"))
    assert first == 1
    assert repeated == 1

    second = await repository.save_rules(make_rules(internal_id, rules_hash="hash_b"))
    assert second == 2

    current = await repository.get_current_rules(internal_id)
    assert current is not None
    rules, version = current
    assert version == 2
    assert rules.rules_hash == "hash_b"

    async with database.session() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(MarketRuleRow)
            .where(MarketRuleRow.market_id == internal_id)
        )
    assert count == 2


async def test_one_active_link_per_match_with_replacement_before_intent(
    database: Database, match_id: str
) -> None:
    repository = MarketRepository(database)
    first_id = await repository.get_or_create_market_id(
        provider="polymarket",
        provider_event_id="ev_itest_4a",
        condition_id=f"0x{uuid4().hex}",
    )
    second_id = await repository.get_or_create_market_id(
        provider="polymarket",
        provider_event_id="ev_itest_4b",
        condition_id=f"0x{uuid4().hex}",
    )
    await repository.save_market(make_market(first_id))
    await repository.save_market(make_market(second_id))

    await repository.link_match(
        market_id=first_id, match_id=match_id, evidence={"pair": ["ply_a", "ply_b"]}
    )
    # Condition replacement before any intent: the new market takes over.
    await repository.link_match(
        market_id=second_id, match_id=match_id, evidence={"pair": ["ply_a", "ply_b"]}
    )

    active = await repository.active_link_for_match(match_id)
    assert active is not None
    assert active.market_id == second_id

    async with database.session() as session:
        rows = (
            (
                await session.execute(
                    select(MarketMatchLinkRow).where(
                        MarketMatchLinkRow.match_id == match_id
                    )
                )
            )
            .scalars()
            .all()
        )
    statuses = {row.market_id: row.status for row in rows}
    assert statuses[first_id] == "replaced"
    assert statuses[second_id] == "active"


async def test_link_is_frozen_after_entry_intent(
    database: Database, match_id: str
) -> None:
    markets = MarketRepository(database)
    ledger = PaperLedgerRepository(database)
    first_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id="ev_itest_5a",
        condition_id=f"0x{uuid4().hex}",
    )
    replacement_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id="ev_itest_5b",
        condition_id=f"0x{uuid4().hex}",
    )
    await markets.save_market(make_market(first_id))
    await markets.save_market(make_market(replacement_id))
    await markets.link_match(
        market_id=first_id, match_id=match_id, evidence={"pair": ["ply_a", "ply_b"]}
    )

    await ledger.create_intent(make_intent(match_id, first_id))

    # Identical re-link is a no-op; migrating to the replacement market is not.
    await markets.link_match(
        market_id=first_id, match_id=match_id, evidence={"pair": ["ply_a", "ply_b"]}
    )
    with pytest.raises(LinkFrozenError):
        await markets.link_match(
            market_id=replacement_id,
            match_id=match_id,
            evidence={"pair": ["ply_a", "ply_b"]},
        )

    active = await markets.active_link_for_match(match_id)
    assert active is not None
    assert active.market_id == first_id


async def test_decision_and_prediction_observations_are_version_idempotent(
    database: Database, match_id: str
) -> None:
    repository = MarketRepository(database)
    internal_id = await repository.get_or_create_market_id(
        provider="polymarket",
        provider_event_id="ev_itest_6",
        condition_id=f"0x{uuid4().hex}",
    )
    await repository.save_market(make_market(internal_id, match_id=match_id))

    observation = make_observation(match_id, internal_id, observation_version=1)
    await repository.save_decision_observation(observation)
    await repository.save_decision_observation(observation)
    await repository.save_decision_observation(
        make_observation(match_id, internal_id, observation_version=2)
    )

    async with database.session() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(DecisionObservationRow)
            .where(DecisionObservationRow.match_id == match_id)
        )
    assert count == 2

    latest = await repository.latest_decision_observation(match_id)
    assert latest is not None
    assert latest.observation_version == 2
    assert latest.action is DecisionAction.BUY
    assert latest.conservative_net_edge == Decimal("0.041")
    assert latest.quote is not None
    assert latest.quote.average_price == Decimal("0.525")

    prediction = make_prediction(match_id)
    await repository.save_prediction(prediction)
    await repository.save_prediction(prediction)
    async with database.session() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(PredictionSnapshotRow)
            .where(PredictionSnapshotRow.match_id == match_id)
        )
    assert count == 1


async def test_raw_cleanup_never_deletes_rules_or_ledger_evidence(
    database: Database, match_id: str
) -> None:
    markets = MarketRepository(database)
    ledger = PaperLedgerRepository(database)
    raw = RawProviderEventRepository(database)

    internal_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id="ev_itest_7",
        condition_id=f"0x{uuid4().hex}",
    )
    await markets.save_market(make_market(internal_id, match_id=match_id))
    await markets.save_rules(make_rules(internal_id, rules_hash="hash_keep"))
    intent = make_intent(match_id, internal_id)
    await ledger.create_intent(intent)

    await raw.append(
        provider="polymarket",
        channel="ws",
        kind="book",
        payload={"sample": True},
        observed_at=NOW - timedelta(days=20),
        match_id=match_id,
    )

    purged = await raw.purge_raw_events(datetime.now(UTC) - timedelta(days=14))
    assert purged >= 1

    async with database.session() as session:
        remaining_raw = await session.scalar(
            select(func.count())
            .select_from(RawProviderEventRow)
            .where(
                RawProviderEventRow.observed_at < datetime.now(UTC) - timedelta(days=14)
            )
        )
        rules_count = await session.scalar(
            select(func.count())
            .select_from(MarketRuleRow)
            .where(MarketRuleRow.market_id == internal_id)
        )
    assert remaining_raw == 0
    assert rules_count == 1
    assert await ledger.get_intent(intent.id) == intent


async def test_market_observations_append_only_for_decision_relevant_changes(
    database: Database, match_id: str
) -> None:
    repository = MarketRepository(database)
    internal_id = await repository.get_or_create_market_id(
        provider="polymarket",
        provider_event_id="ev_itest_8",
        condition_id=f"0x{uuid4().hex}",
    )
    await repository.save_market(make_market(internal_id, match_id=match_id))

    first = await repository.save_observation(
        market_id=internal_id,
        match_id=match_id,
        kind="action_change",
        payload={"action": "buy", "observation_version": 1},
        observed_at=NOW,
    )
    second = await repository.save_observation(
        market_id=internal_id,
        match_id=match_id,
        kind="tracking_gap",
        payload={"reason": "reconnect"},
        observed_at=NOW + timedelta(seconds=5),
    )
    assert second > first
