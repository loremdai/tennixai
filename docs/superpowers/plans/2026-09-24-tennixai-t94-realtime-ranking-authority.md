# T94: Keep Match Rankings Consistent in REST and Realtime Snapshots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure match snapshots and their live SSE updates always use the latest stored singles-ranking snapshot, clearing stale ranks when a player is absent.

**Architecture:** The API-Tennis `get_standings` snapshot remains the sole current-ranking authority. REST hydration and the realtime worker join it by internal player ID; the reducer accepts an authoritative `None` only on those canonicalized paths, while ordinary sparse feed updates keep the existing metadata-preservation behavior. No provider calls, database migrations, new dependencies, or UI changes are needed.

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy/PostgreSQL, pytest.

**Spec:** `PROJECT.md` — “Stable architecture” and “P2.6 approved solution”; `docs/superpowers/plans/2026-09-24-tennixai-player-data-integrity-implementation.md`.

## Global Constraints

- The latest stored ATP/WTA singles standings snapshot is the only source for current rank.
- `get_players.stats[].rank` is season/type-specific and must not be used as current singles rank.
- Missing current ranking remains `None`; never preserve an older profile rank as if current.
- Use existing directory repositories; add no dependency, migration, provider call, poller, or runtime LLM call.
- Do not restart the shared local runtime or touch `.env`, `.next`, or user-owned untracked files.

## Review Focus

- A persisted pre-T92 rank (for example 741) is replaced by the current standings rank (106) during realtime reconciliation and the emitted snapshot.
- A player absent from the latest standings snapshot is emitted with `ranking=None`, not an older cached/profile rank.
- Sparse WebSocket player rows still preserve canonical name and country; the ranking rule must not weaken those fields.
- Reducer callers without a directory retain existing behavior, including preserving ranking metadata across sparse frames.
- A rank-only correction advances the snapshot version and emits `PLAYER_METADATA_UPDATED`.

---

### Task 1: Make standings authoritative in match snapshot hydration

**Files:**
- Modify: `backend/app/realtime/reducer.py`
- Modify: `backend/app/service.py`
- Test: `backend/tests/test_live_reducer.py`
- Test: `backend/tests/test_player_profile_service.py`

**Interfaces:**
- `reduce_live_snapshot(previous, candidate, *, momentum_engine=None, rankings_authoritative=False)` preserves existing defaults; when `rankings_authoritative=True`, each incoming ranking (including `None`) replaces the stored rank while other sparse player metadata retains its existing merge rules.
- `TennisService._hydrate_matches_players` treats directory lookup as authoritative: no latest entry means no current ranking.

- [ ] Update the existing `test_match_current_rank_comes_from_directory_not_provider_profile` regression: the provider returns ranks 72 and 40, only the first player exists in latest standings at rank 5, and the returned ranks must be `[5, None]` (replace its stale expectation of 40).
- [ ] Run `uv run pytest tests/test_player_profile_service.py::test_match_current_rank_comes_from_directory_not_provider_profile -q` and confirm the absent-player assertion fails against current code.
- [ ] Add a reducer regression with a previous snapshot ranked 741/999 and an authoritative candidate ranked 106/None; assert 106/None, a changed version, and `PLAYER_METADATA_UPDATED`.
- [ ] Run the new reducer test and confirm it fails because the current reducer preserves the old non-null rank.
- [ ] Implement the optional `rankings_authoritative` reducer flag without changing default sparse-frame preservation; make service ranking projection return `None` when a configured directory has no current entry, and pass the flag when persisting a normalized snapshot.
- [ ] Run `uv run pytest tests/test_live_reducer.py tests/test_player_profile_service.py -q` and confirm both regressions pass.

### Task 2: Apply current standings to realtime worker publications

**Files:**
- Modify: `backend/app/realtime/worker.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/runtime/assembly.py`
- Test: `backend/tests/test_realtime_worker.py`

**Interfaces:**
- `RealtimeWorker(..., directory=None)` accepts the existing player-directory repository as an optional dependency; absent a directory, behavior stays unchanged.
- Before each reduction/publication, the worker obtains current ranks for the snapshot's two internal player IDs and applies the authoritative reducer mode. Missing entries explicitly clear stale ranks.

- [ ] Add a worker regression that seeds `InMemorySnapshotStore.current` with a stale 741/999 snapshot, seeds `MemoryPlayerDirectoryRepository` with only player A at rank 106, reconciles an unranked API snapshot, and asserts both persisted and published snapshots contain 106/None.
- [ ] Add a sparse subsequent live-frame assertion proving the current standings ranks remain correct and the stale values do not reappear.
- [ ] Run the new worker test and confirm it fails before implementation.
- [ ] Pass the already-constructed directory repository into realtime-worker construction in `main.py` and `runtime/assembly.py`; make `_apply` project the current snapshot by internal player ID and use `rankings_authoritative=True` only when that repository exists.
- [ ] Run `uv run pytest tests/test_realtime_worker.py -q` and confirm all worker tests pass, including the pre-existing sparse metadata-preservation cases.

### Task 3: Verify and close T94

**Files:**
- Modify: `CURRENT.md`
- Modify: `ROADMAP.md`
- No product UI, schema, or configuration files.

- [ ] Run the full deterministic backend suite: `uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not integration"`.
- [ ] Run focused PostgreSQL ranking/realtime integration tests if their configured local test database is available; do not point tests at `tennix_live_local`.
- [ ] Run Ruff on changed Python files and `git diff --check`.
- [ ] Inspect the diff for accidental provider calls, stale-rank fallbacks, credentials, and unrelated files; preserve the shared service without restart.
- [ ] Update task evidence in `CURRENT.md` and `ROADMAP.md`; commit and push the implementation and control-document closure to `origin/main`.
