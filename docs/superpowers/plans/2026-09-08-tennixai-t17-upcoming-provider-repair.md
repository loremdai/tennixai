# T17 Real Upcoming Provider and Partial Failure Handling Implementation Plan

> **Configuration path superseded on 2026-09-09:** M01 made the repository-root `.env` / `.env.example` the only current configuration entry. Any `backend/.env` reference below is historical and must not be followed.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or **superpowers:executing-plans** to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the P1 real upcoming-match path so current LiveTennisAPI data reaches the canonical model, player-specific upcoming queries use the provider's filter without unbounded pagination, and a single live/upcoming failure no longer hides healthy Home content.

**Architecture:** Keep `TennisDataProvider`, `TennisService`, internal IDs, and the Next.js Route Handler proxy as the stable boundaries. `LiveTennisProvider.get_fixtures()` will read the current `/matches?status=upcoming` nested match shape and map it through the existing canonical mapper. When a canonical player ID is supplied, the provider will reverse-map it to the LiveTennisAPI player ID and send `player=<external-id>`; the provider will still defensively filter the mapped response locally. A global listing will intentionally consume only the API's first page, because P1 has no pagination UI and Free Tier quota is finite. Home will load live and upcoming independently with `Promise.allSettled`, while preserving the existing all-failed retry panel. Chat errors will retain provider details so a 429 can be explained with its retry window.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, httpx, pytest/pytest-asyncio, Next.js, TypeScript, React, Vitest, Testing Library, Playwright, existing LiveTennisAPI provider.

**Spec:** [Product and architecture context](../product-context.md), [P1 implementation plan](2026-09-08-tennixai-p1-implementation.md), [T17 registration and root cause](../../../CURRENT.md), and [project roadmap](../../../ROADMAP.md).

## Global Constraints

- Preserve the approved P1 boundary: no PostgreSQL, Redis, history queries, polling, P2 statistics/PBP, Polymarket, or new provider.
- Do not expose LiveTennisAPI or LLM credentials in code, tests, control files, browser bundles, command output, or commits. The local ignored `backend/.env` is the only runtime secret store.
- Keep vendor fields inside `LiveTennisProvider`; all service and UI code continues to consume canonical models and internal IDs.
- Use the current `/matches` response shape. Do not restore the incompatible production dependency on `/fixtures`.
- Do not add an unbounded pagination loop. The unfiltered Home request is one provider page; the player-specific request uses the provider `player` filter and one page.
- Every production behavior change starts with a failing regression test. The deterministic fake suite remains the default gate; real provider/LLM/browser tests remain opt-in.
- Keep manual refresh only. A retry button may issue a new request, but no timer or automatic polling may be introduced.

---

### Task 1: Add a failing provider contract for the current upcoming endpoint

**Files:**
- Modify: `backend/tests/test_livetennis_provider.py`
- Reuse: `backend/tests/fixtures/livetennis/fixtures.json` as the current nested `/matches?status=upcoming` payload, or add a focused `matches_upcoming.json` fixture if the existing fixture needs to remain endpoint-specific.

**Interfaces:**
- Consumes: the existing nested provider payload with `id`, `players.p1/p2`, `scheduled_time`, tournament, round, surface, and status fields.
- Produces: canonical `Match` objects and a request contract for `/matches`, `status=upcoming`, and optional provider `player` ID.

- [ ] **Step 1: Update the mock route and add assertions before changing production code**

  Make the test transport return the nested upcoming payload for `/matches?status=upcoming`. Keep the old `/fixtures` branch only if another test still needs it, but make the new assertions require `get_fixtures()` to request `/matches`. Add a test that calls `get_fixtures()` and asserts:

  - the path ends in `/matches`;
  - `status=upcoming` is present;
  - no `offset` or pagination loop is sent for the global listing;
  - the nested players, scheduled UTC timestamp, tournament, round, surface, and scheduled status map to canonical fields;
  - the internal match and player IDs do not contain vendor IDs.

  Add a player-specific case that first resolves a player through `search_players()`, then calls `get_fixtures(player_id=<internal-id>)`, and asserts `player=<external-provider-id>` is present on the `/matches` request and the returned canonical match contains that internal player ID.

- [ ] **Step 2: Run the focused tests and verify the expected failure**

  Run:

  ```bash
  cd backend && uv run pytest tests/test_livetennis_provider.py -k "upcoming or fixture_ids or local_player_filter" -v
  ```

  Expected: FAIL because the current implementation requests `/fixtures`, parses a fixture-only path, and never sends the provider player filter.

- [ ] **Step 3: Keep existing provider behavior covered**

  Retain the existing assertions for live score mapping, identity stability, error translation, null fields, and vendor-field isolation. The new contract must not weaken those tests or make vendor DTOs visible above the provider boundary.

### Task 2: Repair `LiveTennisProvider` without expanding the provider abstraction

**Files:**
- Modify: `backend/app/providers/livetennis.py`
- Test: `backend/tests/test_livetennis_provider.py`

**Interfaces:**
- Consumes: `player_id` as a canonical internal ID from `TennisService`.
- Produces: `list[Match]` from the current `/matches` endpoint, with stable canonical identities and typed provider failures.

- [ ] **Step 1: Implement the smallest request change**

  Add a private helper that resolves a canonical player ID through `MemoryIdentityRepository.external_id("player", PROVIDER_NAME, player_id)`. If a non-null internal player ID has no provider mapping, return an empty result without making a broad provider request. Otherwise build params with `status="upcoming"` for fixtures and add `player=<external-id>` when applicable.

- [ ] **Step 2: Map upcoming rows through the existing canonical path**

  Change `get_fixtures()` to call `self._request("/matches", params)` and validate/map the payload with `LiveMatchDto`, then apply the existing defensive internal-ID filter. Do not add a second mapper or copy vendor field names into service code. Apply the same provider-side player filter to `get_live_matches()` when `player_id` is supplied so a two-status player query remains quota-conscious.

- [ ] **Step 3: Run the focused provider tests**

  Run:

  ```bash
  cd backend && uv run pytest tests/test_livetennis_provider.py -k "upcoming or fixture_ids or local_player_filter" -v
  cd backend && uv run pytest tests/test_livetennis_provider.py -v
  ```

  Expected: the new endpoint/filter contract and the existing provider suite pass. Confirm the implementation has no loop over `meta.has_more` and no broad fallback request for an unresolved internal player ID.

### Task 3: Verify service/API behavior remains canonical and quota-bounded

**Files:**
- Test: `backend/tests/test_provider_contract.py`
- Test: `backend/tests/test_service.py`
- Test: `backend/tests/test_api.py`
- Modify only if a regression is found: corresponding service/API implementation

**Interfaces:**
- Consumes: provider canonical `Match` objects and internal player IDs.
- Produces: the existing `/api/v1/matches?status=upcoming` and chat-tool contracts.

- [ ] **Step 1: Add the failing service/API assertions if the current suite lacks them**

  Assert that a player-specific upcoming query reaches the provider with a canonical player ID and returns only that player's matches. Assert that the REST response contains scheduled time, tournament, round, surface, and internal IDs. Add a spy-provider assertion that the service still calls the provider once for a non-cached listing and does not introduce pagination.

- [ ] **Step 2: Run the focused service/API tests**

  Run:

  ```bash
  cd backend && uv run pytest tests/test_provider_contract.py tests/test_service.py tests/test_api.py -v
  ```

  Expected: existing time-window, cache, ambiguity, REST error, and canonical-shape tests remain green. Do not alter historical-query behavior; it must continue to return the typed P1 unsupported result without a provider call.

### Task 4: Make Home live/upcoming failures independent and make 429 chat errors readable

**Files:**
- Modify: `frontend/components/home-page.tsx`
- Modify: `frontend/components/home/home-match-sections.tsx`
- Modify: `frontend/hooks/use-chat-stream.ts`
- Modify: `frontend/components/home/home-assistant.tsx`
- Test: `frontend/components/home-page.test.tsx`
- Test: `frontend/hooks/use-chat-stream.test.tsx`

**Interfaces:**
- Consumes: typed `ApiError`/SSE error payloads, including `details.retry_after`.
- Produces: independent live/upcoming section states, existing all-failed retry UX, and a human-readable rate-limit message without losing structured data.

- [ ] **Step 1: Add failing frontend tests**

  Add a Home test where `getMatches("live")` rejects with `provider_unavailable` while `getMatches("upcoming")` resolves. Assert that the upcoming card/section remains visible, the live section shows a typed retry state, and the whole-page `SlateErrorPanel` is not shown. Add the inverse case only if the implementation shape makes it necessary; both statuses must be independently represented.

  Add a stream-hook test whose terminal error event is `{ code: "rate_limited", details: { retry_after: "30" } }`; assert the hook preserves both `code` and `details`. Add a Home assistant assertion that the user-facing copy mentions that the data-service quota is temporarily exhausted and includes the retry interval, while the retry action remains available.

- [ ] **Step 2: Run the focused tests and verify the expected failure**

  Run:

  ```bash
  cd frontend && pnpm test -- components/home-page.test.tsx hooks/use-chat-stream.test.tsx
  ```

  Expected: FAIL because `Promise.all` currently turns one slate failure into one global error, the hook drops SSE `details`, and the assistant renders only the raw error code/message.

- [ ] **Step 3: Implement independent slate state with the existing visual contract**

  Replace the all-or-nothing `Promise.all` path with `Promise.allSettled`. Track live and upcoming matches plus their individual loading/success/error states and codes. Keep a global `SlateErrorPanel` only when both requests fail. Pass section-specific state/error information to `LiveNowSection` and `UpcomingSection`; each failed section gets one manual retry affordance through the existing `loadSlate` callback, while a healthy section renders normally. Derive the featured match/state from whichever healthy result is available.

- [ ] **Step 4: Preserve provider details through the chat hook and format only the UI copy**

  Extend `ChatViewState.error` with `details`. Store `event.payload.details` for SSE errors and preserve details from typed transport errors when available; default to `{}` for generic failures. In `HomeAssistant`, format `rate_limited` using `details.retry_after` when present and fall back to a concise quota-unavailable message when absent. Keep structured `data` and partial text when an error arrives, preserve the existing generic code copy for other errors, and keep the retry button.

- [ ] **Step 5: Run focused frontend tests**

  Run:

  ```bash
  cd frontend && pnpm test -- components/home-page.test.tsx hooks/use-chat-stream.test.tsx
  ```

  Expected: the new partial-failure/429 tests and all existing Home/chat tests pass, including no-polling and all-failed retry behavior.

### Task 5: Update opt-in real gates and the local runbook

**Files:**
- Modify: `backend/tests/live/test_provider_live.py` only if the existing live gate needs an explicit upcoming assertion
- Modify: `frontend/e2e/end-to-end-live.spec.ts` only if the existing live flow needs a current upcoming/player-filter assertion
- Modify: `docs/runbooks/p1-local.md`

- [ ] **Step 1: Keep real tests opt-in and quota-aware**

  Update the provider-live/browser-live checks to use a single bounded upcoming request or one specific-player request. If the live API returns no upcoming data, record a truthful skip/empty result rather than retrying or paging through the API. Do not hard-code a player, match, or secret whose availability can change; the real manual verification will use the currently observed Qinwen Zheng vs Elena Rybakina fixture when it is present.

- [ ] **Step 2: Document the new runtime behavior**

  Add the T17 facts to `docs/runbooks/p1-local.md`: upcoming reads `/matches?status=upcoming`, global Home reads one page, player queries use provider filtering, Free Tier quota is finite, 429 exposes `Retry-After`, and retries are manual. Include safe redacted commands for health/upcoming checks without embedding a key.

- [ ] **Step 3: Run any available opt-in checks once**

  With the already-persisted local credentials, run the provider gate and the real browser gate only after deterministic tests pass. Record whether the result is passed, an honest empty response, a typed 429, or skipped; do not spend quota on repeated retries.

### Task 6: Full verification, browser acceptance, and control-file handoff

**Files:**
- Modify: `ROADMAP.md`
- Modify: `CURRENT.md`
- Modify only if the stable product boundary changed: `PROJECT.md`

- [ ] **Step 1: Run the deterministic backend and frontend gates**

  Run:

  ```bash
  cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live"
  cd frontend && pnpm test && pnpm typecheck && pnpm build && pnpm test:e2e
  ```

  Also run the T17-focused provider, API, Home, and hook tests explicitly so their output is easy to cite in the handoff.

- [ ] **Step 2: Perform one real browser business-flow acceptance**

  Keep the local backend/frontend running with the persistent `.env` configuration. In the browser, refresh Home, confirm Live Now and Upcoming are independently rendered, ask for Zheng Qinwen's next match, verify the structured card shows the opponent, tournament, round, local time, surface, and internal Match link, open the Match page, and verify the contextual question path. If the provider returns a typed rate limit, verify the friendly message and retry affordance instead of claiming live-data success.

- [ ] **Step 3: Update the three control files with evidence**

  When every required gate has fresh output, mark T17 `done`, close P1.6/P1 only if the real boundary is actually verified, and record exact commit IDs and command results in `ROADMAP.md` and `CURRENT.md`. If the real provider is empty or rate-limited, keep that fact explicit and do not convert it into a pass claim.

- [ ] **Step 4: Commit and push only task-owned changes**

  Keep `.codex/`, generated frontend instruction files, and local `.env` files untracked/ignored. Commit source, tests, plan, runbook, and control-file updates, then push the T17 implementation to `origin/main`. Verify the final branch, HEAD, worktree status, and remote commit before reporting completion.
