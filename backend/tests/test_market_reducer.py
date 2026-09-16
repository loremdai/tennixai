"""Canonical market book reducer tests (T60).

One writer per market. Full books replace state, price changes mutate exact
levels, zero size deletes, timestamp/hash regressions are rejected, tick
changes update metadata, missing baselines demand a REST reconcile and
reconnects always reset through REST before accepting deltas.
"""

from datetime import UTC, datetime
from decimal import Decimal


from app.markets.models import BookLevel, OrderBookState, OutcomeBook
from app.markets.reducer import MarketBookReducer, RawMarketEvent

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
TOKEN_A = "990001112223334445551"
TOKEN_B = "990001112223334445552"


def make_reducer(now_fn=None) -> MarketBookReducer:
    return MarketBookReducer(
        market_id="mkt_1",
        token_players={TOKEN_A: "ply_a", TOKEN_B: "ply_b"},
        now_fn=now_fn or (lambda: NOW),
    )


def book_event(
    asset_id: str,
    *,
    buys: list[tuple[str, str]],
    sells: list[tuple[str, str]],
    hash: str,
    timestamp: int,
) -> RawMarketEvent:
    return RawMarketEvent(
        event_type="book",
        asset_id=asset_id,
        payload={
            "event_type": "book",
            "asset_id": asset_id,
            "market": "0xconditionfake",
            "buys": [{"price": price, "size": size} for price, size in buys],
            "sells": [{"price": price, "size": size} for price, size in sells],
            "hash": hash,
            "timestamp": str(timestamp),
        },
        received_at=NOW,
    )


def price_change_event(
    asset_id: str,
    changes: list[tuple[str, str, str]],
    *,
    hash: str | None = None,
    timestamp: int = 1_789_999_300_000,
) -> RawMarketEvent:
    return RawMarketEvent(
        event_type="price_change",
        asset_id=asset_id,
        payload={
            "event_type": "price_change",
            "asset_id": asset_id,
            "market": "0xconditionfake",
            "changes": [
                {"price": price, "side": side, "size": size}
                for price, side, size in changes
            ],
            "hash": hash,
            "timestamp": str(timestamp),
        },
        received_at=NOW,
    )


def seed_both_books(reducer: MarketBookReducer) -> None:
    reducer.apply_event(
        book_event(
            TOKEN_A,
            buys=[("0.50", "300"), ("0.55", "200")],
            sells=[("0.57", "150"), ("0.60", "120")],
            hash="hash_a1",
            timestamp=1_789_999_200_000,
        )
    )
    reducer.apply_event(
        book_event(
            TOKEN_B,
            buys=[("0.40", "180")],
            sells=[("0.45", "160")],
            hash="hash_b1",
            timestamp=1_789_999_200_000,
        )
    )


def test_full_book_replaces_state_with_canonical_ordering():
    reducer = make_reducer()
    seed_both_books(reducer)

    state = reducer.current_state()
    assert state is not None
    first, second = state.books
    assert first.outcome_player_id == "ply_a"
    assert [level.price for level in first.bids] == [Decimal("0.55"), Decimal("0.50")]
    assert [level.price for level in first.asks] == [Decimal("0.57"), Decimal("0.60")]
    assert second.outcome_player_id == "ply_b"
    assert state.sequence == 2
    assert state.book_hash

    # A newer full book replaces the previous levels entirely.
    reduction = reducer.apply_event(
        book_event(
            TOKEN_A,
            buys=[("0.52", "100")],
            sells=[("0.58", "90")],
            hash="hash_a2",
            timestamp=1_789_999_250_000,
        )
    )
    assert reduction.changed
    assert reduction.rejected is None
    state = reducer.current_state()
    assert state is not None
    first = state.books[0]
    assert [level.price for level in first.bids] == [Decimal("0.52")]
    assert [level.price for level in first.asks] == [Decimal("0.58")]


def test_state_is_none_until_both_sides_have_a_baseline():
    reducer = make_reducer()
    reduction = reducer.apply_event(
        book_event(
            TOKEN_A,
            buys=[("0.50", "300")],
            sells=[("0.57", "150")],
            hash="hash_a1",
            timestamp=1_789_999_200_000,
        )
    )
    assert reduction.changed
    assert reducer.current_state() is None


def test_price_change_mutates_exact_levels_insert_update_delete():
    reducer = make_reducer()
    seed_both_books(reducer)

    # Insert a new bid level, update an existing ask, delete a bid via size 0.
    reduction = reducer.apply_event(
        price_change_event(
            TOKEN_A,
            [
                ("0.53", "BUY", "75"),  # insert
                ("0.57", "SELL", "140"),  # update
                ("0.50", "BUY", "0"),  # delete
            ],
            hash="hash_a2",
            timestamp=1_789_999_300_000,
        )
    )
    assert reduction.changed
    state = reducer.current_state()
    assert state is not None
    first = state.books[0]
    assert [(level.price, level.size) for level in first.bids] == [
        (Decimal("0.55"), Decimal("200")),
        (Decimal("0.53"), Decimal("75")),
    ]
    assert [(level.price, level.size) for level in first.asks] == [
        (Decimal("0.57"), Decimal("140")),
        (Decimal("0.60"), Decimal("120")),
    ]


def test_price_change_without_baseline_demands_snapshot():
    reducer = make_reducer()
    reduction = reducer.apply_event(
        price_change_event(TOKEN_A, [("0.53", "BUY", "75")])
    )
    assert reduction.needs_snapshot
    assert not reduction.changed
    assert reducer.current_state() is None


def test_reversed_delivery_is_rejected_by_timestamp():
    reducer = make_reducer()
    seed_both_books(reducer)
    before = reducer.current_state()

    reduction = reducer.apply_event(
        price_change_event(
            TOKEN_A,
            [("0.53", "BUY", "75")],
            hash="hash_old",
            timestamp=1_789_999_100_000,  # older than the seeded book
        )
    )
    assert reduction.rejected == "stale_timestamp"
    assert not reduction.changed
    assert reducer.current_state() == before


def test_duplicate_hash_is_rejected():
    reducer = make_reducer()
    seed_both_books(reducer)

    reduction = reducer.apply_event(
        book_event(
            TOKEN_A,
            buys=[("0.50", "300"), ("0.55", "200")],
            sells=[("0.57", "150"), ("0.60", "120")],
            hash="hash_a1",  # same hash as the seeded book
            timestamp=1_789_999_260_000,
        )
    )
    assert reduction.rejected == "duplicate_hash"
    assert not reduction.changed


def test_tick_size_change_updates_metadata_without_touching_levels():
    reducer = make_reducer()
    seed_both_books(reducer)

    reduction = reducer.apply_event(
        RawMarketEvent(
            event_type="tick_size_change",
            asset_id=TOKEN_A,
            payload={
                "event_type": "tick_size_change",
                "asset_id": TOKEN_A,
                "new_tick_size": "0.01",
                "old_tick_size": "0.001",
                "timestamp": "1789999300000",
            },
            received_at=NOW,
        )
    )
    assert reduction.tick_size == Decimal("0.01")
    assert not reduction.changed
    assert reducer.current_tick_size(TOKEN_A) == Decimal("0.01")


def test_unknown_asset_is_ignored_without_side_effects():
    reducer = make_reducer()
    seed_both_books(reducer)
    before = reducer.current_state()

    reduction = reducer.apply_event(
        price_change_event("9999999999", [("0.53", "BUY", "75")])
    )
    assert not reduction.changed
    assert reducer.current_state() == before


def test_reconnect_rest_baseline_resets_and_accepts_later_deltas():
    reducer = make_reducer()
    seed_both_books(reducer)

    rest_state = OrderBookState(
        market_id="mkt_1",
        books=(
            OutcomeBook(
                outcome_player_id="ply_a",
                bids=(BookLevel(price=Decimal("0.49"), size=Decimal("500")),),
                asks=(BookLevel(price=Decimal("0.56"), size=Decimal("400")),),
            ),
            OutcomeBook(
                outcome_player_id="ply_b",
                bids=(BookLevel(price=Decimal("0.41"), size=Decimal("300")),),
                asks=(BookLevel(price=Decimal("0.46"), size=Decimal("260")),),
            ),
        ),
        sequence=0,
        book_hash="rest_combined",
        provider_timestamp=datetime.fromtimestamp(1_789_999_500, tz=UTC),
        received_at=NOW,
    )
    reduction = reducer.baseline_from_rest(
        rest_state, player_tokens={"ply_a": TOKEN_A, "ply_b": TOKEN_B}
    )
    assert reduction.changed
    state = reducer.current_state()
    assert state is not None
    assert [level.price for level in state.books[0].bids] == [Decimal("0.49")]

    # A delta newer than the REST baseline is accepted again.
    after = reducer.apply_event(
        price_change_event(
            TOKEN_A,
            [("0.50", "BUY", "120")],
            hash="hash_a9",
            timestamp=1_789_999_600_000,
        )
    )
    assert after.changed
    state = reducer.current_state()
    assert state is not None
    assert [level.price for level in state.books[0].bids] == [
        Decimal("0.50"),
        Decimal("0.49"),
    ]


def test_resolution_event_passes_through_without_book_change():
    reducer = make_reducer()
    seed_both_books(reducer)

    reduction = reducer.apply_event(
        RawMarketEvent(
            event_type="resolution",
            asset_id=TOKEN_A,
            payload={"event_type": "resolution", "asset_id": TOKEN_A},
            received_at=NOW,
        )
    )
    assert reduction.resolution_requested
    assert not reduction.changed


def test_sequence_is_monotonic_and_hash_changes_with_state():
    reducer = make_reducer()
    seed_both_books(reducer)
    first = reducer.current_state()
    assert first is not None

    reducer.apply_event(
        price_change_event(
            TOKEN_A,
            [("0.54", "BUY", "10")],
            hash="hash_a3",
            timestamp=1_789_999_400_000,
        )
    )
    second = reducer.current_state()
    assert second is not None
    assert second.sequence > first.sequence
    assert second.book_hash != first.book_hash
