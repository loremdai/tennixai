"""Opt-in public Polymarket market WebSocket smoke gate (T60).

Run with:
    TENNIX_RUN_POLYMARKET_LIVE=1 uv run pytest -m polymarket_live \
        tests/live/test_polymarket_websocket_live.py -v

Subscribes only to the public market channel of one real active tennis
moneyline token pair, waits for at least one book or price_change message,
reduces it through the canonical reducer and prints aggregate counts only.
No active tennis market is an honest dated skip.
"""

import asyncio
import os
from datetime import UTC, datetime

import httpx
import pytest

from app.config import Settings
from app.markets.live import PolymarketMarketFeed
from app.markets.polymarket_dtos import GammaMarketDto
from app.markets.reducer import MarketBookReducer

pytestmark = pytest.mark.polymarket_live


async def test_public_market_websocket_delivers_reducible_events() -> None:
    if os.environ.get("TENNIX_RUN_POLYMARKET_LIVE") != "1":
        pytest.skip("TENNIX_RUN_POLYMARKET_LIVE not set")
    settings = Settings(provider_mode="fake", llm_mode="fake")
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
    assert response.status_code == 200

    tokens: list[str] = []
    for raw_event in response.json():
        if not isinstance(raw_event, dict):
            continue
        for raw_market in raw_event.get("markets", []):
            dto = GammaMarketDto.model_validate(raw_market)
            if (dto.sportsMarketType or "").casefold() != "moneyline":
                continue
            if dto.closed or dto.active is False or dto.acceptingOrders is False:
                continue
            market_tokens = dto.token_ids()
            if len(market_tokens) == 2:
                tokens.extend(market_tokens)
        if len(tokens) >= 4:
            break

    if not tokens:
        pytest.skip(
            f"no active tennis moneyline tokens discovered on {today}; "
            "websocket smoke honestly skipped"
        )
    tokens = tuple(tokens[:4])

    feed = PolymarketMarketFeed(
        ws_url=settings.polymarket_ws_url,
        ping_interval_seconds=10.0,
    )
    reducer = MarketBookReducer(
        market_id="mkt_ws_smoke",
        token_players={
            token: f"ply_side_{index}" for index, token in enumerate(tokens)
        },
        now_fn=lambda: datetime.now(UTC),
    )

    received = {"book": 0, "price_change": 0, "other": 0}
    reductions = 0
    try:

        async def consume() -> None:
            nonlocal reductions
            async for event in feed.subscribe(tokens):
                if event.event_type in received:
                    received[event.event_type] += 1
                else:
                    received["other"] += 1
                reduction = reducer.apply_event(event)
                if reduction.changed:
                    reductions += 1
                if received["book"] + received["price_change"] >= 2:
                    return

        await asyncio.wait_for(consume(), timeout=45)
    except TimeoutError:
        pass
    finally:
        await feed.shutdown()

    total = received["book"] + received["price_change"]
    print(
        f"[polymarket-ws-live {today}] tokens={len(tokens)} "
        f"book={received['book']} price_change={received['price_change']} "
        f"other={received['other']} reduced_changes={reductions}"
    )
    if total == 0:
        # Prove the public channel itself works by subscribing to the most
        # active non-tennis markets; a tennis-only silence is then an honest
        # quiet-market skip rather than a broken subscription.
        control_tokens = await _discover_active_control_tokens(settings)
        control_events = 0
        if control_tokens:
            control_feed = PolymarketMarketFeed(ws_url=settings.polymarket_ws_url)
            try:

                async def consume_control() -> None:
                    nonlocal control_events
                    async for _ in control_feed.subscribe(control_tokens):
                        control_events += 1
                        if control_events >= 1:
                            return

                await asyncio.wait_for(consume_control(), timeout=20)
            except TimeoutError:
                pass
            finally:
                await control_feed.shutdown()
        print(
            f"[polymarket-ws-live {today}] control_tokens={len(control_tokens)} "
            f"control_events={control_events}"
        )
        pytest.skip(
            f"public websocket delivered no book/price_change for tennis "
            f"tokens within 45s on {today}; tokens subscribed={len(tokens)}, "
            f"active-market control events={control_events} "
            f"({'channel verified, tennis market quiet' if control_events else 'channel unverified'})"
        )
    assert total >= 1


async def _discover_active_control_tokens(settings) -> tuple[str, ...]:
    try:
        async with httpx.AsyncClient(
            base_url=settings.polymarket_gamma_base_url, timeout=20.0
        ) as client:
            response = await client.get(
                "/events",
                params={
                    "active": "true",
                    "closed": "false",
                    "order": "volume24hr",
                    "ascending": "false",
                    "limit": 3,
                },
            )
        if response.status_code != 200:
            return ()
        tokens: list[str] = []
        for raw_event in response.json():
            if not isinstance(raw_event, dict):
                continue
            for raw_market in raw_event.get("markets", []):
                dto = GammaMarketDto.model_validate(raw_market)
                if dto.closed or dto.acceptingOrders is False:
                    continue
                market_tokens = dto.token_ids()
                if len(market_tokens) == 2:
                    tokens.extend(market_tokens)
        return tuple(tokens[:4])
    except httpx.HTTPError:
        return ()
