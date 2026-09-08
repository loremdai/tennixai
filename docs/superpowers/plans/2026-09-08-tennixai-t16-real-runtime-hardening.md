# T16 Real Runtime Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the P1 real LiveTennisAPI → business tools → OpenAI-compatible LLM → SSE path bounded and usable without changing the approved product scope.

**Architecture:** Keep the full canonical result in the `data` SSE event for the UI, but send a compact, capped match projection to the LLM tool message. Bound both non-streaming tool selection and streaming prose with one configurable timeout, preserving the existing typed fallback. Resolve player queries at the service boundary by deduplicating normalized display names and excluding composite team names from single-player resolution.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings, OpenAI-compatible Chat Completions, pytest/pytest-asyncio, existing LiveTennisAPI provider.

**Spec:** [Product and architecture context](../product-context.md), [P1 implementation plan](2026-09-08-tennixai-p1-implementation.md), and the real-runtime findings recorded in `CURRENT.md` before T16.

## Global Constraints

- Preserve the approved P1 boundary: no PostgreSQL, Redis, polling, history queries, P2 statistics/PBP, or new provider.
- Keep canonical domain models and the provider interface unchanged.
- Keep full structured data available to the UI; only the LLM context is compacted.
- Keep all LLM and provider credentials server-side and out of Git.
- Every production behavior change must have a failing regression test before implementation.
- The deterministic fake suite remains the default gate; real provider/LLM gates remain opt-in.

### Task 1: Bound the LLM Tool Context

**Files:**
- Modify: `backend/app/chat/orchestrator.py`
- Test: `backend/tests/test_chat_orchestrator.py`

**Interfaces:**
- Consumes: `StructuredToolResult` returned by `BusinessTools.execute`.
- Produces: the existing full `data` event and a compact JSON tool message for the next model turn.

- [ ] **Step 1: Write the failing test**

  Add a wide fake provider case that returns more than 12 live matches. Assert that the emitted `data` event still contains every canonical match, while the tool message retained in the model's messages contains at most 12 compact match summaries, includes `match_count` and `truncated`, and omits verbose `freshness`/nested provider-shaped fields.

- [ ] **Step 2: Run the focused test and verify the expected failure**

  Run:

  ```bash
  cd backend && uv run pytest tests/test_chat_orchestrator.py -k bounded -v
  ```

  Expected: FAIL because the current tool message serializes the complete `StructuredToolResult` without a cap or projection.

- [ ] **Step 3: Implement the narrow projection**

  Add a private orchestrator helper with a fixed `MAX_MODEL_MATCHES = 12`. For each match send only the internal match ID, lifecycle status, player names, tournament name, scheduled time, round, surface, indoor/format, compact score, server/winner player names, and stale marker. Include `match_count` and `truncated` at the result root. Use this helper only for `messages.append({"role": "tool", ...})`; leave the yielded SSE payload as `result.model_dump(mode="json")`.

- [ ] **Step 4: Run the focused test and the chat suite**

  Run:

  ```bash
  cd backend && uv run pytest tests/test_chat_orchestrator.py -k bounded -v
  cd backend && uv run pytest tests/test_chat_orchestrator.py -v
  ```

  Expected: the new regression test and all existing orchestrator tests pass.

### Task 2: Add a Configurable, Total LLM Timeout

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/chat/client.py`
- Test: `backend/tests/test_chat_client.py`
- Modify: `docs/runbooks/p1-local.md`
- Modify: local ignored `backend/.env` only if the persistent runtime config lacks the new setting

**Interfaces:**
- Consumes: `Settings.llm_timeout_seconds`, default `45.0`, constrained to a positive value no greater than `300.0`.
- Produces: `OpenAICompatibleChatModel(..., timeout_seconds=...)` with a total timeout around both `choose` and `stream_text`, translated to the existing `llm_unavailable` error and fallback path.

- [ ] **Step 1: Write the failing tests**

  Add a fake OpenAI-compatible client test whose streaming iterator never yields before the deadline. Construct `OpenAICompatibleChatModel` with a very small `timeout_seconds`, assert the call raises `AppError` with code `llm_unavailable`, and assert the SDK client receives the same timeout. Add a settings test for the configurable value.

- [ ] **Step 2: Run the focused tests and verify the expected failure**

  Run:

  ```bash
  cd backend && uv run pytest tests/test_chat_client.py -v
  ```

  Expected: FAIL because the current client has no timeout constructor argument, does not pass a timeout to `AsyncOpenAI`, and does not wrap the full async stream.

- [ ] **Step 3: Implement the minimal timeout path**

  Add `llm_timeout_seconds` to `Settings`, pass it from `create_app`, and add `timeout_seconds` to `OpenAICompatibleChatModel`. Configure the SDK client timeout and wrap the complete request/iteration in `asyncio.timeout`. Translate both SDK errors and `TimeoutError` to `AppError("llm_unavailable", ...)`. Preserve existing orchestrator event ordering and fallback behavior.

- [ ] **Step 4: Run focused tests and deterministic chat/API gates**

  Run:

  ```bash
  cd backend && uv run pytest tests/test_chat_client.py tests/test_chat_orchestrator.py tests/test_chat_api.py -v
  ```

  Expected: all pass, including structured-data preservation when prose fails.

### Task 3: Make Real Player Resolution Deterministic

**Files:**
- Modify: `backend/app/service.py`
- Test: `backend/tests/test_service.py`

**Interfaces:**
- Consumes: canonical `Player` candidates from any `TennisDataProvider`.
- Produces: the existing `Player` resolution contract, with duplicate normalized names collapsed and composite team/doubles display names excluded from single-player lookup.

- [ ] **Step 1: Write the failing test**

  Add candidates containing two `Novak Djokovic` records, one composite name such as `Novak Djokovic / Casper Ruud`, and one ranked `Novak Djokovic`. Assert `list_matches("live", "Djokovic")` resolves the ranked individual and does not raise `ambiguous_player`. Keep the existing `Jannik` ambiguity test unchanged to prove genuinely different individual names remain ambiguous.

- [ ] **Step 2: Run the focused test and verify the expected failure**

  Run:

  ```bash
  cd backend && uv run pytest tests/test_service.py -k djokovic -v
  ```

  Expected: FAIL with `ambiguous_player` under the current raw substring candidate logic.

- [ ] **Step 3: Implement the service-boundary normalization**

  In `_resolve_player`, remove composite names containing `/`, `&`, or ` vs ` from single-player candidates, then collapse equal casefolded display names by preferring a candidate with a non-null lower ranking and preserving provider order for a complete tie. Apply exact-name preference after normalization; preserve `not_found` and true ambiguity errors.

- [ ] **Step 4: Run the focused and full service tests**

  Run:

  ```bash
  cd backend && uv run pytest tests/test_service.py -v
  ```

  Expected: all service, ambiguity, time-window, and cache tests pass.

### Task 4: Real Gates, Documentation, and Handoff

**Files:**
- Modify: `ROADMAP.md`
- Modify: `CURRENT.md`
- Modify: `PROJECT.md` only to reflect that P1 core implementation is complete while T16 real-runtime hardening is active
- Modify: `docs/runbooks/p1-local.md` with the timeout setting and real-gate interpretation

- [ ] **Step 1: Run the deterministic backend and frontend gates**

  Run the full commands from the runbook: backend deterministic pytest, frontend unit tests, typecheck, build, and Playwright E2E.

- [ ] **Step 2: Run the real provider, real LLM, and combined gates with persistent `backend/.env`**

  Run `provider_live`, `llm_live`, `end_to_end_live`, then the real browser gates when the configured service is available. Record pass, honest empty, typed error, timeout, or skip exactly as observed; never turn a skip into a pass claim.

- [ ] **Step 3: Update all three control files with evidence**

  Mark T16 `done` only with the actual commit and command outputs. If a real gate remains externally unavailable, leave the exact gate `blocked`/`skip` evidence and do not close P1 hardening.

- [ ] **Step 4: Commit and push only task-owned changes**

  Keep `.codex/`, generated frontend instruction files, and all local `.env` files untracked/ignored. Commit source, tests, plan, runbook, and control-file updates, then push the task commit to `origin/main`.
