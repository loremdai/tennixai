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

- [x] Update the existing `test_match_current_rank_comes_from_directory_not_provider_profile` regression: the provider returns ranks 72 and 40, only the first player exists in latest standings at rank 5, and the returned ranks must be `[5, None]` (replace its stale expectation of 40).
- [x] Run `uv run pytest tests/test_player_profile_service.py::test_match_current_rank_comes_from_directory_not_provider_profile -q` and confirm the absent-player assertion fails against current code (`40` was incorrectly retained).
- [x] Add a reducer regression with a previous snapshot ranked 741/999 and an authoritative candidate ranked 106/None; assert 106/None, a changed version, and `PLAYER_METADATA_UPDATED`.
- [x] Run the reducer regression and confirm a non-authoritative reduction preserves stale `999`; then exercise the intended authoritative mode after implementing it.
- [x] Implement the optional `rankings_authoritative` reducer flag without changing default sparse-frame preservation; make service ranking projection return `None` when a configured directory has no current entry, and pass the flag when persisting a normalized snapshot.
- [x] Run `uv run pytest tests/test_live_reducer.py tests/test_player_profile_service.py -q` (`47 passed`).

### Task 2: Apply current standings to realtime worker publications

**Files:**
- Modify: `backend/app/realtime/worker.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/runtime/assembly.py`
- Test: `backend/tests/test_realtime_worker.py`

**Interfaces:**
- `RealtimeWorker(..., directory=None)` accepts the existing player-directory repository as an optional dependency; absent a directory, behavior stays unchanged.
- Before each reduction/publication, the worker obtains current ranks for the snapshot's two internal player IDs and applies the authoritative reducer mode. Missing entries explicitly clear stale ranks.

- [x] Add a worker regression that seeds `InMemorySnapshotStore.current` with a stale 741/999 snapshot, seeds `MemoryPlayerDirectoryRepository` with only player A at rank 106, reconciles an unranked API snapshot, and asserts both persisted and published snapshots contain 106/None.
- [x] Add a sparse subsequent live-frame assertion proving the current standings ranks remain correct and the stale values do not reappear.
- [x] Run the new worker test and confirm it fails before implementation because `RealtimeWorker` has no directory dependency.
- [x] Pass the already-constructed directory repository into realtime-worker construction in `main.py` and `runtime/assembly.py`; make `_apply` project the current snapshot by internal player ID and use `rankings_authoritative=True` only when that repository exists.
- [x] Run `uv run pytest tests/test_realtime_worker.py -q` (`10 passed`), including the pre-existing sparse metadata-preservation cases.

### Task 3: Verify and close T94

**Files:**
- Modify: `CURRENT.md`
- Modify: `ROADMAP.md`
- No product UI, schema, or configuration files.

- [x] Run the full deterministic backend suite: `uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not integration"` (`1336 passed, 12 skipped, 25 deselected`, 208.49s; final run after review fixes).
- [x] Run focused PostgreSQL ranking/realtime integration tests using verified target database `tennix` (not `tennix_live_local`): player-directory integration `9 passed`; live-reduction persistence also passed in full deterministic run.
- [x] Run Ruff on changed Python files and `git diff --check` (both pass).
- [x] Inspect the diff for accidental provider calls, stale-rank fallbacks, credentials, and unrelated files; preserve the shared service without restart. No provider calls, credential changes, UI/schema/config changes, or unrelated tracked files were introduced. User-owned untracked files remain untouched.
- [ ] Update task evidence in `CURRENT.md` and `ROADMAP.md`; commit and push the implementation and control-document closure to `origin/main`.

### Independent review follow-up

- Fixed: a REST rank-only correction was persisted but not published to the Redis/SSE hot snapshot. `TennisService` now publishes the reduction after persistence; the realtime worker rebases from a newer hot snapshot before applying its next frame. Regression tests prove versions advance and the corrected rank is not overwritten.
- Fixed: a transient player-directory read failure could interrupt realtime processing and lose a dequeued frame. The worker now keeps the pending envelope and retries after a bounded one-second delay; a lookup failure is never treated as an empty standings result. The regression test covers both initial sync and a subsequent frame failure/retry.
- Verification after these fixes: the two added regressions pass in the full suite (`1336 passed, 12 skipped, 25 deselected`); Ruff and `git diff --check` pass.
- Deferred minor review note: each live frame currently does directory reads and checks the Redis hot snapshot. This adds work to the realtime path; monitor worker latency/backlog and optimize/coalesce only if measurements justify it.
- Reviewer did not assess three broader questions. (1) A standings sync alone does not fan out a rank correction until a REST read, worker reconcile, or feed event; if this matters, an idle active view may retain its prior rank temporarily. (2) This task relies on the stored provider standings and existing tour selection; it does not independently prove upstream feed correctness, so a bad upstream snapshot can still be shown. (3) The shared service was intentionally not restarted; until an authorized restart, the running browser process continues serving its older code. These are explicit scope limits, not claims of runtime verification.
