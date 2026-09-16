"""Opt-in public read-only Polymarket REST smoke gate (T59).

Run with:
    TENNIX_RUN_POLYMARKET_LIVE=1 uv run pytest -m polymarket_live \
        tests/live/test_polymarket_live.py -v

Uses only public Gamma/CLOB read endpoints; no key, wallet or trading
credential exists for this provider. Prints aggregate counts and internal IDs
only. No active tennis moneyline market is an honest dated skip with
discovery counts, never a fabricated pass.
"""

import json
import os
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import text

from app.config import Settings
from app.errors import AppError
from app.markets.polymarket import PolymarketProvider
from app.markets.polymarket_dtos import GammaMarketDto
from app.persistence.database import Database
from app.persistence.player_directory import PostgresPlayerDirectoryRepository
from app.players.resolver import PlayerResolver

pytestmark = pytest.mark.polymarket_live


def _require_enabled() -> Settings:
    if os.environ.get("TENNIX_RUN_POLYMARKET_LIVE") != "1":
        pytest.skip("TENNIX_RUN_POLYMARKET_LIVE not set")
    return Settings(provider_mode="fake", llm_mode="fake")


async def _resolver_from_directory(
    settings: Settings,
) -> tuple[PlayerResolver, Database] | None:
    database = Database(settings.database_url)
    try:
        async with database.engine.connect() as connection:
            await connection.execute(text("SELECT 1 FROM players LIMIT 1"))
    except Exception:
        await database.dispose()
        return None
    return PlayerResolver(PostgresPlayerDirectoryRepository(database)), database


async def test_polymarket_public_readonly_discovery_and_metadata() -> None:
    settings = _require_enabled()
    today = datetime.now(UTC).date().isoformat()

    async with httpx.AsyncClient(
        base_url=settings.polymarket_gamma_base_url, timeout=30.0
    ) as client:
        response = await client.get(
            "/events",
            params={
                "tag_slug": "tennis",
                "active": "true",
                "closed": "false",
                "limit": 100,
            },
        )
    if response.status_code == 429:
        pytest.skip(f"Polymarket public API rate limited on {today}")
    assert response.status_code == 200, f"unexpected status {response.status_code}"
    events = response.json()
    assert isinstance(events, list)

    moneyline_dtos: list[GammaMarketDto] = []
    total_markets = 0
    for raw_event in events:
        if not isinstance(raw_event, dict):
            continue
        for raw_market in raw_event.get("markets", []):
            total_markets += 1
            dto = GammaMarketDto.model_validate(raw_market)
            if (dto.sportsMarketType or "").casefold() != "moneyline":
                continue
            if dto.closed or dto.active is False or dto.acceptingOrders is False:
                continue
            if len(dto.outcome_names()) != 2 or len(dto.token_ids()) != 2:
                continue
            moneyline_dtos.append(dto)

    print(
        f"[polymarket-live {today}] discovery: events={len(events)} "
        f"markets={total_markets} tennis_moneylines={len(moneyline_dtos)}"
    )

    if not moneyline_dtos:
        pytest.skip(
            f"no active tennis moneyline market on {today}; "
            f"discovery counts events={len(events)} markets={total_markets}"
        )

    resolver_bundle = await _resolver_from_directory(settings)
    if resolver_bundle is None:
        pytest.skip(
            "local player directory unavailable; canonical resolution smoke "
            "requires migrated PostgreSQL with a synced directory"
        )
    resolver, database = resolver_bundle
    try:
        registered: dict[str, str] = {}
        externals: dict[str, tuple[str, tuple[str, str]]] = {}
        counter = {"n": 0}

        async def registrar(provider_event_id, condition_id, token_ids):
            if condition_id in registered:
                return registered[condition_id]
            counter["n"] += 1
            internal_id = f"mkt_live_{counter['n']}"
            registered[condition_id] = internal_id
            externals[internal_id] = (provider_event_id, token_ids)
            return internal_id

        async def lookup(market_id):
            from app.markets.models import MarketExternalId

            entry = externals.get(market_id)
            if entry is None:
                return None
            provider_event_id, token_ids = entry
            condition_id = next(
                cid for cid, mid in registered.items() if mid == market_id
            )
            return MarketExternalId(
                market_id=market_id,
                provider="polymarket",
                provider_event_id=provider_event_id,
                condition_id=condition_id,
                token_ids=token_ids,
            )

        provider = PolymarketProvider(
            gamma_base_url=settings.polymarket_gamma_base_url,
            clob_base_url=settings.polymarket_clob_base_url,
            resolver=resolver,
            registrar=registrar,
            external_lookup=lookup,
            timeout=30.0,
        )
        try:
            markets = await provider.list_tennis_moneylines()
            skip_counts: dict[str, int] = {}
            for skip in provider.skipped:
                skip_counts[skip.reason] = skip_counts.get(skip.reason, 0) + 1
            print(
                f"[polymarket-live {today}] canonical: mapped={len(markets)} "
                f"skipped={skip_counts}"
            )
            if not markets:
                pytest.skip(
                    f"no tennis moneyline resolved against the local player "
                    f"directory on {today}; skip counts={skip_counts}"
                )

            market = markets[0]
            assert market.id.startswith("mkt_live_")

            book = await provider.get_order_book(market.id)
            assert book.book_hash
            first, second = book.books
            assert first.outcome_player_id != second.outcome_player_id
            for side in (first, second):
                prices = [level.price for level in side.bids]
                assert prices == sorted(prices, reverse=True)
                ask_prices = [level.price for level in side.asks]
                assert ask_prices == sorted(ask_prices)

            metadata = await provider.get_execution_metadata(market.id)
            assert metadata.tick_size > 0
            assert metadata.sports_delay_seconds >= 0

            resolution = await provider.get_resolution(market.id)
            assert resolution is not None

            try:
                rules = await provider.get_rules(market.id)
                rules_hash = rules.rules_hash
            except AppError as exc:
                assert exc.code == "not_found"
                rules_hash = "unavailable"

            print(
                f"[polymarket-live {today}] market={market.id} "
                f"book_levels={len(first.bids) + len(first.asks)} "
                f"tick={metadata.tick_size} delay_s={metadata.sports_delay_seconds} "
                f"fee_rate={metadata.fee_rate} resolution={resolution.status.value} "
                f"rules_hash_len={len(rules_hash)}"
            )

            # Canonical output must not carry provider identifiers.
            serialized = json.dumps(
                {
                    "market": market.model_dump(mode="json"),
                    "book": book.model_dump(mode="json"),
                    "resolution": resolution.model_dump(mode="json"),
                }
            )
            for condition_id in registered:
                assert condition_id not in serialized
            for internal_id, (_, token_ids) in externals.items():
                for token_id in token_ids:
                    assert token_id not in serialized
        finally:
            await provider.aclose()
    finally:
        await database.dispose()
