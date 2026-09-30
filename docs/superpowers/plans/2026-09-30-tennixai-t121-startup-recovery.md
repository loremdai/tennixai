# T121 Startup Recovery Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; main is required by AGENTS.md. User has approved implementation of the T120 solution.

**Goal:** Restore reliable daily startup, isolate bad markets, preserve final settlement and recover without LLM when temporary launcher state is lost.

**Architecture:** Reuse the existing PostgreSQL init record, worker retry/reconciliation, bounded jobs and health registry. Distinguish runtime readiness from upstream data fitness; existing Paper gates remain fail closed.

**Tech Stack:** Python 3.12, asyncio, HTTPX, PostgreSQL, Redis, existing launcher/Next frontend.

**Spec:** [T120 solution](../../research/2026-09-30-tennixai-t120-official-recovery-solution.md).

## Global Constraints

- Work on main; preserve user service.py/untracked files; only root .env is read internally, no credential output.
- No LLM, model promotion, real orders, historical/ledger deletion, new dependency, or schema migration.
- Readiness requires current-process DB/schema/Redis checks; degraded sources stay visible and new actions stay blocked.
- Settlement remains supplier-final, including disputed/pending and 50/50; closed market bookkeeping survives quote retirement.

## Review Focus

- Gamma filters return an unrelated/duplicate row: reject rather than use someone else's market.
- One failed or closed subscription consumes capacity or overwrites another failure's health: maintain accurate aggregates.
- Temporary state disappears but DB is old/uninitialized or an owner is still alive: refuse unsafe startup.
- Persisted health belongs to yesterday's process: cannot satisfy new-process readiness.
- Cancellation while provider recovery is blocked: propagate cancellation and clean up streams.

### Task 1: Known-market query and settlement

**Files:** app/markets/polymarket.py; tests/test_polymarket_provider.py (backend).
**Interfaces:** `_gamma_market_by_condition(condition_id) -> GammaMarketDto` queries explicit closed=false then closed=true for valid empty results; `get_order_book` rejects nontradable status before CLOB. Existing rules/resolution signatures stay unchanged.

- [x] Write regressions: closed final/50-50/pending, no closed CLOB fetch, malformed/unrelated/duplicate row rejection, both-empty not_found.
- [x] Run new provider tests: Expected FAIL on missing closed fallback/status validation.
- [x] Implement minimal lookup and status guard; run provider suite: Expected PASS.
- [x] Commit this task with its tests.

### Task 2: Demand and isolated market recovery

**Files:** app/decision/worker.py, app/persistence/market_repositories.py, app/runtime/demand.py, app/runtime/assembly.py, app/main.py, app/markets/worker.py; tests/test_p3_tracking_demand.py, test_market_worker.py, test_runtime_demand.py.
**Interfaces:** TrackingDemand optional `eligible_markets() -> set[str]`; repository supplies open market IDs without modifying links; match tracking context carries stale state. MarketWorker exposes aggregateable `reconciliation_failures` stable codes, bounded timeout and 5..60s retry; terminal closed markets trigger existing resolution hint and stop quotes.

- [x] Write regressions: cancelled/finished/postponed in window, stale live, closed position excluded from quotes but ledger intact, failure/capacity isolation, retry delay/recovery, reconciliation failure, closure, cancellation.
- [x] Run new regressions: Expected FAIL on incorrect demand and first failure aborting worker.
- [x] Implement minimal filters and per-market guards; run the three suites: Expected PASS.
- [x] Commit this task with its tests.

### Task 3: Independent maintenance and readiness

**Files:** app/runtime/daemon.py, app/runtime/assembly.py, app/runtime/health.py, app/runtime/launcher.py; tests/test_runtime_daemon.py, test_runtime_health.py, test_runtime_launcher.py.
**Interfaces:** daemon readiness probe checks Redis after durable cursor recovery; `runtime_ready` is persisted before external subscription recovery. Tick executes bounded jobs despite reconciliation failure; aggregate subscription failures keep Polymarket GAP. Startup requires runtime_ready success from this startup; upstream failures can remain degraded.

- [x] Write regressions: failed reconciler still allows sync/settlement/persist, partial recovery never becomes healthy, degraded data blocks new actions, failed local readiness refuses, stale health and dead child refuse, legitimate zero demand starts.
- [x] Run regressions: Expected FAIL on maintenance starvation/old startup predicate.
- [x] Implement and run affected daemon/health/launcher suites: Expected PASS.
- [x] Commit this task with its tests.

### Task 4: Durable initialization and full startup proof

**Files:** app/runtime/launcher.py, app/persistence/repositories.py; tests/test_runtime_launcher.py, tests/integration/test_runtime_catalog_postgres.py; PROJECT.md, CURRENT.md, ROADMAP.md, docs/runbooks/local-real-runtime.md.
**Interfaces:** load validated RuntimeInitRecord from PostgreSQL; compare record revision, actual Alembic head and repository head. Local initialized/schema fields are recoverable cache only, ownership tokens remain guarded.

- [x] Write regressions: missing temp state with valid DB starts with zero bootstrap/migration/enrichment; incompatible DB/record refuses before spawn; down/up retains ownership/data.
- [x] Run regressions: Expected FAIL on local marker requirement.
- [x] Implement and run launcher/repository proof: Expected PASS.
- [x] Run backend full suite (live opt-ins remain disabled), affected isolated DB/Redis integration, lint/diff; report every failure honestly.
- [x] Execute supported up/status, HTTP API/home and down/up persistence proof; keep the project running, preserve other project containers.
- [x] Review the final change, commit fixes and evidence, update controllers/runbook and push main.

## Evidence

Implementation commits: `ac97af6`, `63c671e`, `26eba0e`, `e13c0ec`, `57325c4`. Provider gate: 38 passed; demand/worker gate: 42 passed; daemon/health/launcher/worker gate: 171 passed; final affected gate: 246 passed. All five Important review findings received RED→GREEN proof in one fix pass; no deferred Minor findings.

Full tests, real restart/data preservation, browser acceptance, corrected failed invocations and rulings are recorded in [T121 validation](../../research/2026-09-30-tennixai-t121-startup-recovery-validation.md). The nonexistent catalog test filename above was corrected to the existing isolated PostgreSQL suite; production schema was not migrated.
