"""CLOB batch `POST /books` adapter tests (T85). No real network calls."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from app.errors import AppError
from app.markets.polymarket import PolymarketProvider

NOW = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)
TOKEN_A = "111111111111111111111"
TOKEN_B = "222222222222222222222"


def provider(handler) -> PolymarketProvider:
    transport = httpx.MockTransport(handler)
    return PolymarketProvider(
        gamma_base_url="https://gamma.test",
        clob_base_url="https://clob.test",
        resolver=None,  # batch reads never resolve players
        transport=transport,
        now_fn=lambda: NOW,
    )


def book_payload(token: str, *, bids=None, asks=None, digest="h1") -> dict:
    return {
        "market": "0xcondition",
        "asset_id": token,
        "timestamp": "1758528000000",
        "hash": digest,
        "bids": bids if bids is not None else [{"price": "0.44", "size": "12"}],
        "asks": asks if asks is not None else [{"price": "0.56", "size": "10"}],
    }


async def test_batch_books_posts_every_token_once_in_order():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json=[
                book_payload(TOKEN_B, digest="hb"),
                book_payload(TOKEN_A, digest="ha"),
            ],
        )

    client = provider(handler)
    try:
        batch = await client.get_order_books([TOKEN_A, TOKEN_B, TOKEN_A])
    finally:
        await client.aclose()

    assert seen["method"] == "POST" and seen["path"] == "/books"
    assert seen["body"] == [{"token_id": TOKEN_A}, {"token_id": TOKEN_B}]
    assert seen["auth"] is None  # public read-only endpoint, no credentials
    assert set(batch.books) == {TOKEN_A, TOKEN_B}
    # Response order is never assumed: books are keyed by asset_id.
    assert batch.books[TOKEN_A].bids[0].price == Decimal("0.44")
    assert batch.books[TOKEN_A].book_hash == "ha"
    assert batch.books[TOKEN_A].provider_timestamp == datetime(
        2025, 9, 22, 8, 0, tzinfo=UTC
    )
    assert batch.missing_tokens == () and batch.malformed_tokens == ()
    assert len(batch.raw) == 2


async def test_batch_books_isolates_a_malformed_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                book_payload(TOKEN_A),
                {
                    "asset_id": TOKEN_B,
                    "bids": [
                        {"price": "0.5", "size": "1"},
                        {"price": "0.5", "size": "2"},
                    ],
                    "asks": [],
                },
            ],
        )

    client = provider(handler)
    try:
        batch = await client.get_order_books([TOKEN_A, TOKEN_B])
    finally:
        await client.aclose()

    assert set(batch.books) == {TOKEN_A}
    assert batch.malformed_tokens == (TOKEN_B,)
    assert batch.missing_tokens == ()


async def test_batch_books_reports_missing_tokens_without_fabricating_them():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[book_payload(TOKEN_A)])

    client = provider(handler)
    try:
        batch = await client.get_order_books([TOKEN_A, TOKEN_B])
    finally:
        await client.aclose()

    assert set(batch.books) == {TOKEN_A}
    assert batch.missing_tokens == (TOKEN_B,)


async def test_batch_books_translates_429_with_retry_after():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "7"}, json={})

    client = provider(handler)
    try:
        with pytest.raises(AppError) as excinfo:
            await client.get_order_books([TOKEN_A])
    finally:
        await client.aclose()
    assert excinfo.value.code == "rate_limited"
    assert excinfo.value.details["retry_after"] == "7"


async def test_batch_books_rejects_a_non_list_payload():
    client = provider(lambda request: httpx.Response(200, json={"error": "nope"}))
    try:
        with pytest.raises(AppError) as excinfo:
            await client.get_order_books([TOKEN_A])
    finally:
        await client.aclose()
    assert excinfo.value.code == "provider_invalid_response"


async def test_batch_books_with_no_tokens_never_calls_the_provider():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request expected")

    client = provider(handler)
    try:
        batch = await client.get_order_books([])
    finally:
        await client.aclose()
    assert batch.books == {} and batch.raw == ()
