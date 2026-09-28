# T112 Polymarket Market Rules Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 Polymarket 官方市场规则字段取得并审计规则；任何缺失、陈旧或变更中的规则都不能产生新的模拟交易。

**Architecture:** Gamma keyset 扫描同时携带每个 market 的 `description` 与 `resolutionSource`，严格映射后才保存内部 ID 对应的规则版本。运行时仅从最近一次完整扫描的规则索引读取行动资格，不在每个决策或结算轮询时额外查 Gamma。展示目录和报价继续独立运行。

**Tech Stack:** Python/FastAPI, Pydantic, SQLAlchemy/Alembic, PostgreSQL, pytest, TypeScript/Vitest.

**Spec:** [P3 market and decision support design](../specs/2026-09-16-tennixai-p3-market-decision-support-design.md) §市场规则与结算；[Polymarket Gamma keyset](https://docs.polymarket.com/api-reference/events/list-events-keyset-pagination)、[market by id](https://docs.polymarket.com/api-reference/markets/get-market-by-id)、[market clarification](https://help.polymarket.com/en/articles/13364548-how-are-markets-clarified)。

## Global Constraints

- 仅单场胜者市场可严格映射；未映射、双打仍可展示但不得进入模型/机会/Paper。
- 规则缺失不能用赛事描述、`resolvedBy`、网球比分或通用模板填造。
- 生产模型仍未晋升；不加入交易凭据、自动下单或额外供应商请求。
- 保留工作区已记录的用户改动；根 `.env` 与真实数据库不重置。

## Review Focus

- Gamma 响应无 `rules` 但有 market `description`/`resolutionSource`：应获得真实规则，且规则不进公开 DTO。
- 相同规则重复扫描与 A→B→A：前者不新增版本，后者新增第三版本并成为当前规则。
- 规则字段缺失、扫描中断或超过新鲜度窗口：旧数据库快照不得授权 BUY/SELL。
- 仅规则来源变化：规则 hash 也必须变化，避免错用原 source。
- 已有 Paper 持仓遇规则变更：保留账本；新的 SELL/intent 被硬门拦住，结算只认供应商 FINAL。

---

### Task 1: Canonical rule snapshot from Gamma

**Files:** `backend/app/markets/polymarket_dtos.py`, `backend/app/markets/polymarket.py`, `backend/app/markets/models.py`, `backend/tests/test_polymarket_provider.py`.

**Interfaces:** `MarketListingScan.rules: tuple[MarketRules, ...]`; `PolymarketProvider.get_rules(market_id) -> MarketRules` shares the same conversion as keyset scan.

- [x] Add real-shaped Gamma tests: market `description` + `resolutionSource`, no `rules`/`resolvedBy`; assert actual text/source, source-only hash change, missing field is unavailable, scan uses only tag+keyset GETs.
- [x] Run focused provider tests and observe RED.
- [x] Parse official fields, derive stable hash from text+source, carry internal-ID-only snapshots in scan; do not use event description fallback.
- [x] Re-run provider tests; confirm complete and interrupted page semantics.
- [x] Review the official [market clarification rules](https://polymarket.com/sports/atp/atp-munar-rinderk-2026-09-02) and Gamma schema. A live API-to-page text comparison was attempted but the Gamma host presented an untrusted TLS certificate in this environment; verification was not weakened, so this specific live comparison remains unverified.

### Task 2: Versioned persistence and safe migration

**Files:** `backend/app/persistence/models.py`, `backend/app/persistence/market_repositories.py`, new `backend/migrations/versions/20260928_0009_market_rule_history.py`, `backend/tests/integration/test_p3_market_persistence.py`.

**Interfaces:** `save_rules(MarketRules) -> int` returns current version; `get_current_rules` returns latest chronological snapshot. Same hash refreshes confirmation time; changed hash appends version even if seen in history.

- [x] Add integration test A→B→A, same-hash repeat and source-only change; observe RED.
- [x] Drop only `(market_id,rules_hash)` uniqueness, retain version uniqueness; allow arbitrary official resolution source length. Downgrade refuses if historical repeated hashes or overlong sources would be lost/truncated.
- [x] Make save compare only to latest version and append on change; same hash only refreshes `fetched_at`.
- [x] Run migration upgrade and integration test on an isolated test database, then verify guarded downgrade behavior. The shared runtime database was not migrated or reset.

### Task 3: Runtime scan and action gates

**Files:** `backend/app/runtime/daemon.py`, `backend/app/runtime/assembly.py`, `backend/app/decision/engine.py`, `backend/app/decision/models.py`, `backend/app/paper/service.py`, `frontend/lib/p3-view-models.ts`, `frontend/lib/p3-workbench-models.ts`, relevant runtime/decision/paper tests.

**Interfaces:** Rule index is empty until a complete successful scan; `get_rules_hash(market_id) -> str | None` returns None for missing, failed or old scan. No decision-loop provider rule GET.

- [x] Add failing tests for one keyset scan serving all mapped rules without per-market GET; partial/failed/old scan revoking action; absent/changed rule yielding NO BET; Paper refusing a BUY/SELL intent without hash.
- [x] Implement one scan-fed bounded-fresh rule index. Reconcile listing first; save available rules only for strict links, then publish index only if scan complete and saves succeeded. Remove resolution-loop rule GET.
- [x] Add explicit `RULES_UNAVAILABLE` gate before action evaluation; preserve `RULE_CHANGED` for frozen versus current mismatch. Remove `"unfrozen"` fallback from Paper.
- [x] Add consumer-facing reason copy; run focused tests and broad deterministic backend/front regression.

### Task 4: Verification and handoff

**Files:** `CURRENT.md`, `ROADMAP.md`; plan notes as needed.

- [x] Check diff scope and credentials; run `git diff --check`, focused and broad tests, and migration proof. Report skipped/blocked gates accurately.
- [x] Verify scan request count with mocked transport; do not turn model on or call order APIs. Direct public Gamma comparison remains unverified due to TLS validation failure described above.
- [x] Commit implementation and test changes with explicit paths (`6b7de72`); update controls with exact commit and actual validation; push `origin/main` while preserving user edits.
