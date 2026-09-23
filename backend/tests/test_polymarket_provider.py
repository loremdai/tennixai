"""Read-only Polymarket adapter contract tests (T59).

All transport is `httpx.MockTransport`; no real network call happens here.
Fixtures use fake IDs and fake player names. The adapter must never issue a
non-GET request, never touch an authenticated path, and never leak URLs,
keys, condition or token identifiers through canonical models or errors.
"""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.errors import AppError
from app.markets.models import MarketStatus, ResolutionStatus
from app.markets.polymarket import PolymarketProvider
from app.players.enrichment import derive_chinese_aliases
from app.players.models import RankingEntry, RankingMovement, Tour
from app.players.normalization import derive_english_aliases
from app.players.repository import MemoryPlayerDirectoryRepository
from app.players.resolver import PlayerResolver
from app.domain import Player

FIXTURES = Path(__file__).parent / "fixtures" / "polymarket"

CONDITION_A1 = "0xfake0000000000000000000000000000000000000000000000000000000000a1"
TOKEN_A = "990001112223334445551"
TOKEN_B = "990001112223334445552"
INTERNAL_MARKET_ID = "mkt_test_a1"
NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def _fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _rank(player_id: str, name: str, rank: int, tour: Tour = Tour.ATP) -> RankingEntry:
    return RankingEntry(
        player=Player(id=player_id, name=name, ranking=rank),
        tour=tour,
        rank=rank,
        points=1000,
        movement=RankingMovement.SAME,
        ranking_date=NOW.date(),
        fetched_at=NOW,
    )


@pytest.fixture()
async def resolver() -> PlayerResolver:
    repository = MemoryPlayerDirectoryRepository()
    await repository.save_ranking_snapshot(
        (
            _rank("ply_alpha", "Alpha One", 10),
            _rank("ply_beta", "Beta Two", 20),
            _rank("ply_gamma", "Gamma Three", 30),
        )
    )
    for directory_player in await repository.list_players_for_alias_sync(limit=100):
        await repository.upsert_aliases(derive_english_aliases(directory_player))
    await repository.upsert_aliases(
        derive_chinese_aliases("ply_alpha", "阿尔法一号", model="test-model")
    )
    await repository.upsert_aliases(
        derive_chinese_aliases("ply_beta", "贝塔二号", model="test-model")
    )
    return PlayerResolver(repository)


class RecordingTransport:
    """Routes requests to canned payloads and records every call."""

    def __init__(self, overrides: dict | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.overrides = overrides or {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = request.url
        key = f"{url.host}{url.path}"
        for pattern, response in self.overrides.items():
            if pattern in key:
                return response(request) if callable(response) else response
        if url.host == "gamma-api.polymarket.com":
            if url.path == "/tags/slug/tennis":
                return httpx.Response(
                    200, json={"id": "42", "slug": "tennis", "label": "Tennis"}
                )
            if url.path == "/events/keyset":
                return httpx.Response(
                    200,
                    json={
                        "events": _fixture("events_tennis.json"),
                        "next_cursor": None,
                    },
                )
            if url.path == "/events":
                return httpx.Response(200, json=_fixture("events_tennis.json"))
            if url.path == "/markets":
                return httpx.Response(200, json=_fixture("gamma_market.json"))
        if url.host == "clob.polymarket.com":
            if url.path.startswith("/clob-markets/"):
                return httpx.Response(200, json=_fixture("clob_market_info.json"))
            if url.path == "/book":
                token = url.params.get("token_id")
                name = (
                    "book_outcome_a.json" if token == TOKEN_A else "book_outcome_b.json"
                )
                return httpx.Response(200, json=_fixture(name))
            if url.path.startswith("/fee-rate/"):
                return httpx.Response(200, json=_fixture("fee_rate.json"))
        return httpx.Response(404, json={"error": "not found"})

    def paths(self) -> list[str]:
        return [
            f"{request.method} {request.url.host}{request.url.path}"
            for request in self.requests
        ]


def make_provider(
    resolver: PlayerResolver,
    transport: RecordingTransport | None = None,
    *,
    gamma_payload_override: dict | None = None,
) -> tuple[PolymarketProvider, RecordingTransport]:
    recorder = transport or RecordingTransport()
    registered: dict[str, str] = {}
    counter = {"n": 0}

    async def registrar(provider_event_id: str, condition_id: str, token_ids):
        if condition_id in registered:
            return registered[condition_id]
        counter["n"] += 1
        internal_id = (
            INTERNAL_MARKET_ID if counter["n"] == 1 else f"mkt_test_{counter['n']}"
        )
        registered[condition_id] = internal_id
        return internal_id

    async def lookup(market_id: str):
        from app.markets.models import MarketExternalId

        if market_id != INTERNAL_MARKET_ID:
            return None
        return MarketExternalId(
            market_id=market_id,
            provider="polymarket",
            provider_event_id="900001",
            condition_id=CONDITION_A1,
            token_ids=(TOKEN_A, TOKEN_B),
        )

    provider = PolymarketProvider(
        gamma_base_url="https://gamma-api.polymarket.com",
        clob_base_url="https://clob.polymarket.com",
        resolver=resolver,
        registrar=registrar,
        external_lookup=lookup,
        transport=httpx.MockTransport(recorder.handler),
        now_fn=lambda: NOW,
    )
    return provider, recorder


# ---------------------------------------------------------------------------
# Listing and filtering
# ---------------------------------------------------------------------------


async def test_list_returns_only_complete_moneylines_with_internal_ids(resolver):
    provider, recorder = make_provider(resolver)

    markets = await provider.list_tennis_moneylines()

    assert len(markets) == 1
    market = markets[0]
    assert market.id == INTERNAL_MARKET_ID
    assert market.status is MarketStatus.OPEN
    assert market.provider == "polymarket"
    assert [outcome.player_id for outcome in market.outcomes] == [
        "ply_alpha",
        "ply_beta",
    ]
    assert [outcome.name for outcome in market.outcomes] == ["Alpha One", "Beta Two"]
    assert market.event_start == datetime(2026, 9, 20, 12, 0, tzinfo=UTC)

    public = market.model_dump(mode="json")
    serialized = json.dumps(public)
    assert CONDITION_A1 not in serialized
    assert TOKEN_A not in serialized
    assert TOKEN_B not in serialized


async def test_list_skips_non_moneyline_malformed_and_closed_with_typed_reasons(
    resolver,
):
    provider, _ = make_provider(resolver)

    await provider.list_tennis_moneylines()

    reasons = {skip.reason for skip in provider.skipped}
    assert "not_moneyline" in reasons  # Total Games market
    assert "malformed_tokens" in reasons  # Epsilon market without clobTokenIds
    assert "closed" in reasons  # Eta market already closed
    for skip in provider.skipped:
        assert skip.quality_code  # typed, stable codes


async def test_list_resolves_bilingual_outcome_names_to_same_internal_ids(resolver):
    events = _fixture("events_tennis.json")
    events[0]["markets"][0]["outcomes"] = json.dumps(["阿尔法一号", "贝塔二号"])
    recorder = RecordingTransport(
        overrides={
            "gamma-api.polymarket.com/events": httpx.Response(
                200, json={"events": events, "next_cursor": None}
            ),
        }
    )
    provider, _ = make_provider(resolver, recorder)

    markets = await provider.list_tennis_moneylines()

    assert len(markets) == 1
    assert [outcome.player_id for outcome in markets[0].outcomes] == [
        "ply_alpha",
        "ply_beta",
    ]


async def test_unresolved_outcome_skips_market_with_typed_reason(resolver):
    events = _fixture("events_tennis.json")
    events[0]["markets"][0]["outcomes"] = json.dumps(["Nobody Known", "Beta Two"])
    recorder = RecordingTransport(
        overrides={
            "gamma-api.polymarket.com/events": httpx.Response(
                200, json={"events": events, "next_cursor": None}
            ),
        }
    )
    provider, _ = make_provider(resolver, recorder)

    markets = await provider.list_tennis_moneylines()

    assert markets == ()
    assert any(skip.reason == "unresolved_player" for skip in provider.skipped)


async def test_keyset_listing_keeps_unknown_doubles_and_reads_every_page(resolver):
    first_event = _fixture("events_tennis.json")[0]
    first_event["markets"][0]["outcomes"] = json.dumps(
        ["Team A / Team B", "Team C / Team D"]
    )
    second_event = _fixture("events_tennis.json")[0]
    second_event["id"] = "900009"
    second_event["markets"][0]["conditionId"] = CONDITION_A1[:-2] + "a9"
    second_event["markets"][0]["clobTokenIds"] = json.dumps(
        ["990001112223334445559", "990001112223334445560"]
    )
    calls: list[httpx.Request] = []

    def page_response(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.params.get("after_cursor") == "cursor-two":
            return httpx.Response(
                200, json={"events": [second_event], "next_cursor": None}
            )
        return httpx.Response(
            200, json={"events": [first_event], "next_cursor": "cursor-two"}
        )

    recorder = RecordingTransport(
        overrides={
            "gamma-api.polymarket.com/events/keyset": page_response,
        }
    )
    provider, recorder = make_provider(resolver, recorder)

    scan = await provider.list_tennis_market_listings()

    assert scan.complete is True
    assert len(scan.listings) == 2
    doubles, singles = scan.listings
    assert doubles.outcome_names == ("Team A / Team B", "Team C / Team D")
    assert doubles.outcome_player_ids == (None, None)
    assert doubles.to_market() is None
    assert singles.outcome_names == ("Alpha One", "Beta Two")
    assert singles.to_market() is not None
    assert len(calls) == 2
    assert calls[0].url.params["tag_id"] == "42"
    assert calls[0].url.params["closed"] == "false"
    assert calls[1].url.params["after_cursor"] == "cursor-two"
    public = json.dumps(doubles.model_dump(mode="json"))
    assert CONDITION_A1 not in public
    assert TOKEN_A not in public and TOKEN_B not in public


async def test_keyset_listing_rejects_repeated_cursor(resolver):
    event = _fixture("events_tennis.json")[0]
    recorder = RecordingTransport(
        overrides={
            "gamma-api.polymarket.com/events/keyset": lambda _request: httpx.Response(
                200, json={"events": [event], "next_cursor": "same-cursor"}
            ),
        }
    )
    provider, _ = make_provider(resolver, recorder)

    with pytest.raises(AppError) as error:
        await provider.list_tennis_market_listings()

    assert error.value.code == "provider_invalid_response"


async def test_keyset_listing_rejects_malformed_page(resolver):
    recorder = RecordingTransport(
        overrides={
            "gamma-api.polymarket.com/events/keyset": httpx.Response(
                200, json={"items": [], "next_cursor": None}
            ),
        }
    )
    provider, _ = make_provider(resolver, recorder)

    with pytest.raises(AppError) as error:
        await provider.list_tennis_market_listings()

    assert error.value.code == "provider_invalid_response"


# ---------------------------------------------------------------------------
# Market / book / metadata reads
# ---------------------------------------------------------------------------


async def test_get_market_round_trips_canonical_shape(resolver):
    provider, _ = make_provider(resolver)

    market = await provider.get_market(INTERNAL_MARKET_ID)

    assert market.id == INTERNAL_MARKET_ID
    assert market.question == "Alpha One vs. Beta Two: Match Winner"
    assert market.status is MarketStatus.OPEN


async def test_get_market_unknown_internal_id_raises_not_found(resolver):
    provider, _ = make_provider(resolver)
    with pytest.raises(AppError) as error:
        await provider.get_market("mkt_missing")
    assert error.value.code == "not_found"


async def test_get_order_book_normalizes_both_independent_sides(resolver):
    provider, _ = make_provider(resolver)

    book = await provider.get_order_book(INTERNAL_MARKET_ID)

    assert book.market_id == INTERNAL_MARKET_ID
    assert book.sequence == 0
    first, second = book.books
    assert first.outcome_player_id == "ply_alpha"
    assert second.outcome_player_id == "ply_beta"
    # Canonical ordering: bids strictly descending, asks strictly ascending.
    assert [level.price for level in first.bids] == [Decimal("0.55"), Decimal("0.5")]
    assert [level.price for level in first.asks] == [Decimal("0.57"), Decimal("0.6")]
    assert [level.price for level in second.asks] == [Decimal("0.45"), Decimal("0.47")]
    assert book.provider_timestamp == datetime.fromtimestamp(
        1789999201000 / 1000, tz=UTC
    )
    # Deterministic combined hash, no raw provider hash format required.
    again = await provider.get_order_book(INTERNAL_MARKET_ID)
    assert again.book_hash == book.book_hash
    assert book.book_hash != ""


async def test_get_order_book_rejects_duplicate_levels(resolver):
    broken_book = _fixture("book_outcome_a.json")
    broken_book["bids"] = [
        {"price": "0.55", "size": "200"},
        {"price": "0.55", "size": "100"},
    ]
    recorder = RecordingTransport(
        overrides={
            "clob.polymarket.com/book": httpx.Response(200, json=broken_book),
        }
    )
    provider, _ = make_provider(resolver, recorder)

    with pytest.raises(AppError) as error:
        await provider.get_order_book(INTERNAL_MARKET_ID)
    assert error.value.code == "provider_invalid_response"


async def test_execution_metadata_reads_dynamic_tick_fee_delay_values(resolver):
    provider, _ = make_provider(resolver)

    metadata = await provider.get_execution_metadata(INTERNAL_MARKET_ID)

    assert metadata.market_id == INTERNAL_MARKET_ID
    assert metadata.tick_size == Decimal("0.01")
    assert metadata.min_order_size == Decimal("5")
    # fee-rate endpoint (250 bps) takes precedence over the static schedule.
    assert metadata.fee_rate == Decimal("0.025")
    assert metadata.fee_exponent == Decimal("2")
    assert metadata.taker_only is True
    assert metadata.maker_base_fee == Decimal("0")
    assert metadata.taker_base_fee == Decimal("0")
    assert metadata.sports_delay_seconds == 12
    assert metadata.game_start_time == datetime(2026, 9, 20, 12, 0, tzinfo=UTC)


async def test_execution_metadata_falls_back_to_fee_schedule(resolver):
    recorder = RecordingTransport(
        overrides={
            "clob.polymarket.com/fee-rate": httpx.Response(404, json={}),
        }
    )
    provider, _ = make_provider(resolver, recorder)

    metadata = await provider.get_execution_metadata(INTERNAL_MARKET_ID)

    assert metadata.fee_rate == Decimal("0.02")


# ---------------------------------------------------------------------------
# Rules and resolution
# ---------------------------------------------------------------------------


async def test_rules_snapshot_is_hashed_and_changed_rules_differ(resolver):
    provider, _ = make_provider(resolver)

    rules = await provider.get_rules(INTERNAL_MARKET_ID)
    assert rules.market_id == INTERNAL_MARKET_ID
    assert rules.resolution_source == "polymarket-uma"
    expected_hash = hashlib.sha256(
        _fixture("gamma_market.json")[0]["rules"].encode("utf-8")
    ).hexdigest()
    assert rules.rules_hash == expected_hash

    changed_recorder = RecordingTransport(
        overrides={
            "gamma-api.polymarket.com/markets": httpx.Response(
                200, json=_fixture("rules_changed.json")
            ),
        }
    )
    changed_provider, _ = make_provider(resolver, changed_recorder)
    changed_rules = await changed_provider.get_rules(INTERNAL_MARKET_ID)
    assert changed_rules.rules_hash != rules.rules_hash


async def test_final_resolution_maps_provider_payouts(resolver):
    recorder = RecordingTransport(
        overrides={
            "gamma-api.polymarket.com/markets": httpx.Response(
                200, json=_fixture("resolution_final.json")
            ),
        }
    )
    provider, _ = make_provider(resolver, recorder)

    resolution = await provider.get_resolution(INTERNAL_MARKET_ID)

    assert resolution is not None
    assert resolution.status is ResolutionStatus.FINAL
    payouts = {
        payout.player_id: payout.payout_per_share for payout in resolution.payouts
    }
    assert payouts == {"ply_alpha": Decimal("1"), "ply_beta": Decimal("0")}
    assert resolution.confirmed_at == datetime(2026, 9, 20, 18, 30, tzinfo=UTC)


async def test_fifty_fifty_resolution_pays_half_per_share(resolver):
    recorder = RecordingTransport(
        overrides={
            "gamma-api.polymarket.com/markets": httpx.Response(
                200, json=_fixture("resolution_fifty_fifty.json")
            ),
        }
    )
    provider, _ = make_provider(resolver, recorder)

    resolution = await provider.get_resolution(INTERNAL_MARKET_ID)

    assert resolution is not None
    assert resolution.status is ResolutionStatus.FINAL
    payouts = {
        payout.player_id: payout.payout_per_share for payout in resolution.payouts
    }
    assert payouts == {"ply_alpha": Decimal("0.5"), "ply_beta": Decimal("0.5")}


async def test_disputed_resolution_stays_unpaid(resolver):
    recorder = RecordingTransport(
        overrides={
            "gamma-api.polymarket.com/markets": httpx.Response(
                200, json=_fixture("resolution_disputed.json")
            ),
        }
    )
    provider, _ = make_provider(resolver, recorder)

    resolution = await provider.get_resolution(INTERNAL_MARKET_ID)

    assert resolution is not None
    assert resolution.status is ResolutionStatus.DISPUTED
    assert resolution.payouts == ()
    assert resolution.confirmed_at is None


async def test_open_market_resolution_is_pending(resolver):
    provider, _ = make_provider(resolver)

    resolution = await provider.get_resolution(INTERNAL_MARKET_ID)

    assert resolution is not None
    assert resolution.status is ResolutionStatus.PENDING
    assert resolution.payouts == ()


async def test_missing_market_resolution_returns_none(resolver):
    recorder = RecordingTransport(
        overrides={
            "gamma-api.polymarket.com/markets": httpx.Response(404, json={}),
        }
    )
    provider, _ = make_provider(resolver, recorder)

    assert await provider.get_resolution(INTERNAL_MARKET_ID) is None


# ---------------------------------------------------------------------------
# Error translation and read-only guarantees
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (500, "provider_unavailable"),
        (403, "provider_unavailable"),
    ],
)
async def test_http_errors_translate_without_leaking_urls(
    resolver, status_code, expected_code
):
    recorder = RecordingTransport(
        overrides={
            "gamma-api.polymarket.com/events": httpx.Response(status_code, json={}),
        }
    )
    provider, _ = make_provider(resolver, recorder)

    with pytest.raises(AppError) as error:
        await provider.list_tennis_moneylines()
    assert error.value.code == expected_code
    message = str(error.value.message) + json.dumps(error.value.details, default=str)
    assert "http" not in message
    assert CONDITION_A1 not in message


async def test_rate_limited_error_keeps_retry_after(resolver):
    recorder = RecordingTransport(
        overrides={
            "gamma-api.polymarket.com/events": httpx.Response(
                429, json={}, headers={"Retry-After": "7"}
            ),
        }
    )
    provider, _ = make_provider(resolver, recorder)

    with pytest.raises(AppError) as error:
        await provider.list_tennis_moneylines()
    assert error.value.code == "rate_limited"
    assert error.value.details.get("retry_after") == "7"


async def test_malformed_json_translates_to_invalid_response(resolver):
    recorder = RecordingTransport(
        overrides={
            "gamma-api.polymarket.com/events": httpx.Response(
                200, content=b"not-json", headers={"Content-Type": "application/json"}
            ),
        }
    )
    provider, _ = make_provider(resolver, recorder)

    with pytest.raises(AppError) as error:
        await provider.list_tennis_moneylines()
    assert error.value.code == "provider_invalid_response"


async def test_adapter_only_issues_public_get_requests(resolver):
    provider, recorder = make_provider(resolver)

    await provider.list_tennis_moneylines()
    await provider.get_market(INTERNAL_MARKET_ID)
    await provider.get_order_book(INTERNAL_MARKET_ID)
    await provider.get_execution_metadata(INTERNAL_MARKET_ID)
    await provider.get_rules(INTERNAL_MARKET_ID)
    await provider.get_resolution(INTERNAL_MARKET_ID)

    assert recorder.requests, "expected recorded requests"
    public_prefixes = (
        "gamma-api.polymarket.com/tags/",
        "gamma-api.polymarket.com/events",
        "gamma-api.polymarket.com/markets",
        "clob.polymarket.com/clob-markets/",
        "clob.polymarket.com/book",
        "clob.polymarket.com/fee-rate/",
    )
    for request in recorder.requests:
        assert request.method == "GET"
        target = f"{request.url.host}{request.url.path}"
        assert target.startswith(public_prefixes), f"unexpected call: {target}"
        assert "authorization" not in {k.lower() for k in request.headers}
