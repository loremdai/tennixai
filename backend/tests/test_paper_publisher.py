"""PaperPublisher unit tests (T66 wiring fix).

The paper service publishes lifecycle marker strings
(``state:id[:reason]``); the assembled app must convert them into
`paper_delta` events on the independent ``tnx:p3:paper:{id}`` channel so
`markets/stream` subscribers receive them, and must never crash the
ledger path. Markers carry internal IDs only.
"""

import json

from app.realtime.publisher import PaperPublisher, paper_channel, paper_hot_key
from realtime_fakes import FakeClock, InMemoryRedis


class RecordingRedis:
    def __init__(self) -> None:
        self.sets: list[tuple[str, str]] = []
        self.published: list[tuple[str, str]] = []

    async def set(self, key: str, value: str, ex=None) -> None:
        self.sets.append((key, value))

    async def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))

    async def get(self, key: str):
        return None


async def test_marker_becomes_paper_delta_on_paper_channel():
    redis = RecordingRedis()
    clock = FakeClock()
    publisher = PaperPublisher(redis, now_fn=clock.utcnow)

    await publisher.publish_marker("filled:mat_1")

    channel, message = redis.published[0]
    assert channel == "tnx:p3:paper:mat_1"
    assert channel == paper_channel("mat_1")
    event = json.loads(message)
    assert event["type"] == "paper_delta"
    assert event["state"] == "filled"
    assert event["id"] == "mat_1"
    assert event.get("reason") is None
    assert event["as_of"]
    hot_key, hot_value = redis.sets[0]
    assert hot_key == paper_hot_key("mat_1")
    assert json.loads(hot_value)["state"] == "filled"


async def test_reason_segment_is_preserved():
    redis = RecordingRedis()
    publisher = PaperPublisher(redis, now_fn=FakeClock().utcnow)

    await publisher.publish_marker("no_fill:mat_2:DEPTH_INSUFFICIENT")

    event = json.loads(redis.published[0][1])
    assert event["state"] == "no_fill"
    assert event["id"] == "mat_2"
    assert event["reason"] == "DEPTH_INSUFFICIENT"


async def test_settlement_blocked_uses_market_id_channel():
    redis = RecordingRedis()
    publisher = PaperPublisher(redis, now_fn=FakeClock().utcnow)

    await publisher.publish_marker("settlement_blocked:mkt_9:RESOLUTION_PENDING")

    channel, message = redis.published[0]
    assert channel == paper_channel("mkt_9")
    event = json.loads(message)
    assert event["id"] == "mkt_9"
    assert event["reason"] == "RESOLUTION_PENDING"


async def test_malformed_marker_is_ignored_without_publishing():
    redis = RecordingRedis()
    publisher = PaperPublisher(redis, now_fn=FakeClock().utcnow)

    await publisher.publish_marker("garbage")
    await publisher.publish_marker("")

    assert redis.published == []
    assert redis.sets == []


async def test_events_reach_an_in_memory_subscriber():
    redis = InMemoryRedis(FakeClock())
    publisher = PaperPublisher(redis, now_fn=FakeClock().utcnow)
    pubsub = redis.pubsub()
    await pubsub.subscribe(paper_channel("mat_3"))

    await publisher.publish_marker("settled:mat_3")

    message = await pubsub.get_message(timeout=0.1)
    assert message is not None
    event = json.loads(message["data"])
    assert event["type"] == "paper_delta"
    assert event["state"] == "settled"
    await pubsub.aclose()
