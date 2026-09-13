# P2 Final Completion Gate Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close T53 by making every deterministic Playwright test pass, preserving the approved product contract and visual truth, removing the duplicate WebSocket setting, and synchronizing the three control documents.

**Architecture:** Keep the existing Home filter serialization and page implementation unless visual inspection proves a task-caused regression. Update only stale E2E expectations for the approved explicit all-gender query contract. Treat each prototype screenshot as a reviewed expected/actual/diff triplet; update only baselines proven to represent the approved current design, and record the per-state decision in the controls.

**Tech Stack:** Next.js/TypeScript, Playwright, Vitest, FastAPI/Pydantic, pytest, PostgreSQL, Redis, Docker Compose, Markdown control documents.

**Spec:** `docs/superpowers/plans/2026-09-12-tennixai-player-directory-multilingual-identity-implementation.md#final-p2.6-completion-gate`

## Global Constraints

- Work on `main`; the T53 claim commit `891b4d5` is already pushed to `origin/main`.
- Preserve the pre-existing untracked files: `.codex/`, `REALTIME_LATENCY_INVESTIGATION.md`, `frontend/AGENTS.md`, `frontend/CLAUDE.md`, and `frontend/next-env.d.ts`.
- The approved Home default is ATP+WTA, explicit genders men+women+mixed+unknown, and singles; do not change filter product semantics.
- Do not implement P3, odds, prediction, market, trading, doubles, Player Chat, runtime translation/RAG, or cloud deployment.
- Real provider/LLM gates are quota-sensitive; reuse already-passing T52 real evidence unless a changed path requires the minimum affected real gate.
- Every visual baseline change requires review of expected, actual, and diff for that named state at both viewports.

---

### Task 1: Capture the T53 baseline and repository invariants

**Files:**
- Read: `CURRENT.md`, `ROADMAP.md`, `PROJECT.md`
- Read: `frontend/e2e/p2-home-filters.spec.ts`, `frontend/e2e/prototype.visual.spec.ts`
- Read: `frontend/e2e/__screenshots__/{desktop,mobile}/*.png`
- Read: `frontend/test-results/**/{*-actual.png,*-diff.png,error-context.md}`

**Interfaces:**
- Consumes: T53 claim commit `891b4d5`, healthy `postgres` and `redis`.
- Produces: named failure list, visual review evidence, unchanged untracked-file inventory.

- [x] **Step 1: Verify the claimed starting point**

  Run:

  ```bash
  git fetch origin
  git status --short --branch
  git branch --show-current
  git log -1 --oneline
  git rev-parse origin/main
  ```

  Expected: `main), HEAD `891b4d5), remote contains `891b4d5), and only the five pre-existing untracked groups are present.

- [x] **Step 2: Reproduce the complete browser gate**

  Run from `frontend`:

  ```bash
  pnpm test:e2e
  ```

  Expected baseline: 42 passed, 32 skipped, 14 failed; failures are only `p2-home-filters` and `prototype.visual`.

- [x] **Step 3: Review every prototype triplet**

  For each `home-initial`, `home-answer`, `match-upcoming`, `match-live`, and `match-finished`, review the expected PNG under `frontend/e2e/__screenshots__`, the corresponding actual PNG under `frontend/test-results`, and the corresponding diff PNG at desktop and mobile resolution. Compare against the approved product code/history before deciding whether the current render is a regression or an approved evolution.

---

### Task 2: Repair the Home filter E2E contract at the narrowest layer

**Files:**
- Modify: `frontend/e2e/p2-home-filters.spec.ts:63-69`
- Modify: `frontend/e2e/p2-home-filters.spec.ts:163-170`
- Test: `frontend/e2e/p2-home-filters.spec.ts`

**Interfaces:**
- Consumes: current `serializeMatchFilters` behavior and the approved all-gender contract.
- Produces: assertions that distinguish explicit all-gender serialization from a selected gender filter.

- [x] **Step 1: Confirm the failing contract**

  Run:

  ```bash
  cd frontend
  pnpm exec playwright test e2e/p2-home-filters.spec.ts --project=desktop --grep "defaults to top-tier|恢复默认"
  ```

  Expected: failure shows `gender=men`, `gender=women`, `gender=mixed`, and `gender=unknown`.

- [x] **Step 2: Replace only stale URL assertions**

  In the two URL checks, replace `expect(url).not.toContain('gender=')` and the matching `!last.includes('gender=')` predicate with literal assertions that all four gender values are present:

  ```typescript
  expect(url).toContain('gender=men')
  expect(url).toContain('gender=women')
  expect(url).toContain('gender=mixed')
  expect(url).toContain('gender=unknown')
  ```

  Do not change filter state, request construction, or product code.

- [x] **Step 3: Run the focused browser proof**

  Run:

  ```bash
  pnpm exec playwright test e2e/p2-home-filters.spec.ts
  ```

  Expected: 6 passed across desktop and mobile.

---

### Task 3: Resolve the ten prototype visual failures by evidence

**Files:**
- Possible Modify: `frontend/app/**`, `frontend/components/**`, or the smallest responsible frontend file only if a non-approved regression is proven.
- Possible Modify: `frontend/e2e/__screenshots__/desktop/{home-initial,home-answer,match-upcoming,match-live,match-finished}.png`
- Possible Modify: `frontend/e2e/__screenshots__/mobile/{home-initial,home-answer,match-upcoming,match-live,match-finished}.png`
- Read: relevant history from `git log` and the approved v0/P2 visual evidence.

**Interfaces:**
- Consumes: Task 1 expected/actual/diff review.
- Produces: zero prototype visual failures and a per-state decision record in T53 controls.

- [x] **Step 1: Name a single evidence-backed hypothesis per state**

  For each state, document whether the mismatch is:

  - a current-page regression requiring the smallest production fix, or
  - an approved post-baseline evolution whose old snapshot is stale.

  The Home mismatches must account for the exact 34px/55px height deltas; the Match mismatches must account for the exact 647/648 changed-pixel region. Do not use `--update-snapshots` before this decision.

- [x] **Step 2: If a regression is proven, add or use the narrowest red proof**（不适用：逐张审查确认是已批准演进，未证明生产回归）

  Run the named visual test while the mismatch is present, then add one focused deterministic assertion only when the existing visual gate does not identify the responsible behavior. Run it and confirm the expected failure before editing the owning component.

- [x] **Step 3: Restore only the responsible page behavior**（不适用：没有页面生产代码回归）

  Change the smallest frontend layer that owns the regression. Preserve Home filter semantics, player-directory behavior, P1/P2 data paths, and approved v0 layout. Re-run the affected visual state at desktop and mobile.

- [x] **Step 4: If the current render is approved, update only the ten stale baselines**

  Run:

  ```bash
  cd frontend
  pnpm exec playwright test e2e/prototype.visual.spec.ts --update-snapshots
  pnpm exec playwright test e2e/prototype.visual.spec.ts
  ```

  Review every changed PNG again at its expected/actual/diff triplet and record all ten decisions; never update unrelated snapshots.

---

### Task 4: Remove the duplicate WebSocket setting with configuration regression proof

**Files:**
- Modify: `backend/app/config.py:21-22`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: existing `Settings.api_tennis_ws_url` field.
- Produces: one declaration and unchanged settings behavior.

- [x] **Step 1: Run the existing configuration proof**

  Run from `backend`:

  ```bash
  uv run pytest tests/test_config.py -q
  ```

- [x] **Step 2: Delete only the second duplicate declaration**

  Leave the first `api_tennis_ws_url` field and all other settings unchanged.

- [x] **Step 3: Re-run configuration and import proofs**

  Run:

  ```bash
  uv run pytest tests/test_config.py -q
  uv run python -c "from app.config import Settings; assert Settings(_env_file=None).api_tennis_ws_url == 'wss://wss.api-tennis.com/live'"
  ```

  Expected: all tests pass and the field resolves to the documented default.

---

### Task 5: Update the three control documents after all evidence is fresh

**Files:**
- Modify: `PROJECT.md`
- Modify: `ROADMAP.md`
- Modify: `CURRENT.md`

**Interfaces:**
- Consumes: actual Git commit IDs and actual verification output from Tasks 1–4 and Task 6.
- Produces: a single coherent P2-closed / T53-done handoff with P3 still planned and unauthorized.

- [x] **Step 1: Rewrite CURRENT to the current handoff only**

  Keep the T53 current task, exact start commit `7bbb541`, claim commit `891b4d5`, final product commit, exact validation results, visual per-state decisions, unchanged untracked-file list, and next action. Remove stale Shelton repair text, duplicate historical current-task headers, and obsolete T43/T52 handoff prose. Use only `planned`, `ready`, `in_progress`, `blocked`, `done`, and `deferred`.

- [x] **Step 2: Reconcile ROADMAP**

  Set the update time, mark T53 `done` with its exact final commit, mark P2.6/P2 formally closed, set overall status to `ready` for the next authorized P3 design task, keep P3 `planned`, and replace every `completed` or `+收尾提交` state/commit expression with the repository-defined state and exact commit(s).

- [x] **Step 3: Reconcile PROJECT**

  Update only the product-stage/current-boundary wording needed to say P2 is formally closed and P3 remains `planned`/ready for design only after explicit user authorization. Do not add P3 capability or change the stable P2 contract.

- [x] **Step 4: Run documentation consistency checks**

  Run:

  ```bash
  rg -n "completed|\+收尾提交|修复尚未实施|T53|P3|in_progress|planned|ready|done|deferred" PROJECT.md ROADMAP.md CURRENT.md
  git diff --check
  ```

  Expected: no stale contradiction, no nonstandard task state, and no whitespace errors.

---

### Task 6: Run the complete acceptance matrix and hygiene gates

**Files:**
- Read: `backend/pyproject.toml`, `frontend/package.json`, `frontend/playwright.config.ts`
- Read: all test outputs and snapshot diffs.

**Interfaces:**
- Consumes: all implementation and control changes.
- Produces: fresh, command-backed completion evidence.

- [x] **Step 1: Confirm services**

  Run:

  ```bash
  docker compose up -d postgres redis
  docker compose ps
  ```

  Expected: both containers report `healthy`.

- [x] **Step 2: Run backend deterministic and infrastructure suites**

  Run from `backend`:

  ```bash
  uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure and not player_alias_llm_live and not player_directory_e2e_live" -q
  uv run pytest -m infrastructure -q
  ```

  Expected: zero failed tests in both suites.

- [x] **Step 3: Run frontend gates**

  Run from `frontend`:

  ```bash
  pnpm test
  pnpm typecheck
  pnpm build
  ```

  Expected: each command exits 0.

- [x] **Step 4: Run all deterministic browser gates**

  Run from `frontend`:

  ```bash
  pnpm test:e2e
  ```

  Expected: exit 0 with passed tests plus only pre-declared opt-in skips and zero failures.

- [x] **Step 5: Run focused visual and player-directory gates**

  Run:

  ```bash
  pnpm exec playwright test e2e/player-directory.spec.ts e2e/player-directory.visual.spec.ts
  pnpm exec playwright test e2e/p1.visual.spec.ts e2e/p2.visual.spec.ts e2e/prototype.visual.spec.ts
  ```

  Expected: all deterministic P1/P2/prototype/player-directory visual tests pass.

- [x] **Step 6: Run leakage and repository hygiene checks**

  Run from the repository root:

  ```bash
  git diff --check
  git grep -nE 'player_key|first_player_key|second_player_key|APIkey' -- ':!backend/app/providers/**' ':!backend/tests/**' ':!docs/**'
  git status --short --branch
  git ls-files --others --exclude-standard
  ```

  Review every hit and compare the untracked list byte-for-byte with the Task 1 inventory. No credential value may appear in source, docs, fixtures, logs, or commits.

- [x] **Step 7: Reuse prior real-provider/LLM evidence**

  Because T53 changes only deterministic E2E expectations, visual baselines if proven stale, a duplicate config declaration, and controls, reuse T52’s already-passing real API-Tennis/LLM/directory-browser evidence. If any provider/resolver/Chat runtime path changes, stop and run the minimum affected real gate before finalizing.

---

### Task 7: Commit, push, and prove the final state

**Files:**
- Modify: all task-scoped files from Tasks 2–6.
- Preserve: all pre-existing untracked files.

**Interfaces:**
- Consumes: fresh green acceptance matrix and exact control evidence.
- Produces: local `main` equal to `origin/main), no task-scoped working-tree changes, T53 `done`.

- [x] **Step 1: Commit product/test/config changes**

  Stage only task-scoped tracked files and commit:

  ```bash
  git add frontend/e2e/p2-home-filters.spec.ts backend/app/config.py frontend/e2e/__screenshots__
  git commit -m "fix: close P2 final completion gate"
  ```

  Actual task commit: `348110c`. The control-document synchronization is committed separately after this evidence is recorded.

- [ ] **Step 2: Push the final commit**

  Run:

  ```bash
  git push origin main
  ```

- [ ] **Step 3: Verify exact local/remote agreement**

  Run:

  ```bash
  git fetch origin
  git rev-parse HEAD
  git rev-parse origin/main
  git rev-list --left-right --count main...origin/main
  git status --short --branch
  ```

  Expected: identical commit IDs, `0 0`, and only the unchanged pre-existing untracked files.

- [ ] **Step 4: Complete T53**

  Update `CURRENT.md` with the final commit and actual outputs only, make the final control-only commit if needed, push it, and repeat Step 3. The final handoff must say exactly: P2 formally closed; no `in_progress`; P3 `planned`/ready for design; user authorization still required; P3 not started.
