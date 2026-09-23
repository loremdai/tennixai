# T93 — Preserve Live Statistics Across Sparse WebSocket Updates

## Goal

Keep the latest real match-statistics values when API-Tennis sends a live WebSocket snapshot with an empty `statistics` array, and make their original observation time visible instead of presenting the enclosing match snapshot time as the statistics update time.

## Evidence and scope

- The official [API-Tennis WebSocket documentation](https://api-tennis.com/documentation_websocket) describes score/PBP event updates and its sample message has `statistics: []`.
- The official [REST documentation](https://api-tennis.com/documentation) shows `get_livescore` / fixtures carrying inline statistics when available.
- `RealtimeWorker` obtains REST snapshots when opening a subscription and after reconnect. Connected WebSocket rows are then reduced as full candidate snapshots.
- A local reducer probe reproduced the defect: one previously available statistic becomes zero rows after a score update with an empty statistics list; the reducer emits `statistics_updated` and reports the capability unavailable.
- `MatchMainColumn` currently passes `MatchSnapshot.as_of` to the statistics card. Each `MatchStatistic` already has its own `as_of` timestamp.

## Constraints

- Do not add polling, provider calls, database schema changes, or dependencies.
- Preserve PBP, score, player, market, decision, and Paper behavior.
- Merge statistics by `(name, period)`: an incoming row replaces that metric; previously known metrics omitted from a sparse snapshot are retained with their original values and `as_of`, but marked stale. If no rows are supplied, all retained rows are stale. A later row for that metric restores its provider availability. Preserve row-level `partial` values when fresh; report aggregate capability `partial` when fresh and stale metrics coexist, and `stale` when only retained metrics remain.
- Do not restart the shared local services or modify `.env`.

## Implementation steps

1. Add reducer regression tests for an empty score-only candidate and a partially populated candidate. Verify omitted metrics remain with their old values/timestamps and stale status, incoming metrics replace only their matching key, and aggregate quality accurately reports stale/partial. Run them and observe the expected failures before changing production code.
2. Implement keyed sparse-field merge in the reducer while preserving full replacement for fields explicitly present in the candidate. Verify focused reducer tests and existing non-empty replacement behavior.
3. Add frontend regression coverage proving the statistics card uses the newest `MatchStatistic.as_of`, not the enclosing `MatchSnapshot.as_of`, and distinguishes retained stale metrics from provider-partial metrics. Remove the misleading global snapshot-time input if no longer needed.
4. Run backend reducer/provider focused tests, frontend statistics tests, full deterministic backend and frontend unit/typecheck gates, changed-file Ruff, and `git diff --check`. Do not run a production build or Playwright against the shared `.next` runtime unless it can be done without interrupting or modifying that runtime.

## Acceptance criteria

- Empty or sparse WebSocket statistics do not erase previously observed metrics.
- Retained data preserves its original values and timestamps and is visibly marked stale; fresh incoming metrics replace only matching metric/period keys.
- Aggregate capability quality distinguishes all-stale from mixed fresh/stale data.
- A score/PBP update with omitted statistics does not claim the statistics themselves were refreshed.
- No additional upstream requests, polling, migrations, or unrelated product changes.

## Implementation result (2026-09-24)

- The reducer now merges by `(name, period)`: incoming rows replace matching rows, omitted prior rows retain their values and observation times but become stale. Aggregate quality becomes `stale` when all retained rows are old and `partial` when fresh and retained rows coexist. A fresh observation advances the row timestamp and reduction even when numeric values are unchanged; repeated omitted frames remain a no-op.
- The match statistics card derives its footer from the newest statistic row, labels stale rows with their own formatted observation time, and notes that per-row times can differ. The enclosing match timestamp is no longer passed as if it were a statistics timestamp.
- Verification after final-review fixes: focused backend reducer/provider tests `71 passed`; focused frontend statistics tests `7 passed`; the full deterministic backend suite `1241 passed, 127 deselected`; frontend Vitest `416 passed`; TypeScript `tsc --noEmit` passed; changed-file Ruff lint and `git diff --check` passed.
- Ruff format check still reports pre-existing formatting differences in the two touched Python files. Comparing formatter output for their pre-task `HEAD` versions shows those differences are in untouched legacy sections; no whole-file reformat was applied.
- Production build and Playwright were not run because the shared local runtime is active and its `.next` output/user-owned `frontend/next-env.d.ts` must be preserved. Services were not restarted and root `.env` was not read or modified.

### Final review record

- `Final: fixed stale-row timestamp visibility` — frontend regression assertion failed before the row displayed its own `as_of`, then passed after the timestamp was rendered beside the stale label; full suite `416/416` passed.
- `Final: fixed unchanged-value observation loss` — `test_unchanged_fresh_metric_advances_its_observation_time` failed before `as_of` participated in the reducer fingerprint, then passed after the fix; full deterministic backend suite `1241/1241` passed. The empty-frame regression also confirms repeated omissions remain a no-op.
- `Final: minor (deferred): snapshots lacking statistics quality metadata do not synthesize an aggregate quality row, and row-level stale states are not used to derive aggregate status. The API-Tennis adapter currently emits statistics quality for every snapshot; defer general custom-provider hardening to a broader provider-contract audit.`
