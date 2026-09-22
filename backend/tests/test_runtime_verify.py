"""Deterministic tests for the T80 bounded, read-only local runtime verifier.

These tests use fakes only — zero external calls, zero quota. They pin the
honest semantics required by the brief:

* a quiet external window yields ``skipped`` with a stable reason code,
  never ``passed``;
* ``with_llm=False`` constructs zero LLM clients (spy-proven);
* every source is called at most once per verify run;
* each receive wait is bounded (45 s constant, injectable for tests);
* outcomes aggregate names/status/reason codes only — provider IDs, keys,
  URLs-with-query and payloads never leak.
"""

import asyncio
import io
import json
import re
import time
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.chat.models import ModelTurn
from app.domain import (
    CircuitTier,
    DataFreshness,
    Discipline,
    Gender,
    Match,
    MatchStatus,
    Player,
    Tournament,
)
from app.errors import AppError
from app.markets.models import Market, MarketOutcome, MarketStatus
from app.markets.reducer import RawMarketEvent
from app.providers.base import ProviderLiveEnvelope
from app.realtime.models import FeedDisconnected
from app.runtime.cli import (
    build_parser,
    format_verify_results,
    run_verify,
    verify_exit_code,
)
from app.runtime.launcher import EXIT_FAILURE, EXIT_OK, EXIT_PRECONDITION
from app.runtime.models import LiveLocalConfigurationError
from app.runtime.verify import (
    RECEIVE_TIMEOUT_SECONDS,
    VerifyDependencies,
    VerifyOutcome,
    verify_runtime,
)

EXPECTED_NAMES = (
    "atp_rankings",
    "tennis_catalog",
    "tennis_websocket",
    "market_discovery",
    "market_book",
    "market_websocket",
    "market_quote_snapshot",
    "llm_chat",
)

REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Planted provider material that must never appear in outcomes or printed
# results, even when the underlying exception messages contain it.
SECRET_FRAGMENTS = (
    "APIkey=SECRETKEYVALUE",
    "wss://stream.api-tennis.example/v2",
    "0xabc123def4567890abc123def4567890",
    "9900112233445566778899",
    "sk-llm-secret-value",
)


def _now() -> datetime:
    return datetime.now(UTC)


def make_live_match(match_id: str = "mat_live_one") -> Match:
    return Match(
        id=match_id,
        status=MatchStatus.LIVE,
        players=(
            Player(id="ply_a", name="Alpha One"),
            Player(id="ply_b", name="Beta Two"),
        ),
        tournament=Tournament(
            id="trn_live",
            name="Live Open",
            tour="atp",
            circuit=CircuitTier.ATP,
            gender=Gender.MEN,
            discipline=Discipline.SINGLES,
        ),
        scheduled_at=_now(),
        freshness=DataFreshness(provider="api_tennis", observed_at=_now()),
    )


def make_market(market_id: str = "mkt_live_one") -> Market:
    return Market(
        id=market_id,
        question="Alpha One vs. Beta Two",
        outcomes=(
            MarketOutcome(player_id="ply_a", name="Alpha One"),
            MarketOutcome(player_id="ply_b", name="Beta Two"),
        ),
        status=MarketStatus.OPEN,
        rules_version=1,
        match_id="mat_live_one",
        provider="polymarket",
        observed_at=_now(),
    )


def make_envelope() -> ProviderLiveEnvelope:
    return ProviderLiveEnvelope(
        external_match_id="ext-1",
        provider="api_tennis",
        channel="livescore",
        kind="score",
        received_at=_now(),
        payload={},
    )


def make_book_event() -> RawMarketEvent:
    return RawMarketEvent(
        event_type="book",
        asset_id="t1",
        payload={},
        received_at=_now(),
    )


def make_book() -> SimpleNamespace:
    return SimpleNamespace(books=(SimpleNamespace(), SimpleNamespace()))


class RecordingTennis:
    """Fake API-Tennis REST provider with call counters."""

    def __init__(
        self, *, rankings=None, live=None, rankings_error=None, live_error=None
    ):
        self.rankings_calls = 0
        self.live_calls = 0
        self.tours: list = []
        self._rankings = (
            (SimpleNamespace(rank=1),) if rankings is None else tuple(rankings)
        )
        self._live = [] if live is None else list(live)
        self._rankings_error = rankings_error
        self._live_error = live_error

    async def get_rankings(self, tour):
        self.rankings_calls += 1
        self.tours.append(tour)
        if self._rankings_error is not None:
            raise self._rankings_error
        return self._rankings

    async def get_live_matches(self, *, player_id=None):
        self.live_calls += 1
        if self._live_error is not None:
            raise self._live_error
        return list(self._live)


class RecordingIdentities:
    def __init__(self, mapping=None):
        self.mapping = dict(mapping or {})
        self.calls = 0
        self.last = None

    async def external_id(self, entity, provider, internal_id):
        self.calls += 1
        self.last = (entity, provider, internal_id)
        return self.mapping.get(internal_id)


class RecordingTokenLookup:
    def __init__(self, mapping=None, error=None):
        self.mapping = dict(mapping or {})
        self.calls = 0
        self.error = error

    async def __call__(self, market_id):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.mapping.get(market_id)


class ScriptedTennisFeed:
    """Fake live-feed provider: yields ``frames`` frames then blocks forever.

    ``frames=0, block=False`` models a stream that ends without any frame.
    """

    def __init__(self, *, frames=1, error=None, block=True):
        self.frames = frames
        self.error = error
        self.block = block
        self.constructed_streams = 0
        self.closed_streams = 0
        self.shutdown_calls = 0
        self.subscribed_ids: list[str] = []

    def stream_match(self, external_match_id):
        self.constructed_streams += 1
        self.subscribed_ids.append(external_match_id)
        feed = self

        async def generator():
            try:
                if feed.error is not None:
                    raise feed.error
                for _ in range(feed.frames):
                    yield make_envelope()
                if feed.block:
                    await asyncio.sleep(3600)
            finally:
                feed.closed_streams += 1

        return generator()

    async def shutdown(self):
        self.shutdown_calls += 1


class ScriptedMarketFeed:
    def __init__(self, *, frames=1, error=None, block=True):
        self.frames = frames
        self.error = error
        self.block = block
        self.constructed_streams = 0
        self.closed_streams = 0
        self.shutdown_calls = 0
        self.subscribed_assets: list = []

    def subscribe(self, asset_ids):
        self.constructed_streams += 1
        self.subscribed_assets.append(tuple(asset_ids))
        feed = self

        async def generator():
            try:
                if feed.error is not None:
                    raise feed.error
                for _ in range(feed.frames):
                    yield make_book_event()
                if feed.block:
                    await asyncio.sleep(3600)
            finally:
                feed.closed_streams += 1

        return generator()

    async def shutdown(self):
        self.shutdown_calls += 1


class RecordingMarkets:
    def __init__(
        self, *, markets=None, book=None, discovery_error=None, book_error=None
    ):
        self.discovery_calls = 0
        self.book_calls = 0
        self.book_market_ids: list = []
        self._markets = (make_market(),) if markets is None else tuple(markets)
        self._book = book if book is not None else make_book()
        self._discovery_error = discovery_error
        self._book_error = book_error
        self.batch_calls: list[tuple[str, ...]] = []
        self._batch_has_books = True
        self._batch_error = None

    async def list_tennis_moneylines(self):
        self.discovery_calls += 1
        if self._discovery_error is not None:
            raise self._discovery_error
        return self._markets

    async def get_order_book(self, market_id):
        self.book_calls += 1
        self.book_market_ids.append(market_id)
        if self._book_error is not None:
            raise self._book_error
        return self._book

    async def get_order_books(self, token_ids):
        self.batch_calls.append(tuple(token_ids))
        if self._batch_error is not None:
            raise self._batch_error
        books = (
            {
                token: SimpleNamespace(bids=(SimpleNamespace(),), asks=())
                for token in token_ids
            }
            if self._batch_has_books
            else {}
        )
        return SimpleNamespace(books=books)


class SpyLlm:
    def __init__(self, *, turn=None, error=None):
        self.calls = 0
        self.messages = None
        self._turn = turn if turn is not None else ModelTurn()
        self._error = error

    async def choose(self, messages, tools, *, parallel_tool_calls=False):
        self.calls += 1
        self.messages = messages
        if self._error is not None:
            raise self._error
        return self._turn


class SpyLlmFactory:
    def __init__(self, llm):
        self.llm = llm
        self.constructions = 0

    def __call__(self):
        self.constructions += 1
        return self.llm


def make_dependencies(
    *,
    tennis=None,
    identities=None,
    live_feed=None,
    markets=None,
    token_lookup=None,
    market_feed=None,
    llm_factory=None,
) -> dict:
    live_feed_instance = live_feed if live_feed is not None else ScriptedTennisFeed()
    market_feed_instance = (
        market_feed if market_feed is not None else ScriptedMarketFeed()
    )
    return {
        "tennis": tennis
        if tennis is not None
        else RecordingTennis(live=[make_live_match()]),
        "identities": identities
        if identities is not None
        else RecordingIdentities({"mat_live_one": "ext-1"}),
        "live_feed_factory": lambda: live_feed_instance,
        "markets": markets if markets is not None else RecordingMarkets(),
        "market_token_lookup": (
            token_lookup
            if token_lookup is not None
            else RecordingTokenLookup({"mkt_live_one": ("t1", "t2")})
        ),
        "market_feed_factory": lambda: market_feed_instance,
        "llm_factory": llm_factory,
    }


def outcome_by_name(outcomes, name) -> VerifyOutcome:
    by_name = {outcome.name: outcome for outcome in outcomes}
    return by_name[name]


# ---------------------------------------------------------------------------
# verify_runtime semantics
# ---------------------------------------------------------------------------


async def test_verify_reports_no_live_match_as_honest_skip_not_pass():
    tennis = RecordingTennis(live=[])
    feed = ScriptedTennisFeed()
    outcomes = await verify_runtime(
        with_llm=False, **make_dependencies(tennis=tennis, live_feed=feed)
    )
    assert tuple(outcome.name for outcome in outcomes) == EXPECTED_NAMES
    websocket = outcome_by_name(outcomes, "tennis_websocket")
    assert websocket.status == "skipped"
    assert websocket.reason_code == "NO_LIVE_MATCH"
    # An empty catalog is still a successful connectivity check, never a pass
    # for the WebSocket source.
    assert outcome_by_name(outcomes, "tennis_catalog").status == "passed"
    assert feed.constructed_streams == 0
    assert all(outcome.status != "failed" for outcome in outcomes)


async def test_verify_never_constructs_or_calls_llm_without_flag():
    llm = SpyLlm()
    factory = SpyLlmFactory(llm)
    outcomes = await verify_runtime(
        with_llm=False, **make_dependencies(llm_factory=factory)
    )
    assert factory.constructions == 0
    assert llm.calls == 0
    outcome = outcome_by_name(outcomes, "llm_chat")
    assert outcome.status == "skipped"
    assert outcome.reason_code == "NOT_REQUESTED"


async def test_verify_with_llm_constructs_one_client_and_calls_it_once():
    llm = SpyLlm()
    factory = SpyLlmFactory(llm)
    outcomes = await verify_runtime(
        with_llm=True, **make_dependencies(llm_factory=factory)
    )
    assert factory.constructions == 1
    assert llm.calls == 1
    assert outcome_by_name(outcomes, "llm_chat").status == "passed"


async def test_verify_llm_failure_reports_failed_with_stable_reason():
    llm = SpyLlm(
        error=AppError(
            "llm_unavailable",
            "LLM request failed for sk-llm-secret-value",
            503,
        )
    )
    outcomes = await verify_runtime(
        with_llm=True, **make_dependencies(llm_factory=SpyLlmFactory(llm))
    )
    outcome = outcome_by_name(outcomes, "llm_chat")
    assert outcome.status == "failed"
    assert outcome.reason_code == "LLM_UNAVAILABLE"


async def test_verify_calls_each_source_at_most_once_on_happy_path():
    tennis = RecordingTennis(live=[make_live_match()])
    identities = RecordingIdentities({"mat_live_one": "ext-1"})
    live_feed = ScriptedTennisFeed(frames=1)
    markets = RecordingMarkets(markets=[make_market()], book=make_book())
    token_lookup = RecordingTokenLookup({"mkt_live_one": ("t1", "t2")})
    market_feed = ScriptedMarketFeed(frames=1)
    outcomes = await verify_runtime(
        with_llm=False,
        **make_dependencies(
            tennis=tennis,
            identities=identities,
            live_feed=live_feed,
            markets=markets,
            token_lookup=token_lookup,
            market_feed=market_feed,
        ),
    )
    assert tennis.rankings_calls == 1
    assert tennis.live_calls == 1
    assert live_feed.constructed_streams == 1
    assert markets.discovery_calls == 1
    assert markets.book_calls == 1
    assert len(markets.batch_calls) == 1  # one bounded batch for the quote lane
    # The private token mapping is a local read, not a provider call: the
    # WebSocket check and the coverage batch each read it once.
    assert token_lookup.calls == 2
    assert market_feed.constructed_streams == 1
    assert identities.last == ("match", "api_tennis", "mat_live_one")
    assert market_feed.subscribed_assets == [("t1", "t2")]
    by_name = {outcome.name: outcome.status for outcome in outcomes}
    assert by_name == {
        "atp_rankings": "passed",
        "tennis_catalog": "passed",
        "tennis_websocket": "passed",
        "market_discovery": "passed",
        "market_book": "passed",
        "market_websocket": "passed",
        "market_quote_snapshot": "passed",
        "llm_chat": "skipped",
    }


async def test_verify_skips_market_sources_without_mapped_market():
    markets = RecordingMarkets(markets=[])
    market_feed = ScriptedMarketFeed()
    token_lookup = RecordingTokenLookup()
    outcomes = await verify_runtime(
        with_llm=False,
        **make_dependencies(
            markets=markets, token_lookup=token_lookup, market_feed=market_feed
        ),
    )
    assert markets.discovery_calls == 1
    assert markets.book_calls == 0
    book = outcome_by_name(outcomes, "market_book")
    assert book.status == "skipped"
    assert book.reason_code == "NO_MAPPED_MARKET"
    websocket = outcome_by_name(outcomes, "market_websocket")
    assert websocket.status == "skipped"
    assert websocket.reason_code == "NO_ACTIVE_BOOK"
    assert market_feed.constructed_streams == 0
    assert token_lookup.calls == 0
    assert outcome_by_name(outcomes, "market_discovery").status == "passed"


async def test_verify_market_websocket_skipped_when_book_unavailable():
    markets = RecordingMarkets(book_error=AppError("not_found", "book 0xabc gone", 404))
    market_feed = ScriptedMarketFeed()
    outcomes = await verify_runtime(
        with_llm=False,
        **make_dependencies(markets=markets, market_feed=market_feed),
    )
    book = outcome_by_name(outcomes, "market_book")
    assert book.status == "failed"
    assert book.reason_code == "NOT_FOUND"
    websocket = outcome_by_name(outcomes, "market_websocket")
    assert websocket.status == "skipped"
    assert websocket.reason_code == "NO_ACTIVE_BOOK"
    assert market_feed.constructed_streams == 0


async def test_verify_book_with_wrong_side_count_fails_closed():
    markets = RecordingMarkets(
        book=SimpleNamespace(books=(SimpleNamespace(),)),
    )
    outcomes = await verify_runtime(
        with_llm=False, **make_dependencies(markets=markets)
    )
    book = outcome_by_name(outcomes, "market_book")
    assert book.status == "failed"
    assert book.reason_code == "BOOK_INCOMPLETE"
    assert outcome_by_name(outcomes, "market_websocket").status == "skipped"


async def test_verify_missing_token_ids_skips_market_websocket():
    token_lookup = RecordingTokenLookup({})  # registered market, no token ids
    market_feed = ScriptedMarketFeed()
    outcomes = await verify_runtime(
        with_llm=False,
        **make_dependencies(token_lookup=token_lookup, market_feed=market_feed),
    )
    websocket = outcome_by_name(outcomes, "market_websocket")
    assert websocket.status == "skipped"
    assert websocket.reason_code == "NO_ACTIVE_BOOK"
    assert market_feed.constructed_streams == 0


async def test_verify_receive_waits_are_bounded():
    assert RECEIVE_TIMEOUT_SECONDS == 45.0
    tennis = RecordingTennis(live=[make_live_match()])
    live_feed = ScriptedTennisFeed(frames=0, block=True)
    market_feed = ScriptedMarketFeed(frames=0, block=True)
    started = time.monotonic()
    outcomes = await verify_runtime(
        with_llm=False,
        receive_timeout_seconds=0.05,
        **make_dependencies(
            tennis=tennis, live_feed=live_feed, market_feed=market_feed
        ),
    )
    elapsed = time.monotonic() - started
    assert elapsed < 5.0
    for name in ("tennis_websocket", "market_websocket"):
        outcome = outcome_by_name(outcomes, name)
        assert outcome.status == "skipped"
        assert outcome.reason_code == "RECEIVE_TIMEOUT"
    # Bounded waits must still release the underlying streams.
    assert live_feed.closed_streams == 1
    assert market_feed.closed_streams == 1


async def test_verify_connection_failures_report_failed_with_stable_reasons():
    tennis = RecordingTennis(live=[make_live_match()])
    live_feed = ScriptedTennisFeed(
        error=FeedDisconnected(
            "connection to wss://stream.api-tennis.example/v2?APIkey=SECRETKEYVALUE closed"
        )
    )
    market_feed = ScriptedMarketFeed(
        error=RuntimeError("dial 9900112233445566778899 failed")
    )
    outcomes = await verify_runtime(
        with_llm=False,
        receive_timeout_seconds=1.0,
        **make_dependencies(
            tennis=tennis, live_feed=live_feed, market_feed=market_feed
        ),
    )
    websocket = outcome_by_name(outcomes, "tennis_websocket")
    assert websocket.status == "failed"
    assert websocket.reason_code == "FEED_DISCONNECTED"
    market_ws = outcome_by_name(outcomes, "market_websocket")
    assert market_ws.status == "failed"
    assert market_ws.reason_code == "RUNTIME_ERROR"


async def test_verify_rankings_error_fails_only_that_source():
    tennis = RecordingTennis(
        rankings_error=AppError(
            "provider_unavailable",
            "GET https://api.example/v2/rankings?APIkey=SECRETKEYVALUE timed out",
            503,
        ),
        live=[make_live_match()],
    )
    outcomes = await verify_runtime(with_llm=False, **make_dependencies(tennis=tennis))
    rankings = outcome_by_name(outcomes, "atp_rankings")
    assert rankings.status == "failed"
    assert rankings.reason_code == "PROVIDER_UNAVAILABLE"
    # Remaining sources are still exercised.
    assert tennis.live_calls == 1
    assert outcome_by_name(outcomes, "tennis_catalog").status == "passed"
    assert outcome_by_name(outcomes, "tennis_websocket").status == "passed"


async def test_verify_empty_rankings_is_honest_skip():
    tennis = RecordingTennis(rankings=[], live=[make_live_match()])
    outcomes = await verify_runtime(with_llm=False, **make_dependencies(tennis=tennis))
    rankings = outcome_by_name(outcomes, "atp_rankings")
    assert rankings.status == "skipped"
    assert rankings.reason_code == "EMPTY_RESULT"


async def test_verify_missing_external_id_skips_tennis_websocket():
    identities = RecordingIdentities({})  # no mapping for the live match
    live_feed = ScriptedTennisFeed()
    outcomes = await verify_runtime(
        with_llm=False,
        **make_dependencies(identities=identities, live_feed=live_feed),
    )
    websocket = outcome_by_name(outcomes, "tennis_websocket")
    assert websocket.status == "skipped"
    assert websocket.reason_code == "NO_EXTERNAL_ID"
    assert live_feed.constructed_streams == 0


async def test_verify_stream_that_ends_without_frame_is_skipped():
    live_feed = ScriptedTennisFeed(frames=0, block=False)
    market_feed = ScriptedMarketFeed(frames=0, block=False)
    outcomes = await verify_runtime(
        with_llm=False,
        receive_timeout_seconds=1.0,
        **make_dependencies(live_feed=live_feed, market_feed=market_feed),
    )
    for name in ("tennis_websocket", "market_websocket"):
        outcome = outcome_by_name(outcomes, name)
        assert outcome.status == "skipped"
        assert outcome.reason_code == "STREAM_ENDED"


async def test_verify_outcomes_never_leak_provider_material():
    tennis = RecordingTennis(
        rankings_error=RuntimeError(
            "GET https://api.example/rankings?APIkey=SECRETKEYVALUE failed"
        ),
        live=[make_live_match()],
        live_error=None,
    )
    live_feed = ScriptedTennisFeed(
        error=FeedDisconnected("wss://stream.api-tennis.example/v2 dropped")
    )
    markets = RecordingMarkets(
        discovery_error=RuntimeError("gamma 0xabc123def4567890abc123def4567890 refused")
    )
    llm = SpyLlm(error=RuntimeError("bad key sk-llm-secret-value"))
    outcomes = await verify_runtime(
        with_llm=True,
        receive_timeout_seconds=1.0,
        **make_dependencies(
            tennis=tennis,
            live_feed=live_feed,
            markets=markets,
            llm_factory=SpyLlmFactory(llm),
        ),
    )
    blob = json.dumps([outcome.model_dump(mode="json") for outcome in outcomes]).lower()
    rendered = format_verify_results(outcomes).lower()
    for fragment in SECRET_FRAGMENTS:
        assert fragment.lower() not in blob
        assert fragment.lower() not in rendered
    for outcome in outcomes:
        assert outcome.status in {"passed", "failed", "skipped"}
        assert outcome.reason_code is None or REASON_CODE.fullmatch(outcome.reason_code)


async def test_verify_dependencies_aclose_releases_cleanup_once():
    released = []

    async def release():
        released.append(True)

    dependencies = VerifyDependencies(**make_dependencies(), cleanup=(release, release))
    await dependencies.aclose()
    assert released == [True, True]
    kwargs = dependencies.verify_kwargs()
    assert set(kwargs) == {
        "tennis",
        "identities",
        "live_feed_factory",
        "markets",
        "market_token_lookup",
        "market_feed_factory",
        "llm_factory",
    }


# ---------------------------------------------------------------------------
# CLI surface (fakes only — never run against real services here)
# ---------------------------------------------------------------------------


def test_verify_exit_code_mapping():
    passed = VerifyOutcome(name="a", status="passed")
    skipped = VerifyOutcome(name="b", status="skipped", reason_code="NO_LIVE_MATCH")
    failed = VerifyOutcome(name="c", status="failed", reason_code="FEED_DISCONNECTED")
    assert verify_exit_code((passed, passed)) == EXIT_OK
    assert verify_exit_code((passed, skipped)) == EXIT_OK
    assert verify_exit_code((passed, skipped, failed)) == EXIT_FAILURE
    assert verify_exit_code((failed,)) == EXIT_FAILURE


def test_format_verify_results_prints_skips_with_reasons():
    outcomes = (
        VerifyOutcome(name="atp_rankings", status="passed"),
        VerifyOutcome(
            name="tennis_websocket", status="skipped", reason_code="NO_LIVE_MATCH"
        ),
        VerifyOutcome(name="llm_chat", status="failed", reason_code="LLM_UNAVAILABLE"),
    )
    rendered = format_verify_results(outcomes)
    assert "atp_rankings" in rendered
    assert "passed" in rendered
    assert "skipped" in rendered
    assert "NO_LIVE_MATCH" in rendered
    assert "failed" in rendered
    assert "LLM_UNAVAILABLE" in rendered


def test_cli_parser_accepts_verify_with_llm_flag():
    args = build_parser().parse_args(["verify", "--with-llm"])
    assert args.command == "verify"
    assert args.with_llm is True
    assert build_parser().parse_args(["verify"]).with_llm is False


def _fake_outcomes():
    return (
        VerifyOutcome(name="atp_rankings", status="passed"),
        VerifyOutcome(
            name="tennis_websocket", status="skipped", reason_code="NO_LIVE_MATCH"
        ),
    )


def test_run_verify_prints_table_and_returns_zero_for_passed_and_skipped():
    recorded = {}

    async def fake_verifier(*, with_llm, **kwargs):
        recorded["with_llm"] = with_llm
        recorded["kwargs"] = kwargs
        return _fake_outcomes()

    released = []

    async def release():
        released.append(True)

    dependencies = VerifyDependencies(**make_dependencies(), cleanup=(release,))
    out = io.StringIO()
    code = run_verify(
        with_llm=False,
        settings_factory=lambda: object(),
        dependencies_factory=lambda settings: dependencies,
        verifier=fake_verifier,
        out=out,
    )
    assert code == EXIT_OK
    assert recorded["with_llm"] is False
    assert released == [True], "dependencies must be released after verification"
    printed = out.getvalue()
    assert "atp_rankings" in printed
    assert "NO_LIVE_MATCH" in printed
    assert "skipped" in printed.lower()


def test_run_verify_returns_nonzero_when_any_source_failed():
    async def fake_verifier(*, with_llm, **kwargs):
        return (
            VerifyOutcome(name="market_book", status="failed", reason_code="NOT_FOUND"),
        )

    dependencies = VerifyDependencies(**make_dependencies())
    out = io.StringIO()
    code = run_verify(
        with_llm=True,
        settings_factory=lambda: object(),
        dependencies_factory=lambda settings: dependencies,
        verifier=fake_verifier,
        out=out,
    )
    assert code == EXIT_FAILURE
    assert "NOT_FOUND" in out.getvalue()


def test_run_verify_maps_configuration_rejection_to_precondition():
    def reject(settings):
        raise LiveLocalConfigurationError("LOCAL_P3_MODE_INVALID")

    out = io.StringIO()
    code = run_verify(
        with_llm=False,
        settings_factory=lambda: object(),
        dependencies_factory=reject,
        verifier=None,
        out=out,
    )
    assert code == EXIT_PRECONDITION
    assert "LOCAL_P3_MODE_INVALID" in out.getvalue()


def test_run_verify_maps_invalid_settings_to_precondition():
    from pydantic import ValidationError

    def explode():
        raise ValidationError.from_exception_data("SETTINGS_INVALID", [])

    out = io.StringIO()
    code = run_verify(
        with_llm=False,
        settings_factory=explode,
        dependencies_factory=lambda settings: pytest.fail("must not build deps"),
        verifier=None,
        out=out,
    )
    assert code == EXIT_PRECONDITION
    assert "SETTINGS_INVALID" in out.getvalue()


def test_outcome_is_frozen_and_minimal():
    outcome = VerifyOutcome(name="x", status="skipped", reason_code="NO_LIVE_MATCH")
    with pytest.raises(Exception):
        outcome.name = "y"  # type: ignore[misc]
    assert set(outcome.model_dump()) == {"name", "status", "reason_code"}


# ---------------------------------------------------------------------------
# T89: the batch quote lane is verified within bounds and honestly.
# ---------------------------------------------------------------------------


async def test_verify_quote_snapshot_is_bounded_to_two_markets():
    markets = RecordingMarkets(
        markets=(make_market("mkt_1"), make_market("mkt_2"), make_market("mkt_3"))
    )
    token_lookup = RecordingTokenLookup(
        {"mkt_1": ("t1a", "t1b"), "mkt_2": ("t2a", "t2b"), "mkt_3": ("t3a", "t3b")}
    )
    outcomes = await verify_runtime(
        with_llm=False,
        **make_dependencies(
            markets=markets, token_lookup=token_lookup, tennis=RecordingTennis(live=[])
        ),
    )

    assert tuple(outcome.name for outcome in outcomes) == EXPECTED_NAMES
    outcome = outcome_by_name(outcomes, "market_quote_snapshot")
    assert outcome.status == "passed"
    assert len(markets.batch_calls) == 1  # exactly one batch request
    assert markets.batch_calls[0] == ("t1a", "t1b", "t2a", "t2b")
    # One lookup for the market WebSocket check plus at most two for the
    # quote lane: the coverage check never fans out beyond its two markets.
    assert token_lookup.calls <= 3


async def test_verify_quote_snapshot_skips_honestly_without_targets():
    token_lookup = RecordingTokenLookup({})  # no mapped tokens at all
    outcomes = await verify_runtime(
        with_llm=False,
        **make_dependencies(token_lookup=token_lookup),
    )

    outcome = outcome_by_name(outcomes, "market_quote_snapshot")
    assert outcome.status == "skipped"
    assert outcome.reason_code == "NO_QUOTE_TARGETS"


async def test_verify_quote_snapshot_reports_failures_with_stable_codes():
    markets = RecordingMarkets()
    markets._batch_error = AppError("rate_limited", "slow down", 429)
    outcomes = await verify_runtime(
        with_llm=False,
        **make_dependencies(markets=markets),
    )

    outcome = outcome_by_name(outcomes, "market_quote_snapshot")
    assert outcome.status == "failed"
    assert outcome.reason_code == "RATE_LIMITED"


async def test_verify_quote_snapshot_without_books_is_an_honest_skip():
    markets = RecordingMarkets()
    markets._batch_has_books = False
    outcomes = await verify_runtime(
        with_llm=False,
        **make_dependencies(markets=markets),
    )

    outcome = outcome_by_name(outcomes, "market_quote_snapshot")
    assert outcome.status == "skipped"
    assert outcome.reason_code == "EMPTY_RESULT"


async def test_verify_quote_snapshot_never_leaks_provider_material():
    markets = RecordingMarkets()
    outcomes = await verify_runtime(
        with_llm=False,
        **make_dependencies(markets=markets),
    )

    outcome = outcome_by_name(outcomes, "market_quote_snapshot")
    blob = outcome.model_dump_json()
    assert "t1" not in blob and "tok" not in blob and "0x" not in blob
