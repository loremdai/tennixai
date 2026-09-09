import asyncio
from pathlib import Path

import pytest

from app.identity import MemoryIdentityRepository
from app.providers.replay import ReplayTennisProvider
from app.realtime.worker import RealtimeWorker

from realtime_fakes import FakeClock, FakeRawRepository, RealtimeBundle


FIXTURE = Path(__file__).parents[1] / "fixtures" / "replay" / "live_match.jsonl"


@pytest.mark.asyncio
async def test_replay_worker_deduplicates_corrects_reconciles_and_ends() -> None:
    identities = MemoryIdentityRepository()
    provider = ReplayTennisProvider.from_file(
        FIXTURE,
        identities=identities,
        speed=5.0,
    )
    match = (await provider.get_live_matches())[0]
    bundle = RealtimeBundle(FakeClock())
    worker = RealtimeWorker(
        identity=identities,
        snapshots=bundle.store,
        leases=bundle.leases,
        publisher=bundle.publisher,
        feed=provider,
        rest=provider,
        raw=FakeRawRepository(),
        now=bundle.clock.utcnow,
        max_live_subscriptions=8,
        provider_name="replay",
    )

    await bundle.leases.acquire(match.id, "viewer_a")
    await worker.reconcile_demand_once()

    for _ in range(80):
        await asyncio.sleep(0.02)
        await worker.reconcile_demand_once()
        if worker.subscription_state(match.id) == "closed":
            break

    versions = [item.snapshot.state_version for item in bundle.store.saved]
    assert versions == [1, 2, 3, 4, 5, 6]
    assert len(bundle.store.saved[2].snapshot.statistics) == 22
    assert bundle.store.saved[3].point_revisions[0].revision == 2
    assert len(bundle.store.saved[4].snapshot.points) == 2
    assert bundle.store.saved[-1].snapshot.match.live_state is not None
    assert bundle.store.saved[-1].snapshot.match.live_state.score is not None
    assert bundle.store.saved[-1].snapshot.match.live_state.score.sets_won == (2, 1)
    assert bundle.publisher.events[-1]["type"] == "match_ended"
    assert provider.opened_external_ids == ["replay-live", "replay-live"]
    assert provider.rest_reconcile_calls == [False, True]
    assert worker.subscription_state(match.id) == "closed"
    await worker.stop()
