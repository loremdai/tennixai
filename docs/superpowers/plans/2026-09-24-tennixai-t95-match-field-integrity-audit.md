# T95 Match Data Field Integrity Audit Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Keep each verified defect in a separate test-first change.

**Goal:** Verify every public match-data field from API-Tennis semantics through canonical mapping, storage/reduction, REST/SSE, and the rendered page; fix each evidenced loss, stale value, wrong unit, or misleading label.

**Architecture:** Build one field-to-screen evidence matrix, then audit provider, persistence/reducer, transport, and UI boundaries in that order. Use deterministic fixtures and focused regressions; live-provider calls and shared-service restarts are not required for code-level closure. Preserve the canonical contract and keep vendor DTOs inside the provider adapter.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy/PostgreSQL, Redis/SSE, Next.js, TypeScript, pytest, Vitest, Playwright.

**Spec:** [`CURRENT.md` — T95 scope](../../../CURRENT.md#t95-范围与交接); API-Tennis [REST documentation](https://api-tennis.com/documentation) and [WebSocket documentation](https://api-tennis.com/documentation_websocket).

## Global Constraints

- The latest stored ATP/WTA singles standings snapshot is the only authority for current player rank; missing rank remains `null`.
- API-Tennis `get_fixtures` and `get_livescore` include `pointbypoint`, `scores`, and `statistics`; empty arrays mean the provider has not supplied those capabilities.
- Do not pass vendor fields into business, API, SSE, or frontend layers.
- Do not turn missing values into zero, guess unsupported metadata, add polling, change the frozen page layout, or add a provider call without evidence that it is necessary.
- Keep the root `.env`, running services, `.next`, and user-owned untracked files untouched; do not restart the shared service during this audit.
- A confirmed defect requires a failing regression before the smallest correction; tests that were not run are not completion evidence.

## Review Focus

1. A live event with no `scores` rows can still have a live state; the page must not invent a set number or render “第 0 盘”. When the provider explicitly reports `event_status: Set N`, that value is the current set even if the set-score rows are incomplete; never infer the current set from row count.
2. A statistic's canonical `unit` must survive transport and control its display; percentages must not render as counts.
3. A recognized WTA match must not enter a prediction path as ATP merely because `Tournament.tour` is missing.
4. API-Tennis may send sparse or corrected frames; absent fields must preserve known state only where the provider contract defines omission as “not updated”, and must not resurrect stale authoritative values.
5. Tie-break/PBP flags and timestamps must retain their source meaning; when official semantics are undocumented, keep the field unavailable rather than infer it.

---

## Task 1: Create the End-to-End Field Evidence Matrix

**Files:**
- Create: `docs/research/2026-09-24-tennixai-t95-match-field-integrity-matrix.md`
- Read: `backend/app/domain.py`, `backend/app/providers/api_tennis_dtos.py`, `backend/app/providers/api_tennis.py`, `backend/app/providers/api_tennis_live.py`, `backend/app/realtime/reducer.py`, `backend/app/realtime/worker.py`, `backend/app/persistence/repositories.py`, `backend/app/api/schemas.py`, `backend/app/api/routes.py`, `frontend/lib/api/types.ts`, `frontend/lib/view-models.ts`, `frontend/components/match/`

- [x] Enumerate every field in `Match`, `Player`, `Tournament`, `LiveMatchState`, `MatchScore`, `SetScore`, `PointEvent`, `MatchStatistic`, `MomentumObservation`, `DataQuality`, `DataFreshness`, and `MatchSnapshot`.
- [x] For each field, record source field or “not provided”, canonical mapping, DB/reducer owner, REST/SSE exposure, page consumer, null/empty meaning, unit/timezone, and the exact test or official source that proves it.
- [x] Mark each row `verified`, `bug fixed`, or `unavailable by provider contract`; do not mark a field verified solely because a broad test suite passes.
- [x] Verify the inventory covers all 22 `StatisticName` values and every MatchSnapshot child collection.
- [x] Review the matrix against the API-Tennis REST and WebSocket docs and the checked-in fixtures; explicitly label any undocumented semantics as unknown.

**Verification:** `rg -n "class (Match|Player|Tournament|LiveMatchState|MatchScore|SetScore|PointEvent|MatchStatistic|MomentumObservation|DataQuality|DataFreshness|MatchSnapshot)" backend/app/domain.py`; compare each declaration with one matrix row; `git diff --check`.

## Task 2: Prevent Invented Zero-Set Labels

**Files:**
- Modify: `frontend/components/match/match-hero.tsx`
- Modify: `frontend/components/match/match-main.tsx`
- Test: `frontend/components/match-page.test.tsx`
- Reference: `backend/app/providers/api_tennis.py::map_live_state`

- [x] Add a live-match test with `score.sets=[]`, a valid live state, and current point score; assert the page does not contain `第 0 盘` or a fabricated set score.
- [x] Run `cd frontend && pnpm test -- components/match-page.test.tsx`; confirm the new assertion fails against current code.
- [x] Render a truthful unavailable label for set-level score when no set rows exist; retain the current layout and continue showing any supplied game-point score.
- [x] Re-run the focused test and `cd frontend && pnpm test -- components/match-page.test.tsx`.

## Task 3: Honor Canonical Statistic Units in the UI

**Files:**
- Modify: `frontend/components/match/match-statistics.tsx`
- Test: `frontend/components/match/match-statistics.test.tsx`
- Reference: `backend/app/providers/api_tennis.py::STAT_NAME_MAP`, `map_statistics`; `backend/tests/fixtures/api_tennis/livescore.json`

- [x] Add tests passing `unit: "percent"` for `total_points_won` and `total_games_won`; assert values render with `%`.
- [x] Run `cd frontend && pnpm test -- components/match/match-statistics.test.tsx`; confirm the new percentage assertions fail against the static `STAT_META` units.
- [x] Use `stat.unit ?? meta.unit` when constructing the display row, retaining metadata only as the fallback for preview/custom payloads that omit a unit.
- [x] Run the focused test, then `cd frontend && pnpm test -- components/match/match-statistics.test.tsx` and `cd frontend && pnpm typecheck`.
- [x] Extend the field matrix with the verified raw statistic, canonical unit, and rendered string for every statistic represented by fixtures.

## Task 4: Preserve ATP/WTA Tour Identity Through Prediction Inputs

**Files:**
- Modify: `backend/app/providers/api_tennis.py`
- Modify: `backend/app/prediction/service.py` only if a missing tour can still silently default to ATP
- Test: `backend/tests/test_api_tennis_provider.py`
- Test: prediction-service tests under `backend/tests/`
- Reference: `backend/app/providers/api_tennis_classification.py`, `backend/app/prediction/service.py::_predict_prematch`, `backend/app/domain.py::Tournament`

- [x] Add provider tests for `Atp Singles` and `Wta Singles` fixtures; require `tournament.circuit` and `tournament.tour` to preserve the ATP/WTA distinction in canonical lowercase form.
- [x] Add a prediction-service regression proving a WTA snapshot supplies `tour="wta"` to `HistoricalMatch`, and an eligible snapshot with unknown tour does not silently become ATP.
- [x] Run the new tests and confirm they fail against `map_match` setting `tour=None` and `_predict_prematch` using `or "atp"`.
- [x] Map only explicitly recognized ATP/WTA event families; leave other event families unknown. Make prediction abstain with a typed unavailable reason if required tour identity is missing.
- [x] Run the provider and prediction-service focused test files plus Ruff for changed backend files.
- [x] Confirm Challenger/ITF and doubles remain out-of-domain and no new coverage is granted.

## Task 5: Audit Score, Server, PBP, and Freshness Semantics

**Files:**
- Modify only if an evidenced discrepancy: `backend/app/providers/api_tennis.py`, `backend/app/providers/api_tennis_live.py`, `backend/app/realtime/reducer.py`, `backend/app/realtime/worker.py`, persistence models/repositories, and their existing tests.
- Tests: `backend/tests/test_api_tennis_provider.py`, `backend/tests/test_api_tennis_live_feed.py`, `backend/tests/test_live_reducer.py`, `backend/tests/test_realtime_worker.py`, `frontend/components/match/match-points.test.tsx`, `frontend/hooks/use-match-stream.test.tsx`.

- [x] Trace `event_final_result`, `event_game_result`, `scores[].score_first/score_second/score_set`, `event_serve`, `event_winner`, and every PBP field from raw DTO through persisted snapshot and UI.
- [x] Verify normal points and tie-break score representations separately; add a regression for each source representation actually documented or present in a sanitized provider fixture.
- [x] Verify PBP point identity and ordering under repeated/missing vendor point numbers, correction revisions, duplicates, and reconnect snapshot replacement.
- [x] Verify status transitions, scheduled time in the requested GMT timezone, `source_updated_at` versus `observed_at`, `as_of`, age/stale state, and sparse-frame merge rules at both REST and WebSocket boundaries.
- [x] For each mismatch, add a failing test, apply one minimal correction, and rerun the owning focused suites; if provider documentation does not define behavior, record the field as unavailable/unknown in the matrix instead of guessing.

## Task 6: Audit Statistics, Momentum, and Capability Availability

**Files:**
- Modify only if an evidenced discrepancy: `backend/app/providers/api_tennis.py`, statistics/momentum reducer and repositories, their DTOs, `frontend/components/match/match-statistics.tsx`, `frontend/components/match/match-momentum.tsx`, and owning tests.
- Tests: `backend/tests/test_api_tennis_provider.py`, `backend/tests/test_live_reducer.py`, `frontend/components/match/match-statistics.test.tsx`, `frontend/components/match/match-momentum.test.tsx`.

- [x] For each of the 22 statistic names, verify provider name, period, player-side mapping, `stat_value`, `stat_won`/`stat_total` when present, canonical unit, availability, and per-stat `as_of`.
- [x] Verify sparse WebSocket updates retain only truly omitted old metrics as stale; new same-value observations refresh their timestamps; empty rows do not become zeroes.
- [x] Verify momentum provenance, algorithm version, input version, provisional status, and the exact reason when unavailable.
- [x] Add or correct focused tests for every discovered mismatch, then verify all statistics and momentum render only available canonical values.

## Task 7: Close the Public Contract and Field Audit

**Files:**
- Update: `docs/research/2026-09-24-tennixai-t95-match-field-integrity-matrix.md`
- Tests: relevant backend API/SSE and frontend transport/component tests identified by the matrix.

- [x] Compare REST snapshot and first SSE `ready` frame field-for-field; compare subsequent `match_delta` updates with their persisted snapshot and `state_version`.
- [x] Verify nullable/missing fields remain nullable through Pydantic response models, TypeScript DTOs, and UI; verify unsupported provider fields never leak.
- [x] Run the full deterministic backend suite and frontend unit/typecheck gates that do not restart services or touch `.next`; run focused PostgreSQL integration tests for changed persistence paths.
- [x] Review every matrix row; each must have source semantics plus code-path evidence and a named test, or be explicitly marked unavailable/unknown with a reason.
- [ ] Record commit IDs, exact test counts, unresolved provider-semantic limits, and the separately authorized runtime restart gate in `CURRENT.md` and `ROADMAP.md`.

## Known Runtime Gate

An earlier local process returned Martin Damm at rank 741 while the latest ATP standings snapshot and ATP official page both returned 106. T92/T94 corrected the code path, and a bounded live API-Tennis standings smoke test authenticated and mapped the current ranking successfully. This task did not start/restart the shared application or run browser verification; that runtime check remains a separate gate.

## Independent Review Follow-ups

- [x] Keep undocumented API-Tennis point flags unknown; migration `0007` makes unknown legacy values nullable and refuses lossy downgrade.
- [x] Preserve persisted freshness on rollback; migration `0008` refuses downgrade while any snapshot has non-null freshness.
- [x] Carry exact live `Set N` provider status through canonical state, PostgreSQL JSON, REST/SSE contract, and both match-page score labels/highlights; unknown status remains unavailable.
- [x] Use coherent percentage-shaped values for the seven percent-unit metrics in the replay fixture and assert their canonical values.
- [x] Distinguish provider-confirmed PBP values from local fallback/grouping policy in the evidence matrix.
