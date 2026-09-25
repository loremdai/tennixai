# T103 Score Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve API-Tennis set games and tiebreak points through provider parsing, stored match snapshots, REST responses, and all existing score displays.

**Architecture:** Decode each provider set-side value strictly as `games` or `games.tiebreak_points` into optional canonical fields. Merge score rows only for the same match, ordered players, and set number; on a detail read, refresh only a finished snapshot whose per-set score is incomplete, reusing the existing metadata cache and persistence/realtime upgrade path. Render the resulting values in player history, match score tables, and Home live rows without inferring unknown data.

**Tech Stack:** Python, Pydantic, FastAPI, pytest, PostgreSQL JSONB snapshots, TypeScript, React, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-26-tennixai-t103-score-integrity-design.md`

## Global Constraints

- Accept only a non-negative integer game count, optionally followed by `.` and a non-negative integer tiebreak-point count; malformed and missing values remain `None`.
- Add a score-specific parser; keep the shared `parse_non_negative_int` behavior unchanged because it also parses numeric PBP fields.
- Canonical tiebreak fields are optional, so existing JSONB snapshots and API consumers with no tiebreak data continue to load.
- Never infer a set score from the match winner, set count, or point-by-point sequence.
- Refresh only a finished match with a missing per-set score, on demand, through the existing `match-metadata:<match_id>` cache; do not add startup, bulk-history, or periodic polling work.
- Keep `get_match_snapshot(..., include_surface=True)` behavior unchanged by default; score-only repair passes `include_surface=False` and must not call API-Tennis `get_draw`.
- Do not run `init`, reset or migrate the database, read or print `.env`, or expose provider credentials/payloads.
- Preserve existing user changes, especially the two unrelated P3 freshness edits in `backend/app/service.py`; stage only T103 hunks.
- Do not regenerate approved visual baselines or add dependencies.

## Review Focus

1. A malformed value such as `6.x`, `-1`, whitespace-only, or `7.2.3` must not be truncated into a plausible score; pin with parser cases in Task 1.
2. An old JSONB score without tiebreak keys must deserialize as `None`; pin in Task 1.
3. A sparse refresh must preserve known values but accept a non-null correction, without moving values between set numbers or player sides; pin in Task 2.
4. A provider failure or still-incomplete response must leave the stored score intact, and complete/live/upcoming matches must not trigger score repair; pin in Task 3.
5. The player-history perspective and the two player-row scoreboards must show each side's own tiebreak points while retaining current missing-score behavior; pin in Task 4.

---

## File Map

- `backend/app/domain.py`: add optional per-player tiebreak points to `SetScore`.
- `backend/app/providers/api_tennis.py`: strictly decode the supplier's dotted score representation.
- `backend/app/realtime/reducer.py`: merge sparse set-score fields by stable match/player/set identity.
- `backend/app/providers/base.py`, all four production providers, and provider test doubles: expose the backward-compatible surface-enrichment option.
- `backend/app/service.py`: identify eligible incomplete finished snapshots, perform one cached score-only refresh, and persist/publish the upgrade. This file already contains unrelated user edits; edit only the T103 block and stage only its T103 hunk.
- `backend/tests/test_api_tennis_provider.py`, `backend/tests/test_domain.py`, `backend/tests/test_live_reducer.py`, `backend/tests/test_service.py`, `backend/tests/test_api.py`, and provider-contract tests: pin parsing, compatibility, reducer, refresh, persistence, and HTTP serialization behavior.
- `frontend/lib/api/types.ts`: include the optional tiebreak fields in the typed API contract.
- `frontend/lib/view-models.ts`, `frontend/lib/player-view-models.ts`, `frontend/components/match/match-hero.tsx`, `frontend/components/match/match-main.tsx`, and `frontend/components/home/home-match-sections.tsx`: carry and display per-player tiebreak points.
- `frontend/lib/player-view-models.test.ts`, `frontend/lib/view-models.test.ts`, `frontend/components/match-page.test.tsx`, and `frontend/components/home-page.test.tsx`: verify history, Home data shaping, match-detail, and Home presentation.
- `CURRENT.md`, `ROADMAP.md`, and this plan: track approval, implementation, evidence, and completion.

### Task 1: Decode and Canonicalize Tiebreak Scores

**Files:**
- Modify: `backend/app/domain.py`
- Modify: `backend/app/providers/api_tennis.py`
- Test: `backend/tests/test_api_tennis_provider.py`
- Test: `backend/tests/test_domain.py`

**Interfaces:**
- Provider input remains `ScoreRowDto.score_first` / `score_second`.
- `SetScore` adds `player1_tiebreak_points: int | None = None` and `player2_tiebreak_points: int | None = None`.
- A provider parsing helper returns `(games, tiebreak_points)`; an invalid input returns `(None, None)`.

- [ ] **Step 1: Add failing provider cases** for `6.7` / `7.9`, ordinary `6` / `4`, `-`, empty, negative, and malformed dotted forms. Assert the decoded set has games `(6, 7)` and tiebreak points `(7, 9)` for the first case, and invalid values stay unknown.
- [ ] **Step 2: Run the focused test and verify the defect is reproduced.**

  Run: `cd backend && uv run pytest tests/test_api_tennis_provider.py -k 'tiebreak or score' -q`

  Expected: the new tiebreak test fails because current parsing returns `None` for dotted values.

- [ ] **Step 3: Add optional canonical fields and a strict parser.** Use a full-string match equivalent to `r"(\d+)(?:\.(\d+))?"`; do not extract a numeric prefix from malformed input. Map each parsed side to the same player side already used by `score_first` / `score_second`.
- [ ] **Step 4: Add backward-compatibility assertions.** Validate a legacy `SetScore` JSON object without either new field and assert both fields are `None`; serialize and validate a new score to prove the values round-trip.
- [ ] **Step 5: Run focused tests and lint.**

  Run: `cd backend && uv run pytest tests/test_api_tennis_provider.py tests/test_domain.py -q && uv run ruff check app/domain.py app/providers/api_tennis.py tests/test_api_tennis_provider.py tests/test_domain.py`

  Expected: all focused tests pass and Ruff reports no issues.

- [ ] **Step 6: Commit the parser/model slice.**

  ```bash
  git add backend/app/domain.py backend/app/providers/api_tennis.py backend/tests/test_api_tennis_provider.py backend/tests/test_domain.py
  git commit -m "fix: preserve tiebreak set scores"
  ```

### Task 2: Preserve Known Scores During Sparse Reduction

**Files:**
- Modify: `backend/app/realtime/reducer.py`
- Test: `backend/tests/test_live_reducer.py`

**Interfaces:**
- `reduce_live_snapshot(previous, candidate, ...)` remains the public reducer API.
- A private score merge combines `SetScore` rows only when match IDs and ordered player IDs match; each candidate non-null field wins, while a candidate null or omitted set row retains the previous known value.

- [ ] **Step 1: Add failing reducer tests.** Cover: same set with incoming `None` retains prior games/tiebreak points; incoming non-null values replace prior values; a missing set row is retained; adjacent set numbers and reversed player identity do not receive the old row's values.
- [ ] **Step 2: Run the new reducer tests and confirm they fail** because the current reducer accepts the candidate score as-is.
- [ ] **Step 3: Implement the smallest private merge helper** before reducer fingerprints/events are computed. Preserve all non-score candidate state and do not merge `sets_won`, point score, server, metadata, or data across a different match/player identity.
- [ ] **Step 4: Run reducer tests plus the existing score/realtime tests.**

  Run: `cd backend && uv run pytest tests/test_live_reducer.py tests/test_realtime_worker.py -q`

  Expected: new sparse-score cases and existing realtime reduction cases pass.

- [ ] **Step 5: Commit the reducer slice.**

  ```bash
  git add backend/app/realtime/reducer.py backend/tests/test_live_reducer.py
  git commit -m "fix: preserve known set scores on sparse updates"
  ```

### Task 3: Refresh Only Incomplete Finished Snapshots

**Files:**
- Modify: `backend/app/providers/base.py`
- Modify: `backend/app/providers/api_tennis.py`
- Modify: `backend/app/providers/livetennis.py`
- Modify: `backend/app/providers/fake.py`
- Modify: `backend/app/providers/replay.py`
- Modify: `backend/app/service.py` (T103 hunk only)
- Modify provider test doubles in `backend/tests/realtime_fakes.py`, `backend/tests/test_runtime_api_role.py`, `backend/tests/test_service.py`, `backend/tests/test_p1_acceptance.py`, `backend/tests/test_chat_orchestrator.py`, `backend/tests/test_momentum_calibration.py`, and `backend/tests/test_api.py` to accept the optional keyword without changing their behavior.
- Test: `backend/tests/test_api_tennis_provider.py`
- Test: `backend/tests/test_service.py`
- Test: `backend/tests/test_api.py` for the match-detail JSON response.

**Interfaces:**
- Provider protocol: `async def get_match_snapshot(self, match_id: str, *, include_surface: bool = True) -> MatchSnapshot`.
- Existing callers retain default surface enrichment. API-Tennis skips `_draw_surface` only when `include_surface=False`; other providers accept the option and retain their current snapshot behavior.
- Service refresh eligibility: match status is `FINISHED` and the snapshot has no score, a score row with either games value unknown, or a missing expected set row from `1..sum(sets_won)`.

- [ ] **Step 1: Add a provider test** that calls API-Tennis `get_match_snapshot(..., include_surface=False)` and asserts it requests `get_fixtures` for that match but does not request `get_draw`; assert the default call still permits existing surface enrichment.
- [ ] **Step 2: Add failing service tests** using a stored finished snapshot and `MemorySnapshotStore`. Verify an incomplete score triggers one refresh, returns and persists the score, and a second read within the existing cache TTL makes no second provider request. Also cover fully scored, live, upcoming, and provider-error cases; none may erase stored values. Add an API test asserting `/api/v1/matches/{match_id}` includes both tiebreak fields.
- [ ] **Step 3: Run the focused tests and confirm the new service/provider cases fail** before implementation.
- [ ] **Step 4: Add the optional provider keyword** to the protocol, four production providers, and listed test doubles. Keep all old one-argument calls valid through the default.
- [ ] **Step 5: Extend the existing cached metadata refresh path.** Detect metadata and score needs independently; use `include_surface=False` only when scores need repair and metadata is already complete; reuse `match-metadata:<match_id>` and the existing `reduce_live_snapshot` → repository save → hot snapshot publish flow. If refresh fails or remains incomplete, return and retain the known snapshot unchanged.
- [ ] **Step 6: Verify provider and service regressions.**

  Run: `cd backend && uv run pytest tests/test_api_tennis_provider.py tests/test_service.py tests/test_api.py -q`

  Expected: targeted tests pass; stored-score refresh makes one bounded provider call and persists the recovered fields.

- [ ] **Step 7: Stage only T103 changes in `backend/app/service.py`.** Use `git add -p backend/app/service.py`, selecting only the score-refresh hunk; inspect `git diff --cached -- backend/app/service.py` and confirm the pre-existing P3 freshness edits remain unstaged and unchanged.
- [ ] **Step 8: Commit provider/service refresh.**

  ```bash
  git add backend/app/providers/base.py backend/app/providers/api_tennis.py backend/app/providers/livetennis.py backend/app/providers/fake.py backend/app/providers/replay.py backend/tests/realtime_fakes.py backend/tests/test_runtime_api_role.py backend/tests/test_service.py backend/tests/test_p1_acceptance.py backend/tests/test_chat_orchestrator.py backend/tests/test_momentum_calibration.py backend/tests/test_api_tennis_provider.py backend/tests/test_api.py
  git commit -m "fix: repair incomplete finished match scores on read"
  ```

### Task 4: Display Tiebreak Points Across the Product

**Files:**
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/view-models.ts`
- Modify: `frontend/lib/player-view-models.ts`
- Modify: `frontend/components/match/match-hero.tsx`
- Modify: `frontend/components/match/match-main.tsx`
- Modify: `frontend/components/home/home-match-sections.tsx`
- Test: `frontend/lib/player-view-models.test.ts`
- Test: `frontend/lib/view-models.test.ts`
- Test: `frontend/components/match-page.test.tsx`
- Test: `frontend/components/home-page.test.tsx`

**Interfaces:**
- `SetScoreDto` gains two optional nullable properties, `player1_tiebreak_points?: number | null` and `player2_tiebreak_points?: number | null`, so a new frontend can consume an older API response.
- A side's score cell renders `games（tiebreak_points）` only when both values exist; normal sets remain unchanged. Player history renders the pair from the profiled player's perspective, e.g. `6–7（7–9）`.

- [ ] **Step 1: Add failing player-history assertions** for both player perspectives and a normal set beside a tiebreak set. Expected: `6–7（7–9） 6–3` for one side and `7–6（9–7） 3–6` for the other.
- [ ] **Step 2: Add failing assertions** for `toHomeMatch` data shaping and the Match-detail/Home components showing `6（7）` / `7（9）`, and proving a normal set still shows only its game count.
- [ ] **Step 3: Run the focused Vitest tests and confirm the new assertions fail.**

  Run: `cd frontend && pnpm exec vitest run lib/player-view-models.test.ts lib/view-models.test.ts components/match-page.test.tsx components/home-page.test.tsx`

- [ ] **Step 4: Add the nullable DTO fields and carry them through the Home view model.** Format only known per-player values; preserve the existing `-`, partial-score, and no-score behavior for unknown values.
- [ ] **Step 5: Render tiebreak details in both Match score tables and Home's featured score rows.** Leave regular set cells and current-point display unchanged.
- [ ] **Step 6: Run focused and full frontend checks.**

  Run: `cd frontend && pnpm exec vitest run lib/player-view-models.test.ts lib/view-models.test.ts components/match-page.test.tsx components/home-page.test.tsx && pnpm test && pnpm typecheck`

  Expected: all frontend tests and TypeScript checks pass.

- [ ] **Step 7: Commit the frontend slice.**

  ```bash
  git add frontend/lib/api/types.ts frontend/lib/view-models.ts frontend/lib/player-view-models.ts frontend/components/match/match-hero.tsx frontend/components/match/match-main.tsx frontend/components/home/home-match-sections.tsx frontend/lib/player-view-models.test.ts frontend/lib/view-models.test.ts frontend/components/match-page.test.tsx frontend/components/home-page.test.tsx
  git commit -m "fix: show tiebreak points in match scores"
  ```

### Task 5: Full Verification and Runtime Evidence

**Files:**
- Update: `CURRENT.md`, `ROADMAP.md`, and the implementation-plan checkboxes with actual results.
- Do not modify: root `.env`, database schema/data by manual scripts, approved visual baselines, or existing unrelated user changes.

- [ ] Run the deterministic backend suite using the repository's configured non-live test defaults; record actual pass/skip/failure counts.
- [ ] Run changed-file Ruff, full frontend Vitest, TypeScript, and `git diff --check`.
- [ ] Confirm the existing local runtime state before using it. Reuse it if healthy; do not run `init`, reset data, or stop services. If a code reload/restart is required for runtime verification, first report that requirement rather than silently interrupting the running stack.
- [ ] Read-only verify the same known finished-match sample through player-history API and match-detail API/browser. Assert games and tiebreak points are present and oriented correctly. Keep output restricted to internal match/player IDs, score fields, HTTP status, and freshness; never print credentials or raw supplier payloads.
- [ ] Review the final diff and status. Confirm the unrelated `backend/app/service.py` freshness hunks and all existing untracked user files remain outside T103 commits.
- [ ] Update T103 completion evidence in `CURRENT.md` and `ROADMAP.md` only after actual gates pass, then commit and push the control update to `origin/main`.

## Plan Self-Review

- **Spec coverage:** parser/canonical fields (Task 1), sparse score reducer (Task 2), bounded cached snapshot repair and provider call suppression (Task 3), three UI surfaces (Task 4), and actual backend/frontend/runtime evidence (Task 5) cover every requirement in the approved T103 spec.
- **Placeholder scan:** no `TBD`, `TODO`, deferred implementation step, or unspecified test gate remains.
- **Type consistency:** provider protocol and all production/test adapters use the same keyword-only `include_surface: bool = True`; canonical/API field names are `player1_tiebreak_points` and `player2_tiebreak_points`.
- **Review-focus coverage:** malformed input and legacy serialization are in Task 1; sparse/corrected identity-safe rows are in Task 2; bounded/no-op/error refresh cases are in Task 3; player perspective and all score surfaces are in Task 4.
