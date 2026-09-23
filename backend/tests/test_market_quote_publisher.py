import json
from datetime import UTC, datetime

from app.markets.publisher import QUOTE_CATALOG_CHANNEL, QuoteCatalogPublisher


NOW = datetime(2026, 9, 23, 11, 30, tzinfo=UTC)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.published = []

    async def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def publish(self, channel, payload):
        self.published.append((channel, payload))


async def test_quote_catalog_publisher_emits_aggregate_private_invalidation():
    redis = FakeRedis()
    publisher = QuoteCatalogPublisher(redis, now_fn=lambda: NOW)

    await publisher.publish_quotes_changed(count=7)
    await publisher.publish_quotes_changed(count=0)

    assert [channel for channel, _payload in redis.published] == [
        QUOTE_CATALOG_CHANNEL,
        QUOTE_CATALOG_CHANNEL,
    ]
    events = [json.loads(payload) for _channel, payload in redis.published]
    assert events == [
        {
            "type": "quotes_changed",
            "sequence": 1,
            "count": 7,
            "as_of": NOW.isoformat(),
        },
        {
            "type": "quotes_changed",
            "sequence": 2,
            "count": 0,
            "as_of": NOW.isoformat(),
        },
    ]
    assert not any(
        key in json.dumps(events).lower()
        for key in ("token", "condition", "provider", "wallet")
    )
