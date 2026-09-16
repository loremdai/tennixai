"""Transactional paper trading service tests (T64).

Fake clock, fake ledger, real quote math: the first eligible BUY and the
first EV SELL become the only entry/exit attempts; requote happens only
after the market's actual sports delay; FOK requires the full stake or the
full position within the frozen limit; an unverifiable book becomes a typed
no-fill and never a synthetic fill; commits precede publishes.
"""

from datetime import UTC, datetime

import pytest

from app.decision.models import DecisionAction
from app.markets.models import ResolutionStatus
from app.paper.models import IntentSide, IntentStatus, PositionStatus, TrackName
from app.paper.service import PaperTradingService
from app.persistence.paper_repositories import UniqueViolationError
from p3_fakes import (
    make_intent,
    make_position,
    make_resolution,
)
from tests_support import FakeClock, InMemoryPaperLedger, build_service_inputs


@pytest.fixture()
def env():
    clock = FakeClock(datetime(2026, 9, 16, 12, 0, tzinfo=UTC))
    ledger = InMemoryPaperLedger()
    published: list[str] = []

    async def publish(event: str) -> None:
        ledger.log.append(f"publish:{event}")
        published.append(event)

    service = PaperTradingService(ledger=ledger, clock=clock.now, publish=publish)
    inputs = build_service_inputs()
    return {
        "clock": clock,
        "ledger": ledger,
        "service": service,
        "published": published,
        **inputs,
    }


async def test_first_buy_creates_one_entry_intent_and_requotes_after_delay(env):
    service, ledger, clock = env["service"], env["ledger"], env["clock"]
    observation = env["buy_observation"]

    await service.on_decision(
        observation,
        book=env["book"],
        metadata=env["metadata"],
        rules_hash="rules_v1",
    )
    intents = await ledger.load_pending_intents()
    assert len(intents) == 1
    intent = intents[0]
    assert intent.side is IntentSide.ENTRY
    assert intent.delay_seconds == 10

    # Before the sports delay: no execution attempt at all.
    clock.advance(5)
    await service.execute_due_intents(
        book=env["book"], metadata=env["metadata"], market_id="mkt_1"
    )
    stored = await ledger.get_intent(intent.id)
    assert stored.status is IntentStatus.PENDING

    # After the delay: FOK against the then-current book fills.
    clock.advance(6)
    await service.execute_due_intents(
        book=env["book"], metadata=env["metadata"], market_id="mkt_1"
    )
    stored = await ledger.get_intent(intent.id)
    assert stored.status is IntentStatus.FILLED
    position = await ledger.get_position(intent.match_id)
    assert position is not None
    assert position.status is PositionStatus.OPEN

    # A second identical BUY observation never creates another intent.
    await service.on_decision(
        observation,
        book=env["book"],
        metadata=env["metadata"],
        rules_hash="rules_v1",
    )
    with pytest.raises(UniqueViolationError):
        await ledger.create_intent(
            make_intent(intent.match_id, intent.market_id, idempotency_key="other")
        )
    # The fill commit happens before the filled publish.
    fill_index = ledger.log.index("commit:fill")
    filled_publish_index = next(
        index
        for index, entry in enumerate(ledger.log)
        if entry.startswith("publish:filled")
    )
    assert fill_index < filled_publish_index


async def test_insufficient_depth_after_delay_is_missed_not_partial(env):
    service, ledger, clock = env["service"], env["ledger"], env["clock"]
    await service.on_decision(
        env["buy_observation"],
        book=env["book"],
        metadata=env["metadata"],
        rules_hash="rules_v1",
    )
    clock.advance(11)

    thin_book = env["thin_book"]
    await service.execute_due_intents(
        book=thin_book, metadata=env["metadata"], market_id="mkt_1"
    )

    intents = [intent for intent in await ledger.load_pending_intents()]
    assert intents == []
    filled = [
        intent
        for intent in await ledger.load_all_intents()
        if intent.status is IntentStatus.NO_FILL
    ]
    assert len(filled) == 1
    assert filled[0].no_fill_reason == "DEPTH_INSUFFICIENT"
    assert await ledger.get_position(filled[0].match_id) is None


async def test_unverifiable_book_never_produces_synthetic_fill(env):
    service, ledger, clock = env["service"], env["ledger"], env["clock"]
    await service.on_decision(
        env["buy_observation"],
        book=env["book"],
        metadata=env["metadata"],
        rules_hash="rules_v1",
    )
    clock.advance(11)

    await service.execute_due_intents(
        book=None, metadata=env["metadata"], market_id="mkt_1"
    )

    no_fills = [
        intent
        for intent in await ledger.load_all_intents()
        if intent.status is IntentStatus.NO_FILL
    ]
    assert len(no_fills) == 1
    assert no_fills[0].no_fill_reason == "BOOK_UNVERIFIABLE"
    assert await ledger.get_position(no_fills[0].match_id) is None


async def test_adverse_price_beyond_frozen_limit_is_no_fill(env):
    service, ledger, clock = env["service"], env["ledger"], env["clock"]
    await service.on_decision(
        env["buy_observation"],
        book=env["book"],
        metadata=env["metadata"],
        rules_hash="rules_v1",
    )
    clock.advance(11)

    await service.execute_due_intents(
        book=env["worse_book"], metadata=env["metadata"], market_id="mkt_1"
    )

    no_fills = [
        intent
        for intent in await ledger.load_all_intents()
        if intent.status is IntentStatus.NO_FILL
    ]
    assert len(no_fills) == 1
    assert no_fills[0].no_fill_reason == "PRICE_EXCEEDED"


async def test_expired_intent_is_terminal_no_fill(env):
    service, ledger, clock = env["service"], env["ledger"], env["clock"]
    await service.on_decision(
        env["buy_observation"],
        book=env["book"],
        metadata=env["metadata"],
        rules_hash="rules_v1",
    )
    # Beyond created_at + expires window.
    clock.advance(3600)

    await service.execute_due_intents(
        book=env["book"], metadata=env["metadata"], market_id="mkt_1"
    )

    no_fills = [
        intent
        for intent in await ledger.load_all_intents()
        if intent.status is IntentStatus.NO_FILL
    ]
    assert len(no_fills) == 1
    assert no_fills[0].no_fill_reason == "EXPIRED"


async def test_sell_creates_single_exit_intent_and_exit_missed_holds(env):
    service, ledger, clock = env["service"], env["ledger"], env["clock"]
    # Seed a filled entry directly.
    intent = make_intent("mat_1", "mkt_1")
    await ledger.create_intent(intent)
    from p3_fakes import make_entry_fill

    await ledger.record_fill(
        make_entry_fill(intent.id), position=make_position("mat_1", "mkt_1")
    )

    sell = env["sell_observation"]
    await service.on_decision(
        sell, book=env["book"], metadata=env["metadata"], rules_hash="rules_v1"
    )
    clock.advance(11)
    # Thin exit depth: the full position cannot leave -> EXIT_MISSED.
    await service.execute_due_intents(
        book=env["thin_book"], metadata=env["metadata"], market_id="mkt_1"
    )

    position = await ledger.get_position("mat_1")
    assert position is not None
    assert position.status is PositionStatus.EXIT_MISSED
    exit_intents = [
        intent
        for intent in await ledger.load_all_intents()
        if intent.side is IntentSide.EXIT
    ]
    assert len(exit_intents) == 1
    assert exit_intents[0].status is IntentStatus.NO_FILL

    # A second SELL never re-tries the exit.
    await service.on_decision(
        sell, book=env["book"], metadata=env["metadata"], rules_hash="rules_v1"
    )
    exit_intents = [
        intent
        for intent in await ledger.load_all_intents()
        if intent.side is IntentSide.EXIT
    ]
    assert len(exit_intents) == 1


async def test_settlement_uses_provider_resolution_and_writes_three_tracks(env):
    service, ledger = env["service"], env["ledger"]
    intent = make_intent("mat_1", "mkt_1")
    await ledger.create_intent(intent)
    from p3_fakes import make_entry_fill

    await ledger.record_fill(
        make_entry_fill(intent.id), position=make_position("mat_1", "mkt_1")
    )

    resolution = make_resolution("mkt_1", status=ResolutionStatus.FINAL)
    await service.settle_market("mkt_1", resolution)

    position = await ledger.get_position("mat_1")
    assert position is not None
    assert position.status is PositionStatus.SETTLED
    tracks = await ledger.load_track_results(position.id)
    assert {result.track for result in tracks} == {
        TrackName.EV_EXIT,
        TrackName.HODL_BASELINE,
        TrackName.CONVERGENCE_LOCK,
    }
    stored_resolution = await ledger.get_resolution("mkt_1")
    assert stored_resolution is not None
    assert stored_resolution.status is ResolutionStatus.FINAL


async def test_hold_and_no_bet_observations_create_nothing(env):
    service, ledger = env["service"], env["ledger"]

    for action in (DecisionAction.HOLD, DecisionAction.NO_BET, DecisionAction.WAIT):
        observation = env["observation_for"](action)
        await service.on_decision(
            observation,
            book=env["book"],
            metadata=env["metadata"],
            rules_hash="rules_v1",
        )

    assert await ledger.load_all_intents() == []
