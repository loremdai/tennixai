# TennixAI P3 Market & Decision Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不接真实交易的前提下，交付赛前/赛中网球单场胜者市场、独立校准概率、可执行 edge、一次入场/一次退出的 `$10` paper ledger，以及 Home、`/markets`、Match 三层结构化 UI。

**Architecture:** API-Tennis 与 Polymarket 分别进入 canonical sports/market reducers；独立 PredictionService 不读取当前市场价格，DecisionService 只在两侧状态均新鲜时比较保守概率与逐档可执行 quote。高频 book 保存在内存/Redis，decision evidence 与 paper ledger 持久化到 PostgreSQL；浏览器只通过 Next.js Route Handler 消费 REST 与独立版本化 SSE。

**Tech Stack:** Python 3.12、FastAPI、Pydantic 2、httpx、websockets、NumPy、scikit-learn、SQLAlchemy async、Alembic、PostgreSQL 16、Redis 7、Next.js 16、React 19、TypeScript、Tailwind CSS、shadcn/ui、Recharts、Vitest、Playwright。

**Spec:** [P3 Market & Decision Support 设计规格](../specs/2026-09-16-tennixai-p3-market-decision-support-design.md)

## Global Constraints

- 每个任务开始前完整阅读根目录 `PROJECT.md`、`ROADMAP.md`、`CURRENT.md`，运行启动入口规定的 Git 检查；先领取唯一当前任务并把领取提交推送到 `origin/main`。
- 根目录 `.env` 是唯一人工配置入口；不得创建或使用 `backend/.env`、`frontend/.env`、`frontend/.env.local`。
- 保留 `CURRENT.md` 记录的未跟踪文件；不得删除、修改或顺手提交任务外改动。
- P3 只读 Polymarket public Gamma/CLOB/WebSocket；不得加入 wallet、private key、L1/L2 trading auth、签名或订单 POST/DELETE。
- provider event/condition/token IDs 只能存在于 adapter/identity persistence；公共 DTO、URL、Chat、前端、截图和日志只使用 internal IDs。
- independent model 不得读取当前或未来 market price/order book/resolution；LLM 不得计算 probability/edge/action/fill/settlement。
- 每个 `match_id` 最多一条 entry intent 和一条 exit intent；FOK 全成或不成，不创建 partial position、partial exit、retry、加仓、换边或重新入场。
- production `BUY/SELL` 只有在 versioned model card、policy artifact、freshness、rules、mapping、liquidity 全部门通过时可出现；证据不足时 `NO BET` 是正确结果。
- raw provider event 14 天；canonical identities、rules evidence、prediction/decision observations 与 paper ledger 长期保留。
- v0 输出是 P3 页面视觉真源。真实接线任务不得自行重设计；每个视觉基线必须逐张审阅，不能批量接受未知 diff。
- 桌面视觉视口 `1440×1000`，移动端 `390×844`；状态不可只靠颜色，图表有文本摘要，触控目标至少 44px。
- 每项实现先写失败测试、确认预期失败，再写最小实现。完成后运行任务门、更新三份总控、提交并推送；未运行的测试不得声称通过。

## Planned File Structure

### Backend market and realtime

- `backend/app/markets/models.py`：canonical market、rules、book、quote 与 resolution。
- `backend/app/markets/providers.py`：窄 `MarketDataProvider` protocol。
- `backend/app/markets/polymarket_dtos.py`：permissive Gamma/CLOB/WebSocket DTO。
- `backend/app/markets/polymarket.py`：公开只读 REST adapter。
- `backend/app/markets/mapping.py`：PlayerResolver + 无序内部 Player ID 对精确组合。
- `backend/app/markets/live.py`：public market WebSocket feed。
- `backend/app/markets/reducer.py`：book snapshot/delta/hash reducer。
- `backend/app/markets/publisher.py`：Redis hot state 与 pub/sub。
- `backend/app/markets/worker.py`：有界 subscription、reconnect、REST reconcile、raw cleanup。
- `backend/app/markets/replay.py`：确定性 market fixture feed。

### Backend prediction, decision and paper

- `backend/app/prediction/models.py`：model availability、prediction、evidence、version metadata。
- `backend/app/prediction/data.py`：可替换历史数据 source 与防泄漏 row schema。
- `backend/app/prediction/audit.py`：许可/覆盖/缺失/乱序审计。
- `backend/app/prediction/prematch.py`：Elo、dynamic rating、HGBM candidates。
- `backend/app/prediction/scoring.py`：确定性网球计分概率引擎。
- `backend/app/prediction/live.py`：prior + beta-binomial shrinkage + hybrid features。
- `backend/app/prediction/calibration.py`：Platt、isotonic、beta candidates。
- `backend/app/prediction/benchmark.py`：walk-forward、bootstrap、model card 与 artifact manifest。
- `backend/app/prediction/service.py`：只读 model artifact 的 runtime prediction facade。
- `backend/app/prediction/cli.py`：`audit`、`benchmark`、`verify-artifact`。
- `backend/app/decision/models.py`：gates、actions、observations、policy version。
- `backend/app/decision/quotes.py`：逐档 `$10` entry/全仓 exit quote 与动态 fee。
- `backend/app/decision/policy.py`：只读 versioned policy artifact。
- `backend/app/decision/engine.py`：`MARKET_ONLY/NO BET/WAIT/BUY/HOLD/SELL`。
- `backend/app/decision/worker.py`：sports/market updates → prediction/decision/paper orchestration。
- `backend/app/paper/models.py`：intent、fill、position、track、settlement。
- `backend/app/paper/state_machine.py`：one-shot FOK entry/exit transitions。
- `backend/app/paper/settlement.py`：provider-final resolution 与 50–50 payout。
- `backend/app/paper/service.py`：transactional ledger orchestration/recovery。

### Backend persistence and API

- `backend/migrations/versions/20260916_0004_p3_market_ledger.py`：可逆 P3 schema。
- `backend/app/persistence/models.py`：P3 rows。
- `backend/app/persistence/market_repositories.py`：market/rules/link/observation repositories。
- `backend/app/persistence/paper_repositories.py`：intent/fill/position/track/resolution transaction repository。
- `backend/app/api/schemas.py`、`backend/app/api/routes.py`：P3 public DTO、REST 与 SSE。
- `backend/app/chat/tools.py`、`backend/app/chat/capabilities.py`、`backend/app/chat/orchestrator.py`：两个只读 P3 business tools。
- `backend/app/config.py`、`backend/app/main.py`：settings、clients、workers 与 lifecycle 装配。

### Frontend

- `frontend/app/markets/page.tsx`：`/markets` route 与 preview entry。
- `frontend/app/api/markets/**`、`frontend/app/api/paper/positions/route.ts`、`frontend/app/api/matches/[matchId]/decision/**`：薄代理。
- `frontend/lib/api/types.ts`、`frontend/lib/api/client.ts`：P3 DTO/REST/SSE discriminated unions。
- `frontend/hooks/use-market-stream.ts`、`frontend/hooks/use-decision-stream.ts`：snapshot-first、gap resync、reconnect。
- `frontend/components/markets/**`：tabs、filters、opportunity/all/ledger rows 与状态。
- `frontend/components/home/home-intelligence.tsx`：≤3 行 Market Pulse。
- `frontend/components/match/decision-summary.tsx`、`probability-market-chart.tsx`、`decision-evidence.tsx`、`paper-lifecycle.tsx`：P3 Match modules。
- `frontend/components/match-page.tsx`、`match-main.tsx`、`match-sidebar.tsx`：批准的 desktop/mobile order。
- `frontend/components/p3-preview-data.ts`：确定性 preview state matrix，生产组件不内置样例。
- `frontend/e2e/p3-markets.spec.ts`、`p3-match.spec.ts`、`p3.visual.spec.ts`：功能、状态和 26 张视觉基线。

---

### T56: Generate, Import, and Freeze the P3 v0 Prototype

**Outcome:** 用户确认的 Home Pulse、`/markets` 和 Match P3 状态原型成为仓库内 preview visual truth；不接真实 P3 API。

**Input gate:** 使用 [P3 v0 Prompt](../../v0/2026-09-16-p3-market-decision-pages-prompt.md) 在 v0 生成并由用户确认、推送输出。若仓库没有该确认输出，T56 保持 `ready` 并在 `CURRENT.md` 记录外部输入；ADE 不得自行设计替代稿。

**Files:**

- Create/modify only the v0-exported frontend components listed in the approved diff.
- Create: `frontend/components/p3-preview-data.ts`
- Create: `frontend/e2e/p3.visual.spec.ts`
- Create: reviewed P3 screenshots under `frontend/e2e/__screenshots__/{desktop,mobile}/`
- Modify: `frontend/components/match/match-header.tsx`
- Modify: `frontend/components/home/home-hero.tsx`

**Interfaces:** preview states are explicit props/query params and never call backend.

```ts
export type DecisionPreviewState =
  | 'market_only' | 'no_bet' | 'wait' | 'buy' | 'entry_pending'
  | 'missed' | 'hold' | 'sell' | 'exit_pending' | 'exited'
  | 'exit_missed' | 'settled' | 'stale' | 'gap'
```

- [ ] **Step 1: Record the exact approved v0 export commit in `CURRENT.md` and claim T56.**
- [ ] **Step 2: Normalize imports to existing shadcn/Lucide/token components without changing accepted geometry or copy.** Do not overwrite package manifests or existing primitives.
- [ ] **Step 3: Add deterministic preview routing and component tests.** Assert every state in `DecisionPreviewState`, three `/markets` tabs, Home ≤3 rows, no wallet/trade buttons, internal links only, and mobile DOM order.
- [ ] **Step 4: Run tests and confirm missing preview behavior fails before completing it.**

```bash
cd frontend
pnpm test -- components/home-page.test.tsx components/match-page.test.tsx components/markets
```

- [ ] **Step 5: Complete preview-only state behavior and create the 26 approved baselines.**

```bash
cd frontend
pnpm test:e2e:update --grep "P3 visual"
pnpm test:e2e --grep "P3 visual"
```

- [ ] **Step 6: Inspect every expected/actual/diff image for overflow, arithmetic contradictions, state ambiguity, stale action leakage and mobile ordering.** Record the reviewed filenames in `CURRENT.md`.
- [ ] **Step 7: Run existing frontend and visual regressions.**

```bash
cd frontend
pnpm test
pnpm typecheck
pnpm build
pnpm test:e2e --grep "prototype|visual"
```

- [ ] **Step 8: Commit only approved prototype assets and controls.** Suggested commit: `feat: freeze P3 market decision prototype`.

---

### T57: Add Canonical P3 Domain, Protocols, and Safe Configuration

**Outcome:** P3 types and provider/service boundaries exist without network, SQL, model training or UI behavior.

**Files:**

- Create: `backend/app/markets/{__init__,models,providers}.py`
- Create: `backend/app/prediction/{__init__,models}.py`
- Create: `backend/app/decision/{__init__,models}.py`
- Create: `backend/app/paper/{__init__,models}.py`
- Modify: `backend/app/config.py`
- Modify: `.env.example`
- Test: `backend/tests/test_p3_domain.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**

```python
class MarketDataProvider(Protocol):
    async def list_tennis_moneylines(self) -> tuple[Market, ...]: ...
    async def get_market(self, market_id: str) -> Market: ...
    async def get_order_book(self, market_id: str) -> OrderBookState: ...
    def subscribe_order_books(self, market_ids: tuple[str, ...]) -> AsyncIterator[MarketEnvelope]: ...
    async def get_resolution(self, market_id: str) -> MarketResolution | None: ...

class DecisionAction(StrEnum):
    MARKET_ONLY = "market_only"
    NO_BET = "no_bet"
    WAIT = "wait"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
```

- [ ] **Step 1: Write failing invariant tests.** Reject naive datetimes, negative sizes, unsorted/duplicate book levels, probabilities outside `[0,1]`, non-complementary model probabilities, external IDs in public models, and illegal lifecycle transitions encoded as models.

```python
def test_decision_observation_requires_versioned_inputs():
    with pytest.raises(ValidationError):
        DecisionObservation(match_id="mat_a", market_id="mkt_a", action=DecisionAction.BUY)
```

- [ ] **Step 2: Run the focused suite and verify import/model failures.**

```bash
cd backend
uv run pytest tests/test_p3_domain.py tests/test_config.py -v
```

- [ ] **Step 3: Implement frozen Pydantic models/protocols and only these settings:** public Gamma/CLOB/WS base URLs, `p3_mode=disabled|shadow|paper`, fixed stake `$10`, model artifact directory, bounded market subscriptions and freshness limits. No secret or trading credential setting is allowed.
- [ ] **Step 4: Add config tests proving defaults, numeric bounds, root `.env` loading and absence of wallet/private-key fields.**
- [ ] **Step 5: Run focused and deterministic regression suites.**

```bash
cd backend
uv run pytest tests/test_p3_domain.py tests/test_config.py tests/test_p2_domain.py tests/test_domain.py -v
```

- [ ] **Step 6: Update controls and commit.** Suggested commit: `feat: define P3 canonical contracts`.

---

### T58: Add Reversible P3 Persistence and Idempotent Ledger Repositories

**Outcome:** PostgreSQL can durably store market identity/rules/linking, decision evidence and one-shot paper lifecycle with recovery-safe uniqueness.

**Files:**

- Create: `backend/migrations/versions/20260916_0004_p3_market_ledger.py`
- Modify: `backend/app/persistence/models.py`
- Create: `backend/app/persistence/market_repositories.py`
- Create: `backend/app/persistence/paper_repositories.py`
- Test: `backend/tests/test_p3_persistence_models.py`
- Test: `backend/tests/integration/test_p3_market_persistence.py`
- Test: `backend/tests/integration/test_p3_paper_ledger.py`

**Schema contract:** create `markets`, `market_external_ids`, `market_rules`, `market_match_links`, `market_observations`, `prediction_snapshots`, `decision_observations`, `paper_order_intents`, `paper_fills`, `paper_positions`, `paper_track_results`, `market_resolutions`. Enforce one provider mapping, one current exact link per market, one entry and one exit intent per match, one main position per match, and unique transition idempotency keys.

- [ ] **Step 1: Write schema tests that inspect names, FKs, JSONB evidence, timestamptz columns and exact unique constraints.**
- [ ] **Step 2: Write integration tests first.** Prove 20 concurrent creators converge, repeated intent/fill/settlement is idempotent, failed transition rolls back fully, restart reloads pending/open state, and raw cleanup never deletes canonical rules/ledger.

```python
assert await repo.create_intent(entry) == await repo.create_intent(entry)
with pytest.raises(UniqueViolationError):
    await repo.create_intent(entry.model_copy(update={"idempotency_key": "other"}))
```

- [ ] **Step 3: Run tests against migration `0003` and verify expected missing-table failures.**

```bash
cd backend
uv run alembic downgrade 0003
uv run pytest -m infrastructure tests/integration/test_p3_market_persistence.py tests/integration/test_p3_paper_ledger.py -v
```

- [ ] **Step 4: Implement migration, ORM rows and narrow repositories.** Store provider IDs only in private external mapping rows; store rules used by an intent as immutable canonical evidence.
- [ ] **Step 5: Prove reversible migration and repository behavior.**

```bash
cd backend
uv run alembic upgrade head
uv run pytest tests/test_p3_persistence_models.py -v
uv run pytest -m infrastructure tests/integration/test_p3_market_persistence.py tests/integration/test_p3_paper_ledger.py -v
uv run alembic downgrade 0003
uv run alembic upgrade head
uv run pytest -m infrastructure tests/integration/test_p3_paper_ledger.py -v
```

- [ ] **Step 6: Update controls and commit.** Suggested commit: `feat: persist P3 market and paper ledger`.

---

### T59: Implement the Read-Only Polymarket Adapter and Exact Match Mapping

**Outcome:** public Gamma/CLOB REST becomes canonical moneyline/rules/book metadata and uniquely links to internal matches without fuzzy final decisions.

**Files:**

- Create: `backend/app/markets/polymarket_dtos.py`
- Create: `backend/app/markets/polymarket.py`
- Create: `backend/app/markets/mapping.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/fixtures/polymarket/*.json`
- Test: `backend/tests/test_polymarket_provider.py`
- Test: `backend/tests/test_market_match_mapping.py`
- Create: `backend/tests/live/test_polymarket_live.py`
- Modify: `backend/pyproject.toml` marker list

**Interfaces:** adapter calls public `/events`/`/markets`, `/clob-markets/{condition_id}`, `/book`, `/fee-rate/{token_id}` and resolution metadata; it never imports a trading SDK.

- [ ] **Step 1: Save minimal redacted fixtures for active tennis moneyline, two independent outcome books, dynamic fee details, changed rules, 50–50 resolution and malformed/closed markets.** Fixtures must use fake IDs and names.
- [ ] **Step 2: Write `httpx.MockTransport` tests.** Assert tennis moneyline filtering, complete player outcomes, independent books, dynamic tick/min-size/fee/delay, rule hash, terminal resolution, 429 retry metadata and zero URL/key/provider-ID leakage from errors.
- [ ] **Step 3: Write mapping tests.** Cover reversed player order, bilingual aliases, 45-minute schedule tolerance, duplicate candidates, unresolved player, mismatched pair, intent-frozen link and condition replacement before/after intent.

```python
assert map_market(market, matches, resolver).match_id == "mat_internal"
assert map_market(ambiguous_market, matches, resolver).status == MappingStatus.AMBIGUOUS
```

- [ ] **Step 4: Run tests and confirm missing adapter/mapping failures.**

```bash
cd backend
uv run pytest tests/test_polymarket_provider.py tests/test_market_match_mapping.py -v
```

- [ ] **Step 5: Implement permissive vendor DTOs, canonical adapter and strict internal-ID mapping.** Parsing failure skips only the malformed market and records a typed quality reason; it never guesses.
- [ ] **Step 6: Add opt-in public live smoke.** It must discover tennis moneylines when present, load both books/market info/rules, and print only aggregate counts/internal IDs. No current tennis market is an honest skip, not a fake pass.

```bash
cd backend
TENNIX_RUN_POLYMARKET_LIVE=1 uv run pytest -m polymarket_live tests/live/test_polymarket_live.py -v
```

- [ ] **Step 7: Run deterministic regressions, update controls and commit.** Suggested commit: `feat: add read-only Polymarket provider`.

---

### T60: Build the Market WebSocket Reducer, Hot State, and Replay Feed

**Outcome:** full books and deltas update canonical hot state without SQL on every tick; gap/reconnect/rule/resolution events are explicit and replayable.

**Files:**

- Create: `backend/app/markets/{live,reducer,publisher,worker,replay}.py`
- Modify: `backend/app/persistence/market_repositories.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/fixtures/replay/p3_market.jsonl`
- Test: `backend/tests/test_market_live_feed.py`
- Test: `backend/tests/test_market_reducer.py`
- Test: `backend/tests/test_market_worker.py`
- Test: `backend/tests/integration/test_market_recovery.py`
- Create: `backend/tests/live/test_polymarket_websocket_live.py`

**Reducer contract:** one writer per token/book; full `book` replaces state, `price_change` mutates exact levels, zero size deletes, timestamp/hash regressions are rejected, tick changes update metadata, reconnect always REST-reconciles before accepting deltas.

- [ ] **Step 1: Write reducer tests for full book, delta insert/update/delete, reversed delivery, duplicate hash, missing base snapshot, reconnect reset, tick change and resolution.**
- [ ] **Step 2: Write worker tests with fake clock/feed.** Assert bounded per-market queues, dynamic subscribe/unsubscribe, no I/O in receive callback, REST reconcile after disconnect, Redis loss recovery, observation batching and 14-day raw cleanup.
- [ ] **Step 3: Run focused tests and verify failures.**

```bash
cd backend
uv run pytest tests/test_market_live_feed.py tests/test_market_reducer.py tests/test_market_worker.py -v
```

- [ ] **Step 4: Implement public WS feed, canonical reducer, Redis publisher and worker.** Send ping every official interval; never subscribe the user/authenticated channel.
- [ ] **Step 5: Add replay and infrastructure recovery tests.** Prove process restart loads durable tracking/position demand, REST-rebuilds books and marks the offline interval as `tracking_gap` without backfilling signals.

```bash
cd backend
uv run pytest -m infrastructure tests/integration/test_market_recovery.py -v
```

- [ ] **Step 6: Run opt-in live WS smoke and deterministic suite.**

```bash
cd backend
TENNIX_RUN_POLYMARKET_LIVE=1 uv run pytest -m polymarket_live tests/live/test_polymarket_websocket_live.py -v
uv run pytest -m "not llm_live and not provider_live and not api_tennis_live and not realtime_live and not polymarket_live and not end_to_end_live and not player_alias_llm_live and not player_directory_e2e_live" -v
```

- [ ] **Step 7: Update controls and commit.** Suggested commit: `feat: add P3 market realtime pipeline`.

---

### T61: Add the Audited Walk-Forward Pre-Match Benchmark Pipeline

**Outcome:** a legally identified local historical source can produce reproducible data audits, Elo/dynamic/HGBM comparisons, calibration reports and a versioned model card without using market data.

**Files:**

- Modify: `backend/pyproject.toml` (`numpy`, `scikit-learn`; do not add pandas/polars unless benchmark evidence requires it in a later task)
- Create: `backend/app/prediction/{data,audit,prematch,calibration,benchmark,cli}.py`
- Create: `backend/tests/fixtures/prediction/historical_matches.csv`
- Test: `backend/tests/test_prediction_data.py`
- Test: `backend/tests/test_prediction_audit.py`
- Test: `backend/tests/test_prematch_models.py`
- Test: `backend/tests/test_prediction_calibration.py`
- Test: `backend/tests/test_prediction_benchmark.py`

**Artifact contract:** `manifest.json`, `model-card.json`, serialized model/calibrator, feature schema and SHA-256 hashes. Model card contains source/license identifier, chronological windows, metrics/subgroups, calibration, code commit and promotion result; it contains no raw rows.

- [ ] **Step 1: Write fixture and leakage tests.** Reject future-dated features, random/match-split leakage, duplicate match across splits, missing source/license and any column matching market/odds/price/book/resolution.
- [ ] **Step 2: Write deterministic candidate tests.** Verify surface Elo updates only after a match, inactive uncertainty grows for dynamic rating, HGBM feature vector uses only prior rows, and fixed seed produces identical artifact hashes.
- [ ] **Step 3: Write walk-forward/calibration tests.** Test Platt/isotonic/beta selection on validation, untouched test isolation, match-level bootstrap and simpler-model tie-break.
- [ ] **Step 4: Run tests before implementation.**

```bash
cd backend
uv sync
uv run pytest tests/test_prediction_data.py tests/test_prediction_audit.py tests/test_prematch_models.py tests/test_prediction_calibration.py tests/test_prediction_benchmark.py -v
```

- [ ] **Step 5: Implement CLI and exact commands.**

```bash
cd backend
uv run python -m app.prediction.cli audit --data "$TENNIX_MODEL_DATA_PATH" --output artifacts/p3/audit.json
uv run python -m app.prediction.cli benchmark --data "$TENNIX_MODEL_DATA_PATH" --output artifacts/p3
uv run python -m app.prediction.cli verify-artifact --artifact-dir artifacts/p3
```

The CLI must fail closed if `TENNIX_MODEL_DATA_PATH`, source/license metadata or audit gate is absent. It must select on validation and report test only after selection.

- [ ] **Step 6: Run the fixture benchmark, inspect the report, update controls and commit code + tiny fixture.** Do not commit a restricted full dataset. Suggested commit: `feat: add audited P3 model benchmark`.

---

### T62: Implement Live Tennis Probability, Calibration Loading, and Safe Degradation

**Outcome:** canonical MatchSnapshot can produce replayable pre-match/live probabilities or typed abstention, with no LLM or market input.

**Files:**

- Create: `backend/app/prediction/{scoring,live,service}.py`
- Modify: `backend/app/prediction/models.py`
- Test: `backend/tests/test_scoring_probability.py`
- Test: `backend/tests/test_live_prediction.py`
- Test: `backend/tests/test_prediction_service.py`

**Interfaces:**

```python
class PredictionService:
    def predict(self, snapshot: MatchSnapshot) -> PredictionSnapshot: ...

class ScoringProbabilityEngine:
    def match_win_probability(self, state: TennisScoringState, serve: ServePointPrior) -> float: ...
```

- [ ] **Step 1: Write exact scoring tests.** Cover love-all symmetry, server advantage, break point, set/match point, best-of-3, best-of-5, standard tiebreak, deciding-set tiebreak, terminal winner and unknown format abstention.
- [ ] **Step 2: Write shrinkage tests.** Small live samples stay near prior; larger samples move monotonically; only service points before the prediction state are counted; PBP correction deterministically recomputes from the affected sequence.
- [ ] **Step 3: Write service tests.** Assert main-tour singles coverage, Challenger/ITF `MODEL_UNAVAILABLE`, missing server/score degradation, score-only fallback, artifact/hash mismatch fail-closed, version/provenance output and zero imports from `app.markets`.
- [ ] **Step 4: Run tests and verify failures.**

```bash
cd backend
uv run pytest tests/test_scoring_probability.py tests/test_live_prediction.py tests/test_prediction_service.py -v
```

- [ ] **Step 5: Implement dynamic-programming scoring, empirical-Bayes update, calibrated service and structured evidence.** Never infer unknown format; return a stable reason code.
- [ ] **Step 6: Run focused tests plus P2 reducer/momentum regressions.**

```bash
cd backend
uv run pytest tests/test_scoring_probability.py tests/test_live_prediction.py tests/test_prediction_service.py tests/test_live_reducer.py tests/test_momentum_engine.py -v
```

- [ ] **Step 7: Update controls and commit.** Suggested commit: `feat: add calibrated live win probability`.

---

### T63: Implement Executable Quotes and the Versioned Decision Engine

**Outcome:** two independent books plus a valid prediction produce auditable `$10` entry/exit quotes, gates, dynamic max price and one structured action.

**Files:**

- Create: `backend/app/decision/{quotes,policy,engine}.py`
- Modify: `backend/app/decision/models.py`
- Create: `backend/tests/fixtures/decision/policy-v1.json`
- Test: `backend/tests/test_executable_quotes.py`
- Test: `backend/tests/test_decision_policy.py`
- Test: `backend/tests/test_decision_engine.py`

**Quote contract:** consume asks for entry and bids for exit; walk levels in price priority, include dynamic fee curve/taker-only semantics, reject below minimum order or insufficient full depth, and retain book hash/timestamp.

- [ ] **Step 1: Write quote tests.** Cover one/multiple levels, price improvement, dynamic fees, insufficient depth, stale book, non-complementary outcome asks, minimum size and exact decimal rounding.

```python
assert quote.stake == Decimal("10.00")
assert quote.average_price == Decimal("0.525")
assert quote.book_hash == "book_v7"
```

- [ ] **Step 2: Write decision table tests for every hard gate and action.** Include `MODEL_UNPROMOTED`, `OUT_OF_DOMAIN`, `DATA_INCOMPLETE`, `MODEL_DISAGREEMENT`, `MARKET_UNMAPPED`, `RULE_CHANGED`, `STALE`, `INSUFFICIENT_LIQUIDITY`, `NO_NET_EDGE`, `WAIT`, `BUY`, `HOLD`, `SELL` and separate `LOCK_PROFIT` option.
- [ ] **Step 3: Write policy artifact tests.** Hash mismatch, test-set-selected threshold, missing validation/shadow evidence or non-positive conservative net-EV lower bound must disable BUY/SELL.
- [ ] **Step 4: Run tests and verify failures.**

```bash
cd backend
uv run pytest tests/test_executable_quotes.py tests/test_decision_policy.py tests/test_decision_engine.py -v
```

- [ ] **Step 5: Implement quote/policy/engine.** Compute max acceptable average price by solving the same fee/depth-aware conservative net-edge inequality; do not use a fixed discount.
- [ ] **Step 6: Run focused and domain regressions, update controls and commit.** Suggested commit: `feat: add executable P3 decision engine`.

---

### T64: Implement the One-Shot FOK Paper Lifecycle and Provider-Final Settlement

**Outcome:** the first eligible BUY and first EV SELL become the only entry/exit attempts for a match, with transactionally durable fill/no-fill, position, counterfactual and settlement state.

**Files:**

- Create: `backend/app/paper/{state_machine,settlement,service}.py`
- Modify: `backend/app/paper/models.py`
- Modify: `backend/app/persistence/paper_repositories.py`
- Test: `backend/tests/test_paper_state_machine.py`
- Test: `backend/tests/test_paper_settlement.py`
- Test: `backend/tests/test_paper_service.py`
- Test: `backend/tests/integration/test_p3_paper_recovery.py`

**State contract:** `BUY → ENTRY_PENDING → FILLED|MISSED`; `FILLED → HOLD|SELL`; `SELL → EXIT_PENDING → EXITED|EXIT_MISSED`; open/exited tracks end in `SETTLED`. `STALE/GAP` is an overlay, not a ledger transition. Every transition includes frozen prediction, decision, rules, fee, delay and book evidence.

- [ ] **Step 1: Write a complete transition-table test.** Reject duplicate entry, duplicate exit, retry after `MISSED/EXIT_MISSED`, partial fill, side switching, add-on entry, out-of-order transition and mutation of frozen evidence.
- [ ] **Step 2: Write FOK execution tests with a fake clock.** Requote only after the market's actual sports delay; require the full `$10` entry or full-position exit within the frozen policy limit; `BOOK_UNVERIFIABLE` becomes no-fill and never a synthetic fill.
- [ ] **Step 3: Write settlement tests.** Assert provider-final win/loss, explicit 50–50 payout at `$0.50` per share, pending/disputed state, retirement/default resolution, pre-start walkover/cancellation, delayed event and condition replacement. Tennis result alone must never settle a paper position.
- [ ] **Step 4: Run tests and verify the expected failures.**

```bash
cd backend
uv run pytest tests/test_paper_state_machine.py tests/test_paper_settlement.py tests/test_paper_service.py -v
```

- [ ] **Step 5: Implement the pure state machine, settlement interpreter and transactional service.** Persist `HODL_BASELINE`, `EV_EXIT` and `CONVERGENCE_LOCK` from one entry without creating extra positions; commit PostgreSQL before publishing any externally visible transition.
- [ ] **Step 6: Prove concurrency and restart recovery.** Start two workers on the same BUY/SELL observation, interrupt after commit-before-publish, restart with pending/open ledger rows and assert exactly one intent/fill/position/settlement.

```bash
cd backend
uv run pytest -m infrastructure tests/integration/test_p3_paper_ledger.py tests/integration/test_p3_paper_recovery.py -v
```

- [ ] **Step 7: Update controls and commit.** Suggested commit: `feat: add one-shot P3 paper lifecycle`.

---

### T65: Orchestrate Dual Live Inputs, Durable Tracking, and Pipeline Metrics

**Outcome:** sports and market events drive prediction, quotes, decisions and paper state in the correct order, independently of open browsers, with bounded work and measurable local latency.

**Files:**

- Create: `backend/app/decision/worker.py`
- Create: `backend/app/realtime/p3_metrics.py`
- Modify: `backend/app/markets/worker.py`
- Modify: `backend/app/realtime/publisher.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_decision_worker.py`
- Test: `backend/tests/test_p3_tracking_demand.py`
- Test: `backend/tests/test_p3_pipeline_metrics.py`
- Test: `backend/tests/integration/test_p3_worker_recovery.py`

**Orchestration contract:** a canonical sports change runs prediction then decision; a valid book change reuses the latest prediction and runs quote/decision only. Tracking demand comes from the pre-match coverage window and unresolved paper positions, not `ViewerLeaseStore`.

- [ ] **Step 1: Write ordering tests.** Prove sports update → prediction → decision, book update → quote/decision without another model call, rule change → action suppression, resolution → settlement, and commit-before-SSE for ledger transitions.
- [ ] **Step 2: Write backpressure and demand tests.** Assert bounded per-match queues, deterministic coalescing to the newest reducible book, no silent ledger drop, position tracking with zero viewers, main-tour tracking window and on-demand market-only loading for Challenger/ITF.
- [ ] **Step 3: Write freshness/gap tests.** A stale or gapped input preserves the last trusted snapshot, suppresses new BUY/SELL, records one tracking gap and resumes only after snapshot reconciliation.
- [ ] **Step 4: Run tests and verify failures.**

```bash
cd backend
uv run pytest tests/test_decision_worker.py tests/test_p3_tracking_demand.py tests/test_p3_pipeline_metrics.py -v
```

- [ ] **Step 5: Implement worker orchestration, independent market/decision publisher namespaces, lifecycle wiring and low-cardinality metrics.** Record ingress→canonical, canonical→prediction, prediction/book→decision and ledger-commit→publish histograms plus backlog/reconnect/gap counters; never put player, match or token IDs in metric labels.
- [ ] **Step 6: Add deterministic restart test and local latency gate.** Replay at least 10,000 valid book changes and 1,000 sports changes after warm-up; fail if local book→decision p95 exceeds `500ms`, sports→decision p95 exceeds `1s`, queues overflow or outputs differ across identical runs.

```bash
cd backend
uv run pytest -m infrastructure tests/integration/test_p3_worker_recovery.py -v
uv run pytest tests/test_p3_pipeline_metrics.py -v
```

- [ ] **Step 7: Run P2 realtime regressions, update controls and commit.**

```bash
cd backend
uv run pytest tests/test_realtime_worker.py tests/test_match_stream_api.py tests/integration/test_realtime_recovery.py -v
```

Suggested commit: `feat: orchestrate P3 realtime decisions`.

---

### T66: Expose Read-Only P3 REST, Independent SSE, and Chat Tools

**Outcome:** canonical P3 snapshots are available through stable business endpoints and compact Chat facts, while existing P2 match-stream semantics remain unchanged.

**Files:**

- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/service.py`
- Modify: `backend/app/chat/{tools,capabilities,orchestrator}.py`
- Test: `backend/tests/test_p3_api.py`
- Test: `backend/tests/test_market_stream_api.py`
- Test: `backend/tests/test_decision_stream_api.py`
- Test: `backend/tests/test_p3_chat_tools.py`
- Test: `backend/tests/test_match_stream_api.py`

**Public endpoints:**

```text
GET /api/v1/markets/opportunities
GET /api/v1/markets
GET /api/v1/paper/positions
GET /api/v1/markets/pulse
GET /api/v1/markets/stream
GET /api/v1/matches/{match_id}/decision
GET /api/v1/matches/{match_id}/decision/stream
```

- [ ] **Step 1: Write REST contract tests.** Assert canonical enum filters/pagination, internal IDs only, ordered opportunity/all/paper/pulse results, honest empty/degraded states and no provider/wallet/private-key fields in body, headers or error text.
- [ ] **Step 2: Write two independent SSE contract suites.** `markets/stream` emits ready/deltas/heartbeat; `decision/stream` emits its own ready/versioned decision deltas/heartbeat. A decision gap refetches only decision state; the existing `/matches/{id}/stream` payload, IDs and sports version remain byte-compatible with its regression fixtures.
- [ ] **Step 3: Write Chat tool tests.** `list_market_opportunities` and `get_match_decision` return bounded canonical fact packets; the LLM cannot create intents, change policy, infer missing probabilities or override the structured action.
- [ ] **Step 4: Run tests and verify failures.**

```bash
cd backend
uv run pytest tests/test_p3_api.py tests/test_market_stream_api.py tests/test_decision_stream_api.py tests/test_p3_chat_tools.py tests/test_match_stream_api.py -v
```

- [ ] **Step 5: Implement schemas, service queries, endpoints and Chat tools.** Use snapshot-first SSE, event IDs from each stream's own cursor, typed reason codes and existing auth/CORS/error conventions.
- [ ] **Step 6: Run all deterministic backend tests, update controls and commit.** Suggested commit: `feat: expose P3 decision APIs`.

---

### T67: Add Typed Frontend Transport, Thin Proxies, and Independent Stream Hooks

**Outcome:** frontend code can consume every P3 snapshot and delta through Next.js proxies without coupling provider fields or P2/P3 version counters.

**Files:**

- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/api/client.ts`
- Create: `frontend/hooks/use-market-stream.ts`
- Create: `frontend/hooks/use-decision-stream.ts`
- Create: `frontend/app/api/markets/{route.ts,opportunities/route.ts,pulse/route.ts,stream/route.ts}`
- Create: `frontend/app/api/paper/positions/route.ts`
- Create: `frontend/app/api/matches/[matchId]/decision/{route.ts,stream/route.ts}`
- Test: `frontend/lib/api/p3-types.test.ts`
- Test: `frontend/hooks/use-market-stream.test.tsx`
- Test: `frontend/hooks/use-decision-stream.test.tsx`
- Test: `frontend/app/api/p3-proxies.test.ts`

**Hook contract:** snapshot first; apply only `version + 1`; duplicate/old events are ignored; gap or malformed delta keeps last trusted view, marks degraded and refetches that resource; reconnect carries its own last event ID.

- [ ] **Step 1: Write runtime decoding tests for all P3 DTOs and every SSE event discriminator.** Unknown enums fail visibly instead of being coerced.
- [ ] **Step 2: Write hook tests with fake EventSource.** Cover ready, ordered delta, duplicate, gap/refetch, reconnect, heartbeat timeout, terminal resolution and component unmount cleanup; assert `useDecisionStream` never changes the `useMatchStream` cursor.
- [ ] **Step 3: Write proxy tests.** Preserve query strings, status, SSE headers and cancellation; reject non-GET methods; do not cache or persist business state.
- [ ] **Step 4: Run tests and verify failures.**

```bash
cd frontend
pnpm test -- lib/api/p3-types.test.ts hooks/use-market-stream.test.tsx hooks/use-decision-stream.test.tsx app/api/p3-proxies.test.ts
```

- [ ] **Step 5: Implement types, client methods, hooks and thin routes using the existing backend proxy helper.** Keep sample data in `p3-preview-data.ts`; production transport must never import it.
- [ ] **Step 6: Run typecheck plus existing match-stream regressions, update controls and commit.**

```bash
cd frontend
pnpm test
pnpm typecheck
```

Suggested commit: `feat: add typed P3 frontend transport`.

---

### T68: Connect Home Market Pulse and the `/markets` Discovery Workspace

**Outcome:** Home provides at most three actionable summaries and `/markets` provides approved Opportunity, All Markets and Paper Ledger views backed by canonical APIs.

**Files:**

- Create: `frontend/app/markets/page.tsx`
- Create: `frontend/components/markets/{markets-page,markets-tabs,market-filters,opportunity-row,market-row,paper-row,markets-state}.tsx`
- Modify: `frontend/components/home/home-intelligence.tsx`
- Modify: `frontend/components/home-page.tsx`
- Modify: `frontend/components/match/match-header.tsx`
- Modify: `frontend/components/home/home-hero.tsx`
- Test: `frontend/components/markets/markets-page.test.tsx`
- Test: `frontend/components/home-intelligence.test.tsx`
- Test: `frontend/e2e/p3-markets.spec.ts`

**Selection contract:** Home reserves one row for the most urgent open position, then selects live BUY → upcoming BUY → strongest WAIT, capped at three. `/markets` Opportunities contains only model-covered BUY/WAIT; All Markets contains every mapped moneyline; Paper Ledger is ledger-derived and never reconstructed from the browser.

- [ ] **Step 1: Write component tests for all three tabs, canonical filters, exact sorting and whole-row internal navigation.** Assert Challenger/ITF rows show market data without an unsupported/negative badge; no row exposes BUY/SELL buttons.
- [ ] **Step 2: Write degradation tests.** Cover loading skeletons, honest empty states, list-level transport failure, row-level stale/gap, market-only, incomplete book and closed/resolved market. Last trusted values remain visible with timestamp, while new actions disappear.
- [ ] **Step 3: Write Home Pulse tests.** Cover zero through five candidates, urgent position reservation, cap at three, internal match links, `/markets` link and absence of trajectories/ledger detail.
- [ ] **Step 4: Run tests and verify failures.**

```bash
cd frontend
pnpm test -- components/markets/markets-page.test.tsx components/home-intelligence.test.tsx components/home-page.test.tsx
```

- [ ] **Step 5: Implement the approved v0 geometry with production hooks.** Preserve existing typography/tokens/header and expose screen-reader text for freshness/action; use no color-only state or emoji icon.
- [ ] **Step 6: Add Playwright flows.** Test direct `/markets` load, each tab/filter, Home→Markets, Home/Markets→Match, refresh/reconnect, no horizontal overflow at `390×844`, keyboard tabs and 44px mobile targets.

```bash
cd frontend
pnpm test:e2e -- e2e/p3-markets.spec.ts
pnpm typecheck
pnpm build
```

- [ ] **Step 7: Update controls and commit.** Suggested commit: `feat: add P3 market discovery views`.

---

### T69: Connect the Match Decision Workbench and Ledger-Driven State Sequence

**Outcome:** Match Page presents one decision truth from market-only through settled, preserves the existing score/P2 intelligence and follows the approved desktop/mobile order.

**Files:**

- Create: `frontend/components/match/{decision-summary,probability-market-chart,decision-evidence,paper-lifecycle}.tsx`
- Modify: `frontend/components/match-page.tsx`
- Modify: `frontend/components/match/match-main.tsx`
- Modify: `frontend/components/match/match-sidebar.tsx`
- Test: `frontend/components/match/decision-summary.test.tsx`
- Test: `frontend/components/match/probability-market-chart.test.tsx`
- Test: `frontend/components/match/paper-lifecycle.test.tsx`
- Test: `frontend/components/match-page.test.tsx`
- Test: `frontend/e2e/p3-match.spec.ts`

**Desktop order:** Hero → full-width DecisionSummary → main Overview/Score/trajectory/evidence/Stats/Recent Control-PBP/lifecycle; sticky sidebar Assistant → Key Facts. **Mobile DOM order:** Hero → DecisionSummary → Score → Key Facts/Overview → trajectory → evidence → Stats → Recent Control/PBP → lifecycle → Assistant.

- [ ] **Step 1: Write state tests for `MARKET_ONLY`, `NO BET`, `WAIT`, `BUY`, `ENTRY_PENDING`, `MISSED`, `HOLD`, `SELL`, `EXIT_PENDING`, `EXITED`, `EXIT_MISSED`, `SETTLED` and orthogonal `STALE/GAP`.** Assert entry controls vanish after intent, there is one current action source, and no status text claims actual wagering.
- [ ] **Step 2: Write arithmetic and chart tests.** Both players keep independent executable asks; no forced 100% complement; `$10` average price/fees/edge/P&L agree with backend values; missing samples remain gaps, not interpolated lines; chart has a textual summary and accessible series names.
- [ ] **Step 3: Write ordering/duplication tests.** Assert mobile DOM order directly, desktop full-width seam, one DecisionSummary, removal of the old `MarketCard`, removal of duplicate AI insight/prompt card and preservation of score/Stats/PBP/Assistant.
- [ ] **Step 4: Run tests and verify failures.**

```bash
cd frontend
pnpm test -- components/match/decision-summary.test.tsx components/match/probability-market-chart.test.tsx components/match/paper-lifecycle.test.tsx components/match-page.test.tsx
```

- [ ] **Step 5: Implement the production connection with `useDecisionStream`.** Render server-provided action/reasons only; never calculate probability, edge, fill, settlement or lifecycle in React. The mobile Ask affordance scrolls/focuses Assistant and is not a trade CTA.
- [ ] **Step 6: Add Playwright state/reconnect/accessibility flows.** Cover direct refresh in every terminal/pending family, sports-stream and decision-stream gaps independently, keyboard focus, responsive overflow and no console/SSE errors.

```bash
cd frontend
pnpm test:e2e -- e2e/p3-match.spec.ts
pnpm test
pnpm typecheck
pnpm build
```

- [ ] **Step 7: Update controls and commit.** Suggested commit: `feat: add P3 match decision workbench`.

---

### T70: Prove Dual-Stream Replay, Recovery, Full Regression, and Visual Fidelity

**Outcome:** one deterministic scenario proves sports + books + decisions + one-shot ledger + settlement across restart, while all existing P1/P2 and approved P3 visuals remain stable.

**Files:**

- Create: `backend/tests/fixtures/replay/p3_dual_stream.jsonl`
- Create: `backend/tests/integration/test_p3_end_to_end_replay.py`
- Create: `backend/tests/integration/test_p3_latency_gate.py`
- Modify: `frontend/e2e/p3-markets.spec.ts`
- Modify: `frontend/e2e/p3-match.spec.ts`
- Modify: `frontend/e2e/p3.visual.spec.ts`
- Add reviewed images only under: `frontend/e2e/__screenshots__/{desktop,mobile}/`

**Replay contract:** fixture includes upcoming→live→finished sports state, both outcome books, a correction, disconnect/reconcile, BUY→FILLED, HOLD→SELL→EXIT_MISSED, final market resolution and all three evaluation tracks. A second fixture covers 50–50 settlement and no entry.

- [ ] **Step 1: Write the end-to-end integration test before completing fixtures.** Assert identical hashes on two runs, PostgreSQL/Redis restart recovery, independent sports/decision versions, explicit tracking gap, no duplicate intent/fill, provider-final settlement and no IDs/secrets in public output.
- [ ] **Step 2: Start local infrastructure and run the new integration gates.**

```bash
docker compose up -d postgres redis
cd backend
uv run alembic upgrade head
uv run pytest -m infrastructure tests/integration/test_p3_end_to_end_replay.py tests/integration/test_p3_latency_gate.py -v
```

- [ ] **Step 3: Run the complete deterministic backend gate.**

```bash
cd backend
uv run pytest -m "not llm_live and not provider_live and not api_tennis_live and not realtime_live and not polymarket_live and not end_to_end_live and not player_alias_llm_live and not player_directory_e2e_live" -v
uv run ruff check app tests
uv run ruff format --check app tests
```

- [ ] **Step 4: Run frontend component, type, build and all fake-browser gates.**

```bash
cd frontend
pnpm test
pnpm typecheck
pnpm build
pnpm test:e2e
```

- [ ] **Step 5: Generate exactly the approved 26 P3 visual cases only when expected rendering is complete.** Home: 4; Markets: 8; Match: 14, each represented across the designated desktop/mobile matrix from the v0 brief. Never approve an unrelated P1/P2 snapshot change.

```bash
cd frontend
pnpm test:e2e:update --grep "P3 visual"
pnpm test:e2e --grep "P3 visual"
```

- [ ] **Step 6: Inspect every expected/actual/diff image one by one.** Record filenames and checks for overflow, hierarchy, state label, arithmetic, stale action suppression, chart gaps, mobile order and 44px targets in `CURRENT.md`; any unreviewed pixel change fails the gate.
- [ ] **Step 7: Run `git diff --check`, scan changed files for provider IDs/credentials/private trading code, update controls and commit.** Suggested commit: `test: prove P3 replay and visual gates`.

---

### T71: Run the Real Read-Only Shadow Gate and Close P3

**Outcome:** current API-Tennis and public Polymarket data prove local read-only operation, exact mapping, freshness, safe abstention and browser rendering; P3 closes with evidence rather than a manufactured recommendation.

**Files:**

- Modify only if an evidenced defect is found: P3 implementation/tests from T57–T70
- Create: `backend/tests/live/test_p3_shadow_live.py`
- Create: `frontend/e2e/p3-live.spec.ts`
- Update: `PROJECT.md`
- Update: `ROADMAP.md`
- Update: `CURRENT.md`

**Input gate:** root `.env` must contain the existing API-Tennis and LLM settings plus any non-secret P3 paths/settings. Polymarket uses public read-only endpoints. A real historical dataset/model artifact may remain local and uncommitted, but its source/license audit, manifest hashes, benchmark metrics and promotion decision must be recorded without raw rows.

- [ ] **Step 1: Re-run the data audit and frozen benchmark on the real local source.** Select/calibrate on train/validation only, open the untouched test once, inspect overall/surface/tour/phase subgroups and write the versioned model card. If leakage, license, coverage, calibration or conservative net-EV evidence fails, mark the artifact `not_promoted`; runtime must emit `NO BET`, never BUY/SELL.
- [ ] **Step 2: Run current public REST/WS smokes.** Assert exact internal player-pair mapping, both outcome books, rules hash, fee/tick/min-size/delay, event freshness and reconnection. No active tennis market is an honest dated skip with discovery counts, not a fabricated fixture result.

```bash
cd backend
TENNIX_RUN_API_TENNIS_LIVE=1 TENNIX_RUN_POLYMARKET_LIVE=1 uv run pytest -m "api_tennis_live or polymarket_live" tests/live -v
```

- [ ] **Step 3: Run the combined shadow backend.** Observe at least one mapped pre-match or live market when available; compare API-Tennis and market freshness, verify all hard gates and persistence, and prohibit private endpoints/wallet credentials. A promoted model may output BUY/WAIT/NO BET; an unpromoted model must output only MARKET_ONLY/NO BET.

```bash
cd backend
TENNIX_RUN_P3_SHADOW_LIVE=1 uv run pytest -m end_to_end_live tests/live/test_p3_shadow_live.py -v
```

- [ ] **Step 4: Run real browser read-only flows through Next.js Route Handlers.** Check Home Pulse, all `/markets` tabs, Match dual SSE, refresh/reconnect, bilingual player links, terminal/empty/degraded copy, zero console errors and zero external/provider IDs in DOM/URLs.

```bash
cd frontend
TENNIX_RUN_P3_SHADOW_LIVE=1 pnpm test:e2e -- e2e/p3-live.spec.ts
```

- [ ] **Step 5: Re-run T70 deterministic gates after any live-found fix.** Do not update a baseline merely to hide a regression.
- [ ] **Step 6: Close only with an evidence table.** Record commits, exact commands/counts, model promotion outcome, dated live coverage/skips, latency percentiles, reviewed screenshots and known P4 deferrals. Update `PROJECT.md`, `ROADMAP.md`, `CURRENT.md`, then commit and push to `origin/main`.

Suggested commit: `docs: close P3 market decision support`.

---

## P3 Completion Gate

P3 is complete only when T56–T71 are done and all of the following are simultaneously true:

- public current tennis markets map only by exact internal player pair plus bounded event context; ambiguous mappings never reach a decision;
- independent model artifacts pass the frozen audit/promotion process, or production honestly remains `NO BET` with `MODEL_UNPROMOTED`;
- `$10` entry/exit quotes use actual side-specific depth, current fee/tick/min-size and sports delay;
- PostgreSQL is the authority for one-shot paper state, provider-final settlement and counterfactual tracks; Redis/browser loss cannot create or erase a position;
- sports and decision streams have independent cursors and recover independently without changing the existing P2 match-stream contract;
- Home, `/markets` and Match follow the approved v0 layout/state matrix on desktop and mobile, with all 26 P3 baselines individually reviewed;
- deterministic replay, PostgreSQL/Redis recovery, local latency, full backend/frontend/Playwright regressions and dated real read-only shadow checks have recorded evidence;
- no wallet, signing key, authenticated trading channel or real order submission exists anywhere in product code, configuration or tests.
