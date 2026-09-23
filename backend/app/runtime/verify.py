"""Bounded, read-only real-source verification for the local runtime (T80).

`verify_runtime` answers one question honestly: can this machine currently
reach each real source the local runtime depends on? It is *not* a health
dashboard and never fabricates success:

* at most ONE ATP ranking call;
* at most ONE current fixture/catalog call (`get_live_matches`, see below);
* at most ONE subscribed live-match WebSocket attempt, and only when an
  eligible LIVE match exists (otherwise an honest `skipped`/`NO_LIVE_MATCH`);
* at most ONE tennis moneyline discovery call;
* at most ONE book/reconciliation call for a discovered mapped market;
* at most ONE public market WebSocket attempt, and only when an active
  mapped book exists (otherwise an honest `skipped`/`NO_ACTIVE_BOOK`);
* each stream receive wait is bounded to `RECEIVE_TIMEOUT_SECONDS` (45 s);
* `with_llm=True` is the SOLE path that may construct or invoke a real Chat
  client — with `with_llm=False` the LLM factory is never called at all.

Catalog call choice: `get_fixtures` filters to SCHEDULED matches only, so it
can never establish WebSocket eligibility; `get_live_matches` is therefore
the single tennis catalog call — it proves REST connectivity and yields the
LIVE matches the WebSocket check needs.

The verifier is read-only with respect to runtime state: it never writes
match fixtures, never sends orders, never touches the paper ledger. The only
persistence it may perform is the idempotent identity/market mapping that
every real provider read already performs (same as the daemon and the
existing live gates).

Outcomes aggregate names, statuses and stable reason codes only. Provider
IDs, keys, URLs-with-query and payloads never appear: failures are mapped
through `stable_reason_code`, which is derived from the exception class or
its `code` attribute, never from message text.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from app.domain import FrozenModel, MatchStatus
from app.players.models import Tour
from app.runtime.health import stable_reason_code
from app.runtime.models import LiveLocalConfigurationError

#: Hard bound on every external receive wait, per the T80 contract.
RECEIVE_TIMEOUT_SECONDS = 45.0

TENNIS_PROVIDER_NAME = "api_tennis"

# Stable skip reasons for honest quiet windows / missing targets.
NO_LIVE_MATCH = "NO_LIVE_MATCH"
NO_EXTERNAL_ID = "NO_EXTERNAL_ID"
NO_MAPPED_MARKET = "NO_MAPPED_MARKET"
NO_ACTIVE_BOOK = "NO_ACTIVE_BOOK"
NOT_REQUESTED = "NOT_REQUESTED"
LLM_NOT_CONFIGURED = "LLM_NOT_CONFIGURED"
RECEIVE_TIMEOUT = "RECEIVE_TIMEOUT"
STREAM_ENDED = "STREAM_ENDED"
EMPTY_RESULT = "EMPTY_RESULT"
BOOK_INCOMPLETE = "BOOK_INCOMPLETE"
NO_QUOTE_TARGETS = "NO_QUOTE_TARGETS"

#: The coverage lane is verified with at most this many discovered markets,
#: so one batch request bounds the whole check (T89).
QUOTE_BATCH_MARKETS = 2


class VerifyOutcome(FrozenModel):
    """One aggregate verification result: name, honest status, stable reason.

    Never carries provider identifiers, URLs, payloads or secrets.
    """

    name: str
    status: Literal["passed", "failed", "skipped"]
    reason_code: str | None = None


def _passed(name: str) -> VerifyOutcome:
    return VerifyOutcome(name=name, status="passed")


def _skipped(name: str, reason_code: str) -> VerifyOutcome:
    return VerifyOutcome(name=name, status="skipped", reason_code=reason_code)


def _failed(name: str, reason_code: str) -> VerifyOutcome:
    return VerifyOutcome(name=name, status="failed", reason_code=reason_code)


@dataclass(frozen=True)
class VerifyDependencies:
    """Injectable real (or fake) sources for one verification run.

    Fields are consumed structurally: `tennis` must offer `get_rankings` and
    `get_live_matches`; `identities` must offer `external_id`; the feed
    factories return objects offering `stream_match(external_match_id)` /
    `subscribe(asset_ids)` async generators (and an optional `shutdown`);
    `markets` must offer `list_tennis_moneylines` and `get_order_book`;
    `market_token_lookup(market_id)` returns the mapped token-id pair or
    `None`; `llm_factory()` returns a ChatModel-compatible client and is
    called ONLY when `with_llm=True`. `cleanup` holds async release hooks
    run exactly once via `aclose`.
    """

    tennis: Any
    identities: Any
    live_feed_factory: Callable[[], Any]
    markets: Any
    market_token_lookup: Callable[[str], Awaitable[tuple[str, str] | None]]
    market_feed_factory: Callable[[], Any]
    llm_factory: Callable[[], Any] | None = None
    cleanup: tuple[Callable[[], Awaitable[None]], ...] = ()

    def verify_kwargs(self) -> dict[str, Any]:
        return {
            "tennis": self.tennis,
            "identities": self.identities,
            "live_feed_factory": self.live_feed_factory,
            "markets": self.markets,
            "market_token_lookup": self.market_token_lookup,
            "market_feed_factory": self.market_feed_factory,
            "llm_factory": self.llm_factory,
        }

    async def aclose(self) -> None:
        """Release every owned resource exactly once; never raises."""
        for release in self.cleanup:
            with contextlib.suppress(Exception):
                await release()


async def _shutdown_quietly(feed: Any) -> None:
    shutdown = getattr(feed, "shutdown", None)
    if shutdown is None:
        return
    with contextlib.suppress(Exception):
        await shutdown()


async def _receive_first(stream: AsyncIterator[Any], timeout: float) -> str:
    """Bounded wait for the first frame: 'frame', 'ended' or 'timeout'.

    Always releases the stream, even on timeout, so a bounded verify never
    leaks a socket or a pending task.
    """
    try:
        async with asyncio.timeout(timeout):
            async for _frame in stream:
                return "frame"
            return "ended"
    except TimeoutError:
        return "timeout"
    finally:
        aclose = getattr(stream, "aclose", None)
        if aclose is not None:
            with contextlib.suppress(Exception):
                await aclose()


async def _check_atp_rankings(tennis: Any) -> VerifyOutcome:
    name = "atp_rankings"
    try:
        entries = await tennis.get_rankings(Tour.ATP)
    except Exception as exc:  # noqa: BLE001 - honest failure, sanitized code
        return _failed(name, stable_reason_code(exc))
    if not entries:
        # Rankings are never legitimately empty: honest skip, never a pass.
        return _skipped(name, EMPTY_RESULT)
    return _passed(name)


async def _check_tennis_catalog(tennis: Any) -> tuple[VerifyOutcome, tuple]:
    name = "tennis_catalog"
    try:
        matches = await tennis.get_live_matches()
    except Exception as exc:  # noqa: BLE001
        return _failed(name, stable_reason_code(exc)), ()
    # A successful catalog call proves REST connectivity even when the
    # window is quiet; downstream checks skip honestly on their own.
    return _passed(name), tuple(matches)


async def _check_tennis_websocket(
    *,
    identities: Any,
    live_feed_factory: Callable[[], Any],
    live_matches: tuple,
    timeout: float,
) -> VerifyOutcome:
    name = "tennis_websocket"
    match = next(
        (m for m in live_matches if m.status == MatchStatus.LIVE),
        None,
    )
    if match is None:
        return _skipped(name, NO_LIVE_MATCH)
    feed = None
    try:
        external_id = await identities.external_id(
            "match", TENNIS_PROVIDER_NAME, match.id
        )
        if not external_id:
            return _skipped(name, NO_EXTERNAL_ID)
        feed = live_feed_factory()
        result = await _receive_first(feed.stream_match(external_id), timeout)
    except Exception as exc:  # noqa: BLE001
        return _failed(name, stable_reason_code(exc))
    finally:
        if feed is not None:
            await _shutdown_quietly(feed)
    if result == "frame":
        return _passed(name)
    if result == "timeout":
        return _skipped(name, RECEIVE_TIMEOUT)
    return _skipped(name, STREAM_ENDED)


async def _check_market_discovery(markets: Any) -> tuple[VerifyOutcome, tuple]:
    name = "market_discovery"
    try:
        discovered = await markets.list_tennis_moneylines()
    except Exception as exc:  # noqa: BLE001
        return _failed(name, stable_reason_code(exc)), ()
    return _passed(name), tuple(discovered)


async def _check_market_book(markets: Any, market: Any) -> VerifyOutcome:
    name = "market_book"
    try:
        book = await markets.get_order_book(market.id)
    except Exception as exc:  # noqa: BLE001
        return _failed(name, stable_reason_code(exc))
    if len(getattr(book, "books", ())) != 2:
        return _failed(name, BOOK_INCOMPLETE)
    return _passed(name)


async def _check_market_websocket(
    *,
    market_token_lookup: Callable[[str], Awaitable[tuple[str, str] | None]],
    market_feed_factory: Callable[[], Any],
    market: Any,
    timeout: float,
) -> VerifyOutcome:
    name = "market_websocket"
    feed = None
    try:
        token_ids = await market_token_lookup(market.id)
        if not token_ids:
            return _skipped(name, NO_ACTIVE_BOOK)
        feed = market_feed_factory()
        result = await _receive_first(feed.subscribe(tuple(token_ids)), timeout)
    except Exception as exc:  # noqa: BLE001
        return _failed(name, stable_reason_code(exc))
    finally:
        if feed is not None:
            await _shutdown_quietly(feed)
    if result == "frame":
        return _passed(name)
    if result == "timeout":
        return _skipped(name, RECEIVE_TIMEOUT)
    return _skipped(name, STREAM_ENDED)


async def _check_market_quote_snapshot(
    *,
    markets: Any,
    discovered: tuple,
    quote_batch_lookup: Callable[[str], Awaitable[tuple[str, str] | None]],
) -> VerifyOutcome:
    """One bounded batch quote request for the coverage lane (T89).

    At most `QUOTE_BATCH_MARKETS` discovered markets contribute their two
    private tokens; a quiet or unmapped catalog skips honestly instead of
    fabricating a quote, and the raw response never leaves the provider.
    """
    name = "market_quote_snapshot"
    token_ids: list[str] = []
    for market in discovered[:QUOTE_BATCH_MARKETS]:
        pair = await quote_batch_lookup(market.id)
        if pair:
            token_ids.extend(token for token in pair if token)
    if not token_ids:
        return _skipped(name, NO_QUOTE_TARGETS)
    try:
        batch = await markets.get_order_books(tuple(token_ids))
    except Exception as exc:  # noqa: BLE001 - honest failure, sanitized code
        return _failed(name, stable_reason_code(exc))
    if not getattr(batch, "books", None):
        return _skipped(name, EMPTY_RESULT)
    return _passed(name)


async def _check_llm(
    *, with_llm: bool, llm_factory: Callable[[], Any] | None
) -> VerifyOutcome:
    name = "llm_chat"
    if not with_llm:
        # The factory is never even constructed without the explicit flag.
        return _skipped(name, NOT_REQUESTED)
    if llm_factory is None:
        return _skipped(name, LLM_NOT_CONFIGURED)
    try:
        client = llm_factory()
        await client.choose([{"role": "user", "content": "Reply with OK."}], [])
    except Exception as exc:  # noqa: BLE001
        return _failed(name, stable_reason_code(exc))
    return _passed(name)


async def verify_runtime(
    *,
    with_llm: bool,
    tennis: Any,
    identities: Any,
    live_feed_factory: Callable[[], Any],
    markets: Any,
    market_token_lookup: Callable[[str], Awaitable[tuple[str, str] | None]],
    market_feed_factory: Callable[[], Any],
    llm_factory: Callable[[], Any] | None = None,
    receive_timeout_seconds: float = RECEIVE_TIMEOUT_SECONDS,
) -> tuple[VerifyOutcome, ...]:
    """Run the bounded read-only verification; honest passed/failed/skipped.

    Sources are checked sequentially so the call bounds are trivially
    enforceable. A quiet external window can only ever produce `skipped`
    with a stable reason code — never `passed`.
    """
    rankings = await _check_atp_rankings(tennis)
    catalog, live_matches = await _check_tennis_catalog(tennis)
    tennis_ws = await _check_tennis_websocket(
        identities=identities,
        live_feed_factory=live_feed_factory,
        live_matches=live_matches,
        timeout=receive_timeout_seconds,
    )
    discovery, discovered = await _check_market_discovery(markets)
    if discovered:
        market = discovered[0]
        book = await _check_market_book(markets, market)
        if book.status == "passed":
            market_ws = await _check_market_websocket(
                market_token_lookup=market_token_lookup,
                market_feed_factory=market_feed_factory,
                market=market,
                timeout=receive_timeout_seconds,
            )
        else:
            market_ws = _skipped("market_websocket", NO_ACTIVE_BOOK)
    else:
        book = _skipped("market_book", NO_MAPPED_MARKET)
        market_ws = _skipped("market_websocket", NO_ACTIVE_BOOK)
    quote_snapshot = await _check_market_quote_snapshot(
        markets=markets,
        discovered=discovered,
        quote_batch_lookup=market_token_lookup,
    )
    llm = await _check_llm(with_llm=with_llm, llm_factory=llm_factory)
    return (
        rankings,
        catalog,
        tennis_ws,
        discovery,
        book,
        market_ws,
        quote_snapshot,
        llm,
    )


def build_verify_dependencies(settings: Any) -> VerifyDependencies:
    """Build real adapters from validated root-`.env` settings.

    Construction performs no I/O (engines and HTTP clients are lazy). The
    caller owns `aclose()`. Heavy imports stay function-local so importing
    this module in deterministic tests remains cheap.
    """
    import httpx

    from app.chat.client import OpenAICompatibleChatModel
    from app.markets.live import PolymarketMarketFeed
    from app.markets.polymarket import PolymarketProvider
    from app.persistence.database import Database
    from app.persistence.market_repositories import MarketRepository
    from app.persistence.player_directory import PostgresPlayerDirectoryRepository
    from app.persistence.repositories import PostgresIdentityRepository
    from app.players.resolver import PlayerResolver
    from app.providers.api_tennis import ApiTennisProvider
    from app.providers.api_tennis_live import ApiTennisLiveFeedProvider
    from app.runtime.config import require_live_local

    live = require_live_local(settings)
    api_key = settings.api_tennis_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        # Defensive: require_live_local already guarantees the credential.
        raise LiveLocalConfigurationError("LOCAL_CREDENTIALS_MISSING")

    def clock() -> datetime:
        return datetime.now(UTC)

    database = Database(live.database_url)
    api_client = httpx.AsyncClient(
        base_url=settings.api_tennis_base_url, timeout=15.0, trust_env=False
    )
    identities = PostgresIdentityRepository(database)
    directory = PostgresPlayerDirectoryRepository(database)
    tennis = ApiTennisProvider(
        client=api_client,
        identities=identities,
        api_key=api_key.get_secret_value(),
        now=clock,
        directory=directory,
    )
    resolver = PlayerResolver(directory)
    markets_repo = MarketRepository(database)

    async def register_market(
        provider_event_id: str, condition_id: str, token_ids: tuple[str, str]
    ) -> str:
        # Idempotent mapping registration — identical to the daemon's read
        # path; verify itself never writes fixtures, orders or ledger state.
        return await markets_repo.get_or_create_market_id(
            provider="polymarket",
            provider_event_id=provider_event_id,
            condition_id=condition_id,
            token_ids=token_ids,
        )

    async def external_lookup(market_id: str) -> Any:
        return await markets_repo.get_external_id(market_id)

    market_provider = PolymarketProvider(
        gamma_base_url=settings.polymarket_gamma_base_url,
        clob_base_url=settings.polymarket_clob_base_url,
        resolver=resolver,
        registrar=register_market,
        external_lookup=external_lookup,
    )

    async def token_lookup(market_id: str) -> tuple[str, str] | None:
        external = await markets_repo.get_external_id(market_id)
        if external is None:
            return None
        return external.token_ids

    def live_feed_factory() -> Any:
        return ApiTennisLiveFeedProvider(
            api_key=api_key.get_secret_value(),
            identities=identities,
            now=clock,
            base_url=settings.api_tennis_ws_url,
        )

    market_feed = PolymarketMarketFeed(ws_url=settings.polymarket_ws_url)

    def llm_factory() -> Any:
        if settings.llm_mode != "openai_compatible":
            raise LiveLocalConfigurationError(LLM_NOT_CONFIGURED)
        llm_api_key = settings.llm_api_key
        if llm_api_key is None or not settings.llm_base_url:
            raise LiveLocalConfigurationError(LLM_NOT_CONFIGURED)
        return OpenAICompatibleChatModel(
            api_key=llm_api_key.get_secret_value(),
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    return VerifyDependencies(
        tennis=tennis,
        identities=identities,
        live_feed_factory=live_feed_factory,
        markets=market_provider,
        market_token_lookup=token_lookup,
        market_feed_factory=lambda: market_feed,
        llm_factory=llm_factory,
        cleanup=(
            api_client.aclose,
            market_provider.aclose,
            market_feed.shutdown,
            database.dispose,
        ),
    )


__all__ = [
    "RECEIVE_TIMEOUT_SECONDS",
    "VerifyDependencies",
    "VerifyOutcome",
    "build_verify_dependencies",
    "verify_runtime",
]
