# T97 — Global Field Presentation Audit

**Status:** Planned / in progress  
**Owner:** Codex on `main`  
**Start HEAD:** `c84fa6d`  
**Date:** 2026-09-24

## Goal

Use the browser to audit the whole user-facing product, not only the current T94 ranking check. Find fields that are missing, inaccessible, mislabeled, incorrectly formatted, clipped, stale without explanation, or shown with misleading fallbacks. Distinguish provider limitations from defects in mapping, API transport, view models, and UI. Fix only issues proven with a concrete example and add regression coverage.

## Surfaces and field groups

1. **Home and global search:** search identity/rank/nationality, schedule filters, tournament/round/surface, Beijing start time, match status/score/server, recent results, structured chat match/history answers, loading/error/empty/partial/stale states.
2. **Players directory and ranking pages:** ATP/WTA tour, rank, English/Chinese names, nationality/flag, points, movement, snapshot date/as-of, search/filter/pagination and empty/error states.
3. **Player profile and results:** identity, ranking/points/date/movement, nationality/flag, birth date/age, photo fallback, current/next match, season selector, win/loss/titles/surface records, results filters/scores/winner/date/tournament/round/surface, partial coverage, pagination and empty states.
4. **Match detail:** event/tournament/round/tour/circuit/gender/discipline/surface/format, scheduled time/status, players/ranks/nationality, set/game/current-point score, server, freshness/connection, statistics (all 22 canonical metrics, units, period, per-side missingness and stale/partial state), point timeline/quality, momentum/derived-data labels, chat context, market quotes, decision explanation and paper lifecycle.
5. **Markets and Paper:** all-market quotes (both sides, bid/ask, spread, depth, observation time, market-only/unmapped labels), opportunity eligibility/edge/confidence/reasons/empty states, paper positions/actions/entry-exit/settlement/status/history and errors. Confirm no live external order is possible or triggered.
6. **Cross-cutting:** responsive desktop/mobile layout, truncation/overflow, labels/units, unknown-value copy, China/Beijing timezone wording, navigation, and no supplier IDs/raw payloads/secrets in rendered UI.

## Execution

1. Reconcile this checklist against `PROJECT.md`, `ROADMAP.md`, `CURRENT.md`, the existing T95–T96 field matrix, canonical response types, route consumers, and current E2E scenarios. Extend the evidence matrix for P3 market/opportunity/paper fields where it does not yet cover them.
2. Run the existing deterministic UI tests and Playwright scenarios that can run without a real local runtime. Inspect the actual rendered pages in a browser at desktop and mobile sizes using known test fixtures; record which states/data each fixture represents.
3. Attempt the real local-stack/browser check using the project's `tennix-live up` and approved non-LLM verification path. Do not run `init`, manually migrate, or alter `.env`; if the stack is uninitialized, record this as a distinct real-data blocker and continue only with the fixture-backed audit.
4. For each suspected issue, save a sanitized example and trace it through provider mapping → canonical model → persistence/cache/reducer → REST/SSE → frontend view model → rendered field. Classify it as provider-unavailable/undocumented, data/mapping, transport/state, or presentation. Never turn unavailable data into guessed values.
5. Fix confirmed in-scope defects with a regression test first; update the field matrix with source, semantics, consumer, and proof. Do not redesign the product or add provider calls/capabilities outside a verified fix.
6. Run affected tests, full frontend unit/type checks, bounded Playwright/browser checks, formatting/lint for changed files, and `git diff --check`. Preserve user-owned untracked files and the existing `.next` directory.
7. Update `CURRENT.md` and `ROADMAP.md` with verified findings, remaining provider/runtime limitations, commits, and actual test outcomes; commit and push the task results to `origin/main`.

## Acceptance gate

- Every currently visible product surface above is opened or exercised in a browser; unavailable runtime-only surfaces are explicitly marked blocked rather than assumed good.
- A field-coverage checklist records display/value source, expected null/partial behavior, and browser proof for each relevant user-facing group.
- No confirmed presentation/data defect is left unfixed without a concrete blocker and a corresponding record in `CURRENT.md`.
- Full required deterministic checks pass; real-data browser checks are separately reported as pass/fail/blocked and never conflated with fixture success.
- Control documents match the actual Git HEAD and working tree, and task changes are committed/pushed.

## Safety boundaries

- Do not inspect, print, change, or commit the root `.env` or any credentials.
- Do not run the LLM-consuming `init` or bypass it with direct migrations; stop at that boundary and request approval if real data requires it.
- Do not stop or alter unrelated user services/containers. Stop only processes/containers started by this task if cleanup is necessary.
- Browser checks must stay read-only with respect to external services; paper actions are test/demo-only and no Polymarket order or transaction may be submitted.
