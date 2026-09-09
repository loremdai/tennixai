"""Match snapshot REST and versioned SSE contract tests."""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.domain import (
    DataFreshness,
    LiveMatchState,
    Match,
    MatchScore,
    MatchSnapshot,
    MatchStatus,
    Player,
    SetScore,
    Tournament,
)
from app.identity import MemoryIdentityRepository
from app.main import create_app
from app.providers.fake import FakeTennisProvider
from app.realtime.reducer import reduce_live_snapshot
from realtime_fakes import FakeClock, InMemoryRedis, RealtimeBundle

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture()
async def env(clock: FakeClock):
    bundle = RealtimeBundle(clock)
    provider = FakeTennisProvider(identities=MemoryIdentityRepository(), now=lambda: NOW)
    await provider.build()
    settings = Settings(_env_file=None, fixed_now="2026-09-09T12:00:00Z", sse_heartbeat_seconds=1)
    app = create_app(settings, provider=provider, realtime=bundle)

    # SSE needs a real streaming server; httpx ASGITransport buffers responses.
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=8123, log_level="error")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    try:
        async with AsyncClient(base_url="http://127.0.0.1:8123") as client:
            yield client, bundle, provider
    finally:
        server.should_exit = True
        await serve_task


def live_match(match_id: str = "mat_stream") -> Match:
    return Match(
        id=match_id,
        status=MatchStatus.LIVE,
        players=(Player(id="ply_a", name="A"), Player(id="ply_b", name="B")),
        tournament=Tournament(id="trn_t", name="Tulln"),
        live_state=LiveMatchState(
            score=MatchScore(
                sets_won=(1, 1),
                sets=(SetScore(number=3, player1_games=2, player2_games=2),),
                points=("30", "15"),
            ),
            server_player_id="ply_a",
            state_version=0,
        ),
        freshness=DataFreshness(provider="fake", observed_at=NOW),
    )


def candidate(match_id: str, points: int) -> MatchSnapshot:
    from app.domain import PointEvent

    return MatchSnapshot(
        match=live_match(match_id),
        points=tuple(
            PointEvent(
                id=f"pe_{match_id}_{i}",
                match_id=match_id,
                sequence=i,
                set_number=3,
                game_number=1,
                point_number=i,
                server_player_id="ply_a",
                winner_player_id="ply_a",
                score_after=MatchScore(sets_won=(0, 0), sets=(), points=("15", "0")),
                observed_at=NOW,
                provider="fake",
                source_fingerprint=f"fp-{i}",
            )
            for i in range(1, points + 1)
        ),
        statistics=(),
        momentum=(),
        quality=(),
        state_version=0,
        as_of=NOW,
    )


async def seed_store(bundle: RealtimeBundle, match_id: str, points: int) -> MatchSnapshot:
    reduction = reduce_live_snapshot(None, candidate(match_id, points))
    await bundle.store.save_reduction(reduction)
    return reduction.snapshot


async def collect_frames(
    client: AsyncClient, path: str, max_frames: int, timeout: float = 4.0
) -> list[dict]:
    frames: list[dict] = []
    async def reader() -> None:
        async with client.stream("GET", path) as response:
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    raw, buffer = buffer.split("\n\n", 1)
                    frame = parse_frame(raw)
                    if frame:
                        frames.append(frame)
                        if len(frames) >= max_frames:
                            return
    await asyncio.wait_for(reader(), timeout=timeout)
    return frames


def parse_frame(raw: str) -> dict | None:
    event = None
    frame_id = None
    data_lines = []
    for line in raw.split("\n"):
        if line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("id:"):
            frame_id = line[len("id:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].strip())
    if event is None or not data_lines:
        return None
    return {"event": event, "id": frame_id, "data": json.loads("\n".join(data_lines))}


@pytest.mark.asyncio
async def test_snapshot_endpoint_returns_full_snapshot(env) -> None:
    client, bundle, provider = env
    live = await provider.get_live_matches()
    match_id = live[0].id

    response = await client.get(f"/api/v1/matches/{match_id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["match"]["id"] == match_id
    # The first persisted reduction assigns version 1.
    assert data["state_version"] == 1
    assert data["as_of"]
    assert {item["capability"] for item in data["quality"]} >= {
        "point_by_point",
        "statistics",
        "momentum",
    }
    # The resolved snapshot is persisted for later PG-first reads.
    assert bundle.store.current[match_id].match.id == match_id


@pytest.mark.asyncio
async def test_stream_sends_ready_then_atomic_deltas_with_version_ids(env) -> None:
    client, bundle, provider = env
    snapshot = await seed_store(bundle, "mat_stream", 2)

    async def publish_later() -> None:
        await asyncio.sleep(0.3)
        reduction = reduce_live_snapshot(snapshot, candidate("mat_stream", 3))
        await bundle.publisher.publish_delta(reduction)

    task = asyncio.create_task(publish_later())
    frames = await collect_frames(
        client, "/api/v1/matches/mat_stream/stream", max_frames=2
    )
    await task

    assert frames[0]["event"] == "ready"
    assert frames[0]["data"]["state_version"] == 1
    assert frames[0]["data"]["snapshot"]["match"]["id"] == "mat_stream"
    assert frames[1]["event"] == "match_delta"
    assert frames[1]["id"] == "2"
    assert frames[1]["data"]["state_version"] == 2
    assert set(frames[1]["data"]["changes"]) == {"point_appended", "momentum_updated"}


@pytest.mark.asyncio
async def test_each_version_is_published_exactly_once(env) -> None:
    client, bundle, provider = env
    snapshot = await seed_store(bundle, "mat_stream", 1)

    async def publish_later() -> None:
        await asyncio.sleep(0.2)
        current = snapshot
        for points in (2, 3):
            reduction = reduce_live_snapshot(current, candidate("mat_stream", points))
            current = reduction.snapshot
            await bundle.publisher.publish_delta(reduction)

    task = asyncio.create_task(publish_later())
    frames = await collect_frames(
        client, "/api/v1/matches/mat_stream/stream", max_frames=3
    )
    await task

    deltas = [frame for frame in frames if frame["event"] == "match_delta"]
    assert [frame["id"] for frame in deltas] == ["2", "3"]
    assert [frame["data"]["state_version"] for frame in deltas] == [2, 3]


@pytest.mark.asyncio
async def test_version_gap_is_forwarded_not_filled(env) -> None:
    client, bundle, provider = env
    snapshot = await seed_store(bundle, "mat_stream", 1)

    async def publish_later() -> None:
        await asyncio.sleep(0.2)
        # Jump straight to version 4; the server must not fabricate 2 and 3.
        reduction = _reduction_to_version(bundle, snapshot, 4)
        await bundle.publisher.publish_delta(reduction)

    task = asyncio.create_task(publish_later())
    frames = await collect_frames(
        client, "/api/v1/matches/mat_stream/stream", max_frames=2
    )
    await task

    deltas = [frame for frame in frames if frame["event"] == "match_delta"]
    assert [frame["id"] for frame in deltas] == ["4"]


def _reduction_to_version(bundle: RealtimeBundle, base: MatchSnapshot, points: int):
    current = base
    reduction = None
    for step in range(2, points + 1):
        reduction = reduce_live_snapshot(current, candidate("mat_stream", step))
        current = reduction.snapshot
    return reduction


@pytest.mark.asyncio
async def test_match_ended_closes_the_stream(env) -> None:
    client, bundle, provider = env
    snapshot = await seed_store(bundle, "mat_stream", 1)

    async def publish_later() -> None:
        await asyncio.sleep(0.2)
        await bundle.publisher.publish_match_ended("mat_stream", 1, NOW)

    task = asyncio.create_task(publish_later())
    frames = await collect_frames(
        client, "/api/v1/matches/mat_stream/stream", max_frames=2, timeout=4.0
    )
    await task

    assert frames[-1]["event"] == "match_ended"


@pytest.mark.asyncio
async def test_heartbeat_carries_no_version_change(env) -> None:
    client, bundle, provider = env
    await seed_store(bundle, "mat_stream", 1)

    frames = await collect_frames(
        client, "/api/v1/matches/mat_stream/stream", max_frames=3, timeout=5.0
    )

    heartbeats = [frame for frame in frames if frame["event"] == "heartbeat"]
    assert heartbeats, "expected at least one heartbeat within 5s"
    assert all(frame["id"] is None for frame in heartbeats)


@pytest.mark.asyncio
async def test_viewer_lease_exists_only_while_connected(env) -> None:
    client, bundle, provider = env
    await seed_store(bundle, "mat_stream", 1)

    async def open_and_close() -> str:
        async with client.stream("GET", "/api/v1/matches/mat_stream/stream") as response:
            async for chunk in response.aiter_text():
                if "\n\n" in chunk:
                    break
        viewers = await bundle.redis.hgetall("tnx:demand:mat_stream")
        return json.dumps(viewers)

    during = await open_and_close()
    await asyncio.sleep(0.05)
    viewers_after = await bundle.redis.hgetall("tnx:demand:mat_stream")
    lease_keys = [
        key
        for key in viewers_after
        if key not in ("grace_until", "demanded_at")
    ]
    assert lease_keys == []
    assert during is not None


@pytest.mark.asyncio
async def test_stream_headers_disable_buffering(env) -> None:
    client, bundle, provider = env
    await seed_store(bundle, "mat_stream", 1)

    async with client.stream("GET", "/api/v1/matches/mat_stream/stream") as response:
        assert response.headers["cache-control"] == "no-cache, no-transform"
        assert response.headers["x-accel-buffering"] == "no"
        async for chunk in response.aiter_text():
            if "\n\n" in chunk:
                break


@pytest.mark.asyncio
async def test_unknown_match_stream_returns_not_found(env) -> None:
    client, bundle, provider = env

    response = await client.get("/api/v1/matches/mat_missing/stream")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
