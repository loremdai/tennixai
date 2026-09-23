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
- Keep the last statistic values and their original `as_of`; mark them stale when a later snapshot omits statistics. A subsequent non-empty statistics snapshot replaces the old rows and restores provider availability.
- Do not restart the shared local services or modify `.env`.

## Implementation steps

1. Add a reducer regression test for a previous snapshot with statistics followed by a score-only candidate with `statistics=()` and capability unavailable. Verify values remain, original per-stat timestamps remain, and the effective statistics/quality are stale rather than unavailable. Run it and observe the expected failure before changing production code.
2. Implement the narrowest reducer merge: an empty candidate statistics list does not erase prior rows; mark retained rows and capability stale. Keep the existing non-empty replacement behavior. Verify focused reducer tests.
3. Add frontend regression coverage proving the statistics card uses the newest `MatchStatistic.as_of`, not the enclosing `MatchSnapshot.as_of`, and makes retained stale values visibly stale. Remove the misleading global snapshot-time input if no longer needed.
4. Run backend reducer/provider focused tests, frontend statistics tests, full deterministic backend and frontend unit/typecheck gates, changed-file Ruff, and `git diff --check`. Do not run a production build or Playwright against the shared `.next` runtime unless it can be done without interrupting or modifying that runtime.

## Acceptance criteria

- Empty WebSocket statistics do not clear previously observed statistics.
- Retained data preserves its original values and timestamps and is visibly marked stale.
- New non-empty statistics replace retained values and are no longer stale.
- A score/PBP update with omitted statistics does not claim the statistics themselves were refreshed.
- No additional upstream requests, polling, migrations, or unrelated product changes.
