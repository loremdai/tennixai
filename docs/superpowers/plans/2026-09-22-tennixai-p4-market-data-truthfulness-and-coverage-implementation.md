# TennixAI P4.3 市场数据可信度与覆盖 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `/markets`「全部市场」以有界公开 batch snapshot 展示真实、带时间且状态明确的报价；让 Opportunities 对未晋升模型诚实解释为空；全程不放松模型、映射或 paper 安全门。

**Architecture:** 两条互不污染的报价车道。车道 A（新增）= 只读 CLOB `POST /books` 批量快照 → canonical latest-quote projection → 全部市场展示；车道 B（既有）= 严格映射 + 主巡单打 + tracking demand 的 WebSocket → Redis 热状态 → Prediction/Decision/Paper。`market_match_links.status='active'` 是 market→match 的唯一查询真相。Snapshot 车道绝不触发 PredictionService、DecisionWorker、PaperTradingService 或 WebSocket 订阅。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2 async / Alembic / PostgreSQL 16 / Redis 7 / httpx / Pydantic v2；Next.js（App Router）+ TypeScript + Tailwind + Playwright + Vitest。

## 权威输入

- 设计规格：[docs/superpowers/specs/2026-09-22-tennixai-p4-market-data-truthfulness-and-coverage-design.md](../specs/2026-09-22-tennixai-p4-market-data-truthfulness-and-coverage-design.md)（用户已于 2026-09-22 书面确认）
- 官方接口：[CLOB 批量 `POST /books`](https://docs.polymarket.com/api-reference/market-data/get-order-books-request-body)、[CLOB rate limits](https://docs.polymarket.com/api-reference/rate-limits)、[market WebSocket](https://docs.polymarket.com/market-data/realtime-data)
- 总控：[PROJECT.md](../../../PROJECT.md)、[ROADMAP.md](../../../ROADMAP.md)、[CURRENT.md](../../../CURRENT.md)

## Global Constraints（每个任务都隐含适用）

- **只读 Polymarket + paper-only**：不新增钱包、私钥、签名、认证或下单路径；不训练、评估、校准或晋升任何模型；不产生虚假 `BUY`/`WAIT`。
- **不改变** FOK 语义、one-shot intent、ledger 权威（PostgreSQL）、provider-final settlement、`BOOK_UNVERIFIABLE`/`NO_FILL` 与既有独立 SSE cursor 语义。
- **Snapshot 车道副作用为零**：snapshot 采集不得调用 `PredictionService`、`DecisionWorker`、`PaperTradingService`，不得创建 WebSocket 订阅、不得调用 LLM。
- **WebSocket roster 不扩大**：只有「严格 mapping + 领域资格（ATP/WTA/大满贯单打）+ tracking demand」三者同时满足才可进入 WebSocket；Challenger/ITF 可展示报价但不进入模型建议。
- **不引入** Kafka、Redis Streams、微服务、完整行情历史仓库、自动交易、LLM 补全。
- **凭据与身份**：根目录 `.env` 是唯一人工配置入口；不得创建或读取子目录环境文件；公开 API、SSE、Chat、URL、日志、错误页与截图不得出现 provider token / condition ID / event ID / 密钥 / 钱包 / 签名材料。provider ID 只能存在于 `market_external_ids`（私有映射）与 14 天 raw 诊断表。
- **raw 保留 14 天**：market 批量响应按 batch 写入既有 `raw_provider_events`，沿用既有清理；canonical/derived 长期保留。
- **视觉真相**：不新画 v0 原型；`?preview=p3` 冻结原型是视觉真源，布局几何、桌面 `1440×1000`、移动 `390×844` 保持。任何 PNG 变化必须逐张产出 expected/actual/diff 并由用户审阅；**不得**用 mask、阈值调整、skip、retry 或盲目重录规避。
- **未跟踪文件保护**：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts` 不得修改、删除或提交。
- **单主任务**：同一时间只有一个 `in_progress` 主任务；每个任务的领取、节点、完成与交接都必须更新并推送三份总控文件。
- **前端**：`frontend/AGENTS.md` 要求写前端代码前先读 `frontend/node_modules/next/dist/docs/` 中与本次改动相关的指南；不得依赖训练数据里的 Next.js 约定。

## 全局命令约定

```bash
# 后端确定性套件（默认门；不触外部配额）
cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure and not player_alias_llm_live and not player_directory_e2e_live and not polymarket_live and not local_runtime_live" -q

# 后端 infrastructure（需要 compose 的 PostgreSQL/Redis）
cd backend && uv run pytest -m infrastructure -q

# 后端单文件 / 单用例
cd backend && uv run pytest tests/test_market_worker.py -v
cd backend && uv run pytest tests/test_market_worker.py::test_name -v

# ruff（只针对本任务新增/修改的文件）
cd backend && uv run ruff check app/... tests/... && uv run ruff format --check app/... tests/...

# 前端
cd frontend && pnpm test          # vitest
cd frontend && pnpm typecheck
cd frontend && pnpm build
cd frontend && pnpm test:e2e      # 功能并行 + 视觉串行两条 lane
cd frontend && pnpm test:e2e --grep @visual   # 只跑视觉
```

**提交纪律**：每个任务的实现提交只包含该任务的文件；提交信息用仓库既有前缀（`feat:` / `fix:` / `test:` / `docs:`），并在正文末尾附：

```
Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

**总控纪律**：每个任务开始时在 `CURRENT.md` 写入执行者/ADE、`main`、起始提交与时间并推送；完成时把任务行改为 `done` 并附完成提交与实际验证证据（未运行的测试不得声称通过），同时更新 `ROADMAP.md`，必要时更新 `PROJECT.md`。

## 文件结构总览

**后端新增**

| 文件 | 责任 |
|---|---|
| `backend/app/markets/quotes.py` | canonical 展示报价状态机：hot book / projection → `DisplayQuote`（规格 §5.3 七个状态的唯一实现） |
| `backend/app/markets/quote_snapshot.py` | 批量快照的 canonical 解析、投影写入、raw batch 保留与 source precedence |
| `backend/app/runtime/market_snapshot.py` | 有界 120 秒 snapshot 调度作业：候选选择、公平轮转、分批、429/backoff、coverage 汇总 |
| `backend/migrations/versions/20260922_0006_market_quote_snapshots.py` | 可逆 migration：`market_quote_snapshots` 单行/market 投影 |

**后端修改**

| 文件 | 改动 |
|---|---|
| `backend/app/persistence/market_repositories.py` | `MarketOverviewRow` + active-link join 读模型；`latest_predictions_for_matches` 批量；`MarketQuoteSnapshotRepository` |
| `backend/app/persistence/models.py` | `MarketQuoteSnapshotRow` |
| `backend/app/markets/publisher.py` | `get_hot_books`（单次 MGET） |
| `backend/app/markets/polymarket.py` | `get_order_books`（`POST /books` 批量、typed 429/坏 payload） |
| `backend/app/markets/polymarket_dtos.py` | 批量响应条目 DTO（复用 `BookDto`） |
| `backend/app/markets/live.py` | 每连接 keepalive task；`MarketFeedClosed`（正常关闭）与 `MarketFeedDisconnected`（异常）分离 |
| `backend/app/markets/worker.py` | 正常关闭生命周期分支；不误报全局故障 |
| `backend/app/service.py` | `markets()` 用 active link 与批量装载；`opportunities()` 增 aggregate availability；`markets_snapshot()` 增 availability |
| `backend/app/api/schemas.py` | `MarketQuoteDto`、`MarketSummaryDto` 显式 quote/model/decision 语义、`OpportunityAvailabilityDto` |
| `backend/app/api/routes.py` | `/markets/opportunities` 返回 availability 信封 |
| `backend/app/config.py`、`backend/app/runtime/models.py`、`backend/app/runtime/config.py` | 四个有界 snapshot 配置项贯通 |
| `backend/app/runtime/daemon.py`、`backend/app/runtime/health.py`、`backend/app/runtime/assembly.py` | snapshot job 接线、coverage health、WS 热 book → 投影镜像 |
| `backend/app/runtime/verify.py` | 有界真实门新增 `market_quote_snapshot` |
| `.env.example` | 四个新配置键 |
| `docs/runbooks/local-real-runtime.md` | 双通道语义、新配置、coverage 健康口径 |

**前端修改**

| 文件 | 改动 |
|---|---|
| `frontend/lib/api/p3-types.ts` | `quote`/`quote_state`/`quote_source`/`model_availability`/`decision_action`/availability 的严格解码（未知 enum fail closed） |
| `frontend/lib/p3-view-models.ts` | `MarketRowModel` 携带 quote 状态与来源；`toMarketRow` 不再由 null action 伪造 `market_only` |
| `frontend/lib/api/client.ts` | opportunities 列表返回 availability |
| `frontend/components/markets/market-row.tsx`、`opportunities-view.tsx`、`markets-state.tsx` | 报价状态标签、缺失字段的 `—`、低级别无负向标签、未晋升空态文案、正确导航 |
| `frontend/components/markets/markets-page.test.tsx`、`frontend/lib/api/p3-types.test.ts`、`frontend/lib/p3-view-models.test.ts` | 新状态矩阵单测 |
| `frontend/e2e/p3-markets.spec.ts` | 双视口新场景 |
| `frontend/e2e/p3.visual.spec.ts` 与 `frontend/e2e/__screenshots__/**` | 冻结基线零变化证据（仅在有意变化时逐张审阅后更新） |

## 任务间接口契约（跨任务签名，务必逐字一致）

```python
# T84 产出，T87 消费
class MarketOverviewRow:            # app/persistence/market_repositories.py
    market_id: str
    question: str | None
    status: str
    rules_version: int
    observed_at: datetime | None
    updated_at: datetime
    outcome_a_player_id: str | None
    outcome_a_name: str | None
    outcome_b_player_id: str | None
    outcome_b_name: str | None
    active_match_id: str | None     # ONLY from market_match_links.status='active'

async def MarketRepository.list_market_overviews() -> list[MarketOverviewRow]
async def MarketRepository.latest_predictions_for_matches(match_ids: Sequence[str]) -> dict[str, PredictionSnapshot]
async def MarketHotPublisher.get_hot_books(market_ids: Sequence[str]) -> dict[str, OrderBookState]

# T85 产出，T86/T87 消费
class QuoteState(StrEnum):          # app/markets/quotes.py
    REALTIME = "realtime"; SNAPSHOT = "snapshot"; PARTIAL = "partial"
    NO_LIQUIDITY = "no_liquidity"; UNAVAILABLE = "unavailable"
    STALE = "stale"; LIMITED = "limited"

class QuoteSource(StrEnum):         # app/markets/quotes.py
    REALTIME = "realtime"; SNAPSHOT = "snapshot"

class DisplayQuote(FrozenModel):    # app/markets/quotes.py
    state: QuoteState
    source: QuoteSource | None
    as_of: datetime | None
    outcome_bids: tuple[str | None, str | None]
    outcome_asks: tuple[str | None, str | None]
    best_bid: tuple[str, str] | None
    best_ask: tuple[str, str] | None
    spread: str | None
    depth_usd: str | None

def display_quote(*, hot_book, snapshot, now: datetime, realtime_fresh_seconds: int, snapshot_fresh_seconds: int) -> DisplayQuote

class ClobBooksBatch(FrozenModel):  # app/markets/quote_snapshot.py（PRIVATE 适配层模型）
    books: Mapping[str, TokenBook]  # token_id -> 单边 canonical levels（PRIVATE）
    missing_tokens: tuple[str, ...]
    malformed_tokens: tuple[str, ...]
    raw: tuple[dict, ...]           # 原始响应，仅用于 14 天 raw 表

class TokenBook(FrozenModel):
    token_id: str
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    book_hash: str
    provider_timestamp: datetime | None

async def PolymarketProvider.get_order_books(token_ids: Sequence[str]) -> ClobBooksBatch

async def MarketQuoteSnapshotRepository.upsert(record: QuoteSnapshotRecord) -> bool
async def MarketQuoteSnapshotRepository.load(market_id: str) -> QuoteSnapshotRecord | None
async def MarketQuoteSnapshotRepository.load_many(market_ids: Sequence[str]) -> dict[str, QuoteSnapshotRecord]

# T86 产出，T89 消费
class MarketQuoteCoverage(FrozenModel):   # app/runtime/models.py
    generated_at: datetime
    candidate: int = 0; attempted: int = 0
    fresh_realtime: int = 0; fresh_snapshot: int = 0; partial: int = 0
    no_liquidity: int = 0; unavailable: int = 0; stale: int = 0; limited: int = 0
    batch_failures: int = 0
    rate_limited: bool = False
    retry_after_until: datetime | None = None
    last_successful_batch_at: datetime | None = None

def RuntimeHealthRegistry.set_market_coverage(coverage: MarketQuoteCoverage | None) -> None

# T87 产出，T88/T89 消费
class MarketQuoteDto(BaseModel):          # app/api/schemas.py
    state: str; source: str | None; as_of: datetime | None
    outcome_bids: tuple[str | None, str | None] | None
    outcome_asks: tuple[str | None, str | None] | None
    best_bid: tuple[str, str] | None; best_ask: tuple[str, str] | None
    spread: str | None; depth_usd: str | None

class OpportunityAvailabilityDto(BaseModel):
    reason: str          # ELIGIBLE_UNPROMOTED | NO_ELIGIBLE_ACTION | NO_COVERED_MARKET | DECISION_GAP
    model_status: str    # "not_promoted" | "promoted" | "unknown"
```

## 任务顺序与依赖

```
T84 (active-link read model)  ──┬─→ T87 (typed contract, 读 quote)  ─→ T88 (UI)  ─→ T89 (收口)
T85 (batch adapter + projection)┴─→ T86 (snapshot 调度 + health + WS 加固)
```

T84–T89 必须顺序领取/完成/提交/推送；不得跳项，不得把两个任务合并为一个提交。

---

# T84 — Active-Link Market Overview Projection

**交付物**：`market_match_links.status='active'` 成为 market→match 的唯一查询真相；Markets 查询一次批量装载 links / match facts / 最新 quote / prediction / decision，无 N+1；link 导航、tier、phase、player names 恢复；replaced / inactive link 不泄漏。

**不改变**：API 形状（`MarketSummaryDto` 字段集不变，只是取值来源正确）、`markets.match_id` 列（保留为历史兼容字段，不回填）、decision/paper 语义、Redis 命名空间。

### Task T84.1: 新增 active-link read model 与批量装载方法

**Files:**
- Modify: `backend/app/persistence/market_repositories.py`
- Modify: `backend/app/markets/publisher.py`
- Test: `backend/tests/test_market_overview_projection.py`（新建，T84.2 使用）

**Interfaces:**
- Consumes: 既有 `MarketRow`、`MarketMatchLinkRow`、`PredictionSnapshotRow`、`MarketHotPublisher`
- Produces: `MarketOverviewRow`、`MarketRepository.list_market_overviews() -> list[MarketOverviewRow]`、`MarketRepository.latest_predictions_for_matches(ids) -> dict[str, PredictionSnapshot]`、`MarketHotPublisher.get_hot_books(ids) -> dict[str, OrderBookState]`

- [ ] **Step 1: 先写失败测试（integration，真实 PostgreSQL 上的 SQL 真相）**

在 `backend/tests/integration/test_p3_query_service.py` 末尾追加（该文件已有 `_seed`、`pytestmark = pytest.mark.infrastructure` 与 `database` fixture）：

```python
async def test_market_overview_joins_active_links_only(database: Database) -> None:
    """`markets.match_id` is legacy; the ACTIVE link is the only match truth."""
    seeded = await _seed(database)
    markets = MarketRepository(database)
    match_id = seeded["match_id"]
    player_a = seeded["player_a"]
    player_b = seeded["player_b"]

    # A newer market replaces the seeded link for the same match; the older
    # link flips to `replaced` and must never leak a match identity again.
    suffix = uuid4().hex[:10]
    replacement = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev_{suffix}",
        condition_id=f"cond_{uuid4().hex}",
    )
    await markets.save_market(
        make_market(replacement, match_id=None, player_a=player_a, player_b=player_b)
    )
    await markets.link_match(
        market_id=replacement, match_id=match_id, evidence={"pair": [player_a, player_b]}
    )

    overviews = {row.market_id: row for row in await markets.list_market_overviews()}
    assert overviews[replacement].active_match_id == match_id
    assert overviews[replacement].link_evidence_available is True
    # The legacy column is untouched and never used as read truth.
    assert overviews[seeded["market_id"]].active_match_id is None

    overflow = await MarketRepository(database).list_market_overviews()
    assert all(row.market_id for row in overflow)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/integration/test_p3_query_service.py::test_market_overview_joins_active_links_only -v`
Expected: FAIL — `MarketRow` object has no attribute `market_id`（当前 `list_market_overviews` 返回 `MarketRow`，无 `active_match_id`）

- [ ] **Step 3: 实现 `MarketOverviewRow` 与 join 读模型**

在 `backend/app/persistence/market_repositories.py` 顶部 import 区加入：

```python
from dataclasses import dataclass
```

在 `class LinkFrozenError` 之后加入：

```python
@dataclass(frozen=True)
class MarketOverviewRow:
    """One market joined to its ACTIVE match link (T84).

    `active_match_id` comes exclusively from `market_match_links` with
    `status='active'`; the legacy `markets.match_id` column is historical
    compatibility only and is never read as market→match truth. The row
    carries internal IDs only.
    """

    market_id: str
    question: str | None
    status: str
    rules_version: int
    observed_at: datetime | None
    updated_at: datetime
    outcome_a_player_id: str | None
    outcome_a_name: str | None
    outcome_b_player_id: str | None
    outcome_b_name: str | None
    active_match_id: str | None
    link_evidence_available: bool
```

把 `list_market_overviews` 整体替换为：

```python
    async def list_market_overviews(self) -> list[MarketOverviewRow]:
        """Every known market with its ACTIVE match link, most recent first.

        ONE query: `market_match_links` is joined on `status='active'` as
        part of the join condition, so replaced/inactive links can never
        leak a match identity into the read model. Callers must load match
        facts, quotes and prediction/decision evidence in bulk — never per
        row (T84 forbids N+1 SQL/Redis on this path).
        """
        statement = (
            select(
                MarketRow.id,
                MarketRow.question,
                MarketRow.status,
                MarketRow.rules_version,
                MarketRow.observed_at,
                MarketRow.updated_at,
                MarketRow.outcome_a_player_id,
                MarketRow.outcome_a_name,
                MarketRow.outcome_b_player_id,
                MarketRow.outcome_b_name,
                MarketMatchLinkRow.match_id,
                MarketMatchLinkRow.evidence,
            )
            .select_from(MarketRow)
            .outerjoin(
                MarketMatchLinkRow,
                (MarketMatchLinkRow.market_id == MarketRow.id)
                & (MarketMatchLinkRow.status == "active"),
            )
            .order_by(MarketRow.updated_at.desc())
        )
        async with self._database.session() as session:
            rows = (await session.execute(statement)).all()
        return [
            MarketOverviewRow(
                market_id=row[0],
                question=row[1],
                status=row[2],
                rules_version=int(row[3]),
                observed_at=row[4],
                updated_at=row[5],
                outcome_a_player_id=row[6],
                outcome_a_name=row[7],
                outcome_b_player_id=row[8],
                outcome_b_name=row[9],
                active_match_id=row[10],
                link_evidence_available=bool(row[10]) and bool(row[11]),
            )
            for row in rows
        ]
```

在 `latest_prediction` 之后加入批量变体（保留单条版本，供 `match_decision`/`opportunities` 既有路径使用）：

```python
    async def latest_predictions_for_matches(
        self, match_ids: Sequence[str]
    ) -> dict[str, PredictionSnapshot]:
        """Newest prediction evidence per match in ONE query (no N+1).

        Same ordering contract as `latest_prediction`: newest `as_of`, then
        newest row id for identical timestamps.
        """
        ids = {match_id for match_id in match_ids if match_id}
        if not ids:
            return {}
        statement = (
            select(PredictionSnapshotRow)
            .where(PredictionSnapshotRow.match_id.in_(ids))
            .distinct(PredictionSnapshotRow.match_id)
            .order_by(
                PredictionSnapshotRow.match_id,
                PredictionSnapshotRow.as_of.desc(),
                PredictionSnapshotRow.id.desc(),
            )
        )
        async with self._database.session() as session:
            rows = (await session.execute(statement)).scalars().all()
        return {
            row.match_id: PredictionSnapshot.model_validate(row.payload) for row in rows
        }
```

把新公开名字加入 `__all__`：

```python
__all__ = [
    "LinkFrozenError",
    "MarketOverviewRow",
    "MarketRepository",
]
```

- [ ] **Step 4: 实现 `MarketHotPublisher.get_hot_books`（单次 MGET）**

在 `backend/app/markets/publisher.py` 的 `get_hot_book` 之后加入：

```python
    async def get_hot_books(
        self, market_ids: Sequence[str]
    ) -> dict[str, OrderBookState]:
        """One MGET for every requested market (T84: no per-row Redis calls).

        Missing keys and unparsable payloads are skipped: absent hot state
        degrades to "not present", never to a fabricated book.
        """
        ids = [market_id for market_id in market_ids if market_id]
        if not ids:
            return {}
        raw_values = await self._redis.mget([market_hot_key(market_id) for market_id in ids])
        books: dict[str, OrderBookState] = {}
        for market_id, raw in zip(ids, raw_values, strict=True):
            if raw is None:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            try:
                books[market_id] = OrderBookState.model_validate_json(raw)
            except ValueError:
                continue
        return books
```

并把文件顶部 import 补上 `from collections.abc import Callable, Sequence`（保留既有 `Callable`）。

- [ ] **Step 5: 给测试用 `InMemoryRedis` 增加 `mget`**

在 `backend/tests/realtime_fakes.py` 的 `InMemoryRedis.get` 之后加入：

```python
    async def mget(self, names: list[str]) -> list[str | None]:
        return [await self.get(name) for name in names]
```

- [ ] **Step 6: 运行 integration 测试确认通过**

Run: `cd backend && uv run pytest tests/integration/test_p3_query_service.py::test_market_overview_joins_active_links_only -v`
Expected: PASS（需要 compose 的 PostgreSQL 在跑且已 `uv run alembic upgrade head`）

- [ ] **Step 7: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add backend/app/persistence/market_repositories.py backend/app/markets/publisher.py \
        backend/tests/realtime_fakes.py backend/tests/integration/test_p3_query_service.py
git commit -m "feat: project markets from active match links"
```

### Task T84.2: 让 `P3QueryService.markets()` 只认 active link 并批量装载

**Files:**
- Modify: `backend/app/service.py`（`P3QueryService.markets()` 与 `_position_dtos()` 的 hot-book 批量化）
- Test: `backend/tests/test_market_overview_projection.py`（新建）

**Interfaces:**
- Consumes: T84.1 的全部方法
- Produces: `markets()` 返回的 `MarketPageDto` 中 `match_id` 一律来自 active link；`_hot_book` 仍保留给单市场路径

- [ ] **Step 1: 先写失败测试（确定性单元测试，spy 证明零 N+1）**

新建 `backend/tests/test_market_overview_projection.py`：

```python
"""Active-link projection tests for the markets read path (T84).

Deterministic spies prove the query path loads every dependency in bulk:
one overview query, one decision query, one batched match-facts call, one
batched prediction call and one batched Redis read — for any row count.
"""

from datetime import UTC, datetime
from decimal import Decimal

from app.markets.models import BookLevel, OrderBookState, OutcomeBook
from app.persistence.market_repositories import MarketOverviewRow
from app.service import P3QueryService

NOW = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)


def overview(
    market_id: str,
    *,
    match_id: str | None = None,
    status: str = "open",
    question: str | None = None,
) -> MarketOverviewRow:
    return MarketOverviewRow(
        market_id=market_id,
        question=question,
        status=status,
        rules_version=1,
        observed_at=NOW,
        updated_at=NOW,
        outcome_a_player_id="ply_a",
        outcome_a_name="Provider A",
        outcome_b_player_id="ply_b",
        outcome_b_name="Provider B",
        active_match_id=match_id,
        link_evidence_available=match_id is not None,
    )


class SpyMarkets:
    """Repository spy: per-row calls raise instead of counting (N+1 kill-switch)."""

    def __init__(self, rows, *, observations=(), predictions=None):
        self._rows = list(rows)
        self._observations = list(observations)
        self._predictions = dict(predictions or {})
        self.overview_calls = 0
        self.observation_calls = 0
        self.prediction_calls: list[tuple[str, ...]] = []

    async def list_market_overviews(self):
        self.overview_calls += 1
        return list(self._rows)

    async def latest_decision_observations(self):
        self.observation_calls += 1
        return list(self._observations)

    async def latest_predictions_for_matches(self, match_ids):
        self.prediction_calls.append(tuple(match_ids))
        return dict(self._predictions)

    async def latest_prediction(self, match_id):
        raise AssertionError("markets() must not fetch predictions per row")


class SpyHotBooks:
    def __init__(self, books=None):
        self._books = dict(books or {})
        self.bulk_calls: list[tuple[str, ...]] = []

    async def get_hot_books(self, market_ids):
        self.bulk_calls.append(tuple(market_ids))
        return {mid: self._books[mid] for mid in market_ids if mid in self._books}

    async def get_hot_book(self, market_id):
        raise AssertionError("markets() must not fetch hot books per row")


def book(market_id: str) -> OrderBookState:
    return OrderBookState(
        market_id=market_id,
        books=(
            OutcomeBook(
                outcome_player_id="ply_a",
                bids=(BookLevel(price=Decimal("0.58"), size=Decimal("120")),),
                asks=(BookLevel(price=Decimal("0.60"), size=Decimal("90")),),
            ),
            OutcomeBook(
                outcome_player_id="ply_b",
                bids=(BookLevel(price=Decimal("0.40"), size=Decimal("80")),),
                asks=(BookLevel(price=Decimal("0.42"), size=Decimal("70")),),
            ),
        ),
        sequence=9,
        book_hash=f"hash_{market_id}",
        provider_timestamp=NOW,
        received_at=NOW,
    )


class StubFactsService(P3QueryService):
    """P3QueryService with the batched match-facts lookup stubbed out."""

    def __init__(self, *, facts, **kwargs):
        super().__init__(database=None, **kwargs)
        self._facts = dict(facts)
        self.fact_calls: list[tuple[str, ...]] = []

    async def _match_facts(self, match_ids):
        self.fact_calls.append(tuple(match_ids))
        return {mid: self._facts[mid] for mid in match_ids if mid in self._facts}


async def test_markets_uses_active_link_and_loads_dependencies_in_bulk() -> None:
    rows = [
        overview("mkt_linked", match_id="mat_1"),
        overview("mkt_unlinked", question="Unlinked moneyline"),
        overview("mkt_linked_two", match_id="mat_2"),
    ]
    spy = SpyMarkets(rows)
    hot = SpyHotBooks({"mkt_linked": book("mkt_linked")})
    service = StubFactsService(
        facts={
            "mat_1": {
                "player_names": ("Alpha", "Beta"),
                "player_ids": ("ply_a", "ply_b"),
                "tier": "atp",
                "gender": "men",
                "tournament_name": "Test Open",
                "phase": "live",
            },
            "mat_2": {
                "player_names": ("Gamma", "Delta"),
                "player_ids": ("ply_a", "ply_b"),
                "tier": "challenger",
                "gender": "men",
                "tournament_name": "Test Challenger",
                "phase": "prematch",
            },
        },
        markets=spy,
        paper=None,
        hot_books=hot,
    )

    page = await service.markets(page=1, page_size=50)
    by_id = {row.market_id: row for row in page.markets}

    # The ACTIVE link drives match identity, facts and quote lookup.
    assert by_id["mkt_linked"].match_id == "mat_1"
    assert by_id["mkt_linked"].tier == "atp"
    assert by_id["mkt_linked"].phase == "live"
    assert by_id["mkt_linked"].tournament_name == "Test Open"
    assert by_id["mkt_linked"].player_names == ("Alpha", "Beta")
    assert by_id["mkt_linked"].outcome_asks == ("0.60", "0.42")
    assert by_id["mkt_linked_two"].match_id == "mat_2"
    assert by_id["mkt_linked_two"].tier == "challenger"

    # An unlinked market keeps its canonical question and invents nothing.
    unlinked = by_id["mkt_unlinked"]
    assert unlinked.match_id is None
    assert unlinked.question == "Unlinked moneyline"
    assert unlinked.tier is None and unlinked.tournament_name is None
    assert unlinked.best_ask is None
    assert unlinked.model_probability is None

    # Bulk-only: one call each, regardless of row count.
    assert spy.overview_calls == 1
    assert spy.observation_calls == 1
    assert len(spy.prediction_calls) == 1
    assert len(hot.bulk_calls) == 1
    assert len(service.fact_calls) == 1
    assert set(spy.prediction_calls[0]) == {"mat_1", "mat_2"}
    assert set(hot.bulk_calls[0]) == {"mkt_linked", "mkt_unlinked", "mkt_linked_two"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_market_overview_projection.py -v`
Expected: FAIL — `AttributeError: 'MarketOverviewRow' object has no attribute 'id'`（现有实现按 `MarketRow` 属性访问）

- [ ] **Step 3: 重写 `markets()`**

把 `backend/app/service.py` 中 `async def markets(...)` 的换行到 `return MarketPageDto(...)` 之间整体替换为（保持既有筛选、排序、分页与 DTO 字段集不变）：

```python
    async def markets(self, *, tier=None, gender=None, phase=None, page=1, page_size=20):
        from app.api.schemas import MarketPageDto, MarketSummaryDto

        market_rows = await self._markets.list_market_overviews()
        observations = await self._markets.latest_decision_observations()
        decision_by_match = {
            observation.match_id: observation for observation in observations
        }
        # ACTIVE links are the only match truth; every dependency below is
        # loaded in ONE bulk call regardless of row count (T84: no N+1).
        match_ids = [row.active_match_id for row in market_rows]
        facts = await self._match_facts(match_ids)
        predictions = await self._markets.latest_predictions_for_matches(match_ids)
        hot_books = await self._bulk_hot_books([row.market_id for row in market_rows])
        summaries = []
        for row in market_rows:
            match_id = row.active_match_id
            match_facts = facts.get(match_id, {}) if match_id else {}
            market_phase = match_facts.get("phase")
            if row.status in ("closed", "resolved"):
                market_phase = "closed"
            elif market_phase is None:
                market_phase = (
                    "prematch"
                    if row.status in ("scheduled", "open", "unknown")
                    else "closed"
                )
            observation = decision_by_match.get(match_id) if match_id else None
            book = hot_books.get(row.market_id)
            outcome_ids = (row.outcome_a_player_id, row.outcome_b_player_id)
            outcome_names = (row.outcome_a_name, row.outcome_b_name)
            best_bid, best_ask = self._best_levels(book, row.outcome_a_player_id)
            outcome_bids, outcome_asks, spread, depth = self._outcome_levels(
                book, outcome_ids
            )
            prediction = predictions.get(match_id) if match_id else None
            model_covered = prediction is not None and prediction.availability.value in (
                "available",
                "degraded",
            )
            model_probability = None
            if prediction is not None and row.outcome_a_player_id is not None:
                for outcome in prediction.outcomes:
                    if outcome.player_id == row.outcome_a_player_id:
                        model_probability = outcome.probability
                        break
            # Canonical directory names win; provider outcome labels are the
            # fallback so a row is never nameless when the market knows them.
            fact_ids = match_facts.get("player_ids")
            fact_names = match_facts.get("player_names")
            name_by_id = (
                dict(zip(fact_ids, fact_names, strict=False))
                if fact_ids is not None and fact_names is not None
                else {}
            )
            resolved_names = [
                (name_by_id.get(player_id) if player_id else None) or outcome_name
                for player_id, outcome_name in zip(outcome_ids, outcome_names, strict=False)
            ]
            player_names = (
                (resolved_names[0], resolved_names[1])
                if resolved_names[0] is not None and resolved_names[1] is not None
                else None
            )
            summaries.append(
                MarketSummaryDto(
                    market_id=row.market_id,
                    match_id=match_id,
                    question=row.question,
                    status=row.status,
                    tournament_name=match_facts.get("tournament_name"),
                    tier=match_facts.get("tier"),
                    gender=match_facts.get("gender"),
                    phase=market_phase,
                    model_covered=model_covered,
                    action=(
                        observation.action.value if observation is not None else None
                    ),
                    reason_code=(
                        observation.reason_code if observation is not None else None
                    ),
                    player_ids=(
                        outcome_ids
                        if outcome_ids[0] is not None and outcome_ids[1] is not None
                        else None
                    ),
                    player_names=player_names,
                    model_probability=model_probability,
                    best_bid=best_bid,
                    best_ask=best_ask,
                    outcome_bids=outcome_bids,
                    outcome_asks=outcome_asks,
                    spread=_p3_decimal_text(spread),
                    depth_usd=_p3_decimal_text(depth),
                    is_stale=(
                        (observation.is_stale if observation is not None else False)
                        or (book.is_stale if book is not None else False)
                    ),
                    has_gap=observation.has_gap if observation is not None else False,
                    as_of=row.observed_at,
                )
            )
        if tier is not None:
            summaries = [item for item in summaries if item.tier == tier]
        if gender is not None:
            summaries = [item for item in summaries if item.gender == gender]
        if phase is not None:
            summaries = [item for item in summaries if item.phase == phase]
        total = len(summaries)
        start = (page - 1) * page_size
        return MarketPageDto(
            markets=summaries[start : start + page_size],
            page=page,
            page_size=page_size,
            total=total,
        )
```

在 `_hot_book` 之后加入批量读取助手，并把 `_position_dtos()` 的 `book = await self._hot_book(position.market_id)` 改为批量结果：

```python
    async def _bulk_hot_books(self, market_ids) -> dict:
        """One MGET for every requested market; absent hot state means the
        market is simply missing from the result — never a fabricated book."""
        ids = tuple(market_id for market_id in market_ids if market_id)
        if self._hot_books is None or not ids:
            return {}
        try:
            return await self._hot_books.get_hot_books(ids)
        except Exception:
            return {}
```

`_position_dtos()` 内：

```python
    async def _position_dtos(self, positions):
        from app.api.schemas import PaperPositionDto

        facts = await self._match_facts([position.match_id for position in positions])
        hot_books = await self._bulk_hot_books(
            [position.market_id for position in positions]
        )
        rows = []
        for position in positions:
            book = hot_books.get(position.market_id)
```

（其余行不变。）

- [ ] **Step 4: 更新既有 Q3 查询服务集成测试的 hot-book stub**

把 `backend/tests/integration/test_p3_query_service.py` 中的 `StubHotBooks` 替换为：

```python
class StubHotBooks:
    def __init__(self, states: dict) -> None:
        self._states = states
        self.bulk_calls: list[tuple[str, ...]] = []

    async def get_hot_books(self, market_ids):
        self.bulk_calls.append(tuple(market_ids))
        return {mid: self._states[mid] for mid in market_ids if mid in self._states}

    async def get_hot_book(self, market_id: str):
        return self._states.get(market_id)
```

在 `test_enriched_fields_and_pulse_selection` 末尾追加批量读取断言：

```python
    assert hot_books.bulk_calls  # every row's quote came from ONE bulk read
    assert len(hot_books.bulk_calls) <= 2
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && uv run pytest tests/test_market_overview_projection.py tests/integration/test_p3_query_service.py -v`
Expected: PASS（integration 需要 compose PostgreSQL）

- [ ] **Step 6: 加入 no-N+1 的 SQL 语句计数证据（integration）**

在 `backend/tests/integration/test_p3_query_service.py` 顶部 import 区加入 `from sqlalchemy import event`，并追加：

```python
async def test_markets_query_issues_a_constant_number_of_statements(
    database: Database,
) -> None:
    """Row count must not change the statement count (no N+1)."""
    seeded = await _seed(database)
    markets = MarketRepository(database)
    queries = P3QueryService(
        database=database, markets=markets, paper=PaperLedgerRepository(database),
        hot_books=None,
    )

    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(database.engine.sync_engine, "before_cursor_execute", _record)
    try:
        statements.clear()
        await queries.markets(page=1, page_size=50)
        baseline = len(statements)

        extra_ids = []
        for index in range(3):
            suffix = f"{uuid4().hex[:8]}{index}"
            match = await PostgresIdentityRepository(database).get_or_create(
                "match", "itest-t84", suffix
            )
            market = await markets.get_or_create_market_id(
                provider="polymarket",
                provider_event_id=f"ev84_{suffix}",
                condition_id=f"cond84_{uuid4().hex}",
            )
            await markets.save_market(make_market(market, match_id=None))
            await markets.link_match(
                market_id=market, match_id=match, evidence={"pair": ["a", "b"]}
            )
            extra_ids.append(market)

        statements.clear()
        await queries.markets(page=1, page_size=50)
        expanded = len(statements)
    finally:
        event.remove(database.engine.sync_engine, "before_cursor_execute", _record)

    assert expanded == baseline
    assert expanded <= 8
    assert all(market_id for market_id in extra_ids)
```

- [ ] **Step 7: 运行新证据测试**

Run: `cd backend && uv run pytest tests/integration/test_p3_query_service.py -v`
Expected: PASS

- [ ] **Step 8: 全量确定性 + 焦点回归**

Run: `cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure and not player_alias_llm_live and not player_directory_e2e_live and not polymarket_live and not local_runtime_live" -q`
Expected: 全部通过（注册新测试文件后总数增加）

Run: `cd backend && uv run pytest -m infrastructure -q`
Expected: 全部通过

- [ ] **Step 9: ruff**

Run: `cd backend && uv run ruff check app/persistence/market_repositories.py app/markets/publisher.py app/service.py tests/test_market_overview_projection.py tests/integration/test_p3_query_service.py tests/realtime_fakes.py && uv run ruff format --check app/persistence/market_repositories.py app/markets/publisher.py app/service.py tests/test_market_overview_projection.py tests/integration/test_p3_query_service.py tests/realtime_fakes.py`
Expected: 无输出（干净）

- [ ] **Step 10: 确认没有其他读者依赖 `markets.match_id`**

Run: `cd /Users/daibin/Documents/Coding/TennixAI && git grep -n "\.match_id" -- backend/app | grep -i "market_row\|row\.match_id" | grep -v "service.py"`
Expected: 无业务读取路径（`save_market`/`get_market` 的写入与单市场读取保留）

- [ ] **Step 11: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add backend/app/service.py backend/tests/test_market_overview_projection.py \
        backend/tests/integration/test_p3_query_service.py
git commit -m "feat: load markets from active links without per-row reads"
```

### Task T84.3: T84 收口（总控 + 推送）

- [ ] **Step 1: 更新 `CURRENT.md`**

把「当前动作」改为完成记录，写入：T84 完成提交、实际运行的验证命令与结果（确定性套件计数、infrastructure 计数、新测试名），并把任务状态改为 `done`，`下一步` 指向 T85 领取。

- [ ] **Step 2: 更新 `ROADMAP.md`**

把 T84 行状态改为 `done`，`完成提交` 填两个实现提交，`验收证据` 填实际命令与数字（例如「`uv run pytest tests/test_market_overview_projection.py -v` N passed；integration M passed；SQL 语句计数证据 `expanded == baseline`；replaced link 不泄漏」）。T85 行保持 `planned`。

- [ ] **Step 3: 提交并推送**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add CURRENT.md ROADMAP.md
git commit -m "docs: close T84 active-link market projection"
git push origin main
```

---

# T85 — Read-Only Batch Quote Coverage

**交付物**：公开只读 CLOB `POST /books` 批量适配器；可逆 migration 与 durable latest-quote projection（每 market 最多一行）；canonical 两侧重组与七个可见状态；幂等 upsert 与 source precedence；raw batch 走既有 14 天 raw 表。

**不改变**：WebSocket 车道、decision/paper、API 形状（读侧接线在 T87）。

### Task T85.1: 可逆 migration 与投影模型

**Files:**
- Create: `backend/migrations/versions/20260922_0006_market_quote_snapshots.py`
- Modify: `backend/app/persistence/models.py`
- Test: `backend/tests/test_market_quote_snapshot.py`（新建）

**Interfaces:**
- Produces: `MarketQuoteSnapshotRow`（表 `market_quote_snapshots`）

- [ ] **Step 1: 先写失败测试（schema 元数据，无需数据库）**

新建 `backend/tests/test_market_quote_snapshot.py`：

```python
"""Latest-quote projection schema and canonical quote display tests (T85)."""

from app.persistence.models import Base, MarketQuoteSnapshotRow


def test_market_quote_snapshots_table_shape():
    table = Base.metadata.tables["market_quote_snapshots"]
    assert MarketQuoteSnapshotRow.__tablename__ == "market_quote_snapshots"
    assert [column.name for column in table.primary_key.columns] == ["market_id"]
    for name in (
        "source",
        "quote_state",
        "book_hash",
        "as_of",
        "expires_at",
        "payload",
        "updated_at",
    ):
        assert name in table.columns
    # Display statistics are stored explicitly so a missing side is a NULL
    # column, never a fabricated zero.
    for name in (
        "outcome_a_bid",
        "outcome_a_ask",
        "outcome_b_bid",
        "outcome_b_ask",
        "spread",
        "depth_usd",
    ):
        assert name in table.columns
        assert table.columns[name].nullable
    for name in ("as_of", "expires_at", "updated_at"):
        assert table.columns[name].type.timezone
    # Provider identity never enters the projection.
    for name in ("token", "condition_id", "provider_event_id"):
        assert all(name not in column.name for column in table.columns)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_market_quote_snapshot.py -v`
Expected: FAIL — `KeyError: 'market_quote_snapshots'`

- [ ] **Step 3: 新增 ORM 行**

在 `backend/app/persistence/models.py` 的 `MarketObservationRow` 之后（P3 市场区段内）加入：

```python
class MarketQuoteSnapshotRow(Base):
    """Durable latest-quote projection: at most one row per market (T85).

    A display read model for the coverage lane — NOT a market history store.
    It carries canonical two-outcome levels (internal player ids only) plus
    the display statistics the pages show. Provider tokens, condition ids,
    raw provider JSON, model probabilities, decisions and paper state never
    enter this table; the high-frequency material stays in the existing
    observation/raw tables under the 14-day retention.
    """

    __tablename__ = "market_quote_snapshots"

    market_id: Mapped[str] = mapped_column(
        ForeignKey("markets.id"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_state: Mapped[str] = mapped_column(String(16), nullable=False)
    book_hash: Mapped[str | None] = mapped_column(String(128))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    outcome_a_bid: Mapped[str | None] = mapped_column(String(32))
    outcome_a_ask: Mapped[str | None] = mapped_column(String(32))
    outcome_b_bid: Mapped[str | None] = mapped_column(String(32))
    outcome_b_ask: Mapped[str | None] = mapped_column(String(32))
    spread: Mapped[str | None] = mapped_column(String(32))
    depth_usd: Mapped[str | None] = mapped_column(String(32))
    payload: Mapped[dict | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 4: 新增可逆 migration**

新建 `backend/migrations/versions/20260922_0006_market_quote_snapshots.py`：

```python
"""Add the durable latest-quote projection.

Creates only `market_quote_snapshots` (one row per market) for the P4.3
coverage lane: canonical two-outcome levels plus display statistics with an
explicit state, source and timestamp. It stores no provider identity, raw
payload, model or paper state. Downgrade drops only this table; every
P2/P3 table is untouched.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "market_quote_snapshots",
        sa.Column("market_id", sa.String(length=64), primary_key=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("quote_state", sa.String(length=16), nullable=False),
        sa.Column("book_hash", sa.String(length=128), nullable=True),
        sa.Column("as_of", TZ, nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("outcome_a_bid", sa.String(length=32), nullable=True),
        sa.Column("outcome_a_ask", sa.String(length=32), nullable=True),
        sa.Column("outcome_b_bid", sa.String(length=32), nullable=True),
        sa.Column("outcome_b_ask", sa.String(length=32), nullable=True),
        sa.Column("spread", sa.String(length=32), nullable=True),
        sa.Column("depth_usd", sa.String(length=32), nullable=True),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("updated_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
    )


def downgrade() -> None:
    op.drop_table("market_quote_snapshots")
```

- [ ] **Step 5: 运行 schema 测试与 migration 往返**

Run: `cd backend && uv run pytest tests/test_market_quote_snapshot.py -v`
Expected: PASS

Run: `cd backend && uv run alembic upgrade head && uv run alembic downgrade 0005 && uv run alembic upgrade head && echo "ROUNDTRIP OK"`
Expected: 三次命令 exit 0；`ROUNDTRIP OK`。**只对 `tennix`/`tennix_live_local` 这两个本地回环库执行；不得触碰任何其他库。**

- [ ] **Step 6: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add backend/migrations/versions/20260922_0006_market_quote_snapshots.py \
        backend/app/persistence/models.py backend/tests/test_market_quote_snapshot.py
git commit -m "feat: add the durable latest-quote projection schema"
```

### Task T85.2: canonical 报价模块（状态机 + precedence + 展示统计）

**Files:**
- Create: `backend/app/markets/quotes.py`
- Modify: `backend/app/service.py`（`_best_levels`/`_outcome_levels` 委托到共享实现）
- Test: `backend/tests/test_market_quote_snapshot.py`（追加）

**Interfaces:**
- Produces: `QuoteState`、`QuoteSource`、`DisplayQuote`、`QuoteSnapshotRecord`、`TokenBook`、`ClobBooksBatch`、`best_levels`、`outcome_levels`、`classify_batch_quote`、`build_quote_snapshot`、`decide_quote_write`、`display_quote`

- [ ] **Step 1: 先写失败测试（七个状态、precedence 真值表、缺失字段不掩盖真实报价）**

在 `backend/tests/test_market_quote_snapshot.py` 追加：

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.markets.models import BookLevel, OrderBookState, OutcomeBook
from app.markets.quotes import (
    ClobBooksBatch,
    QuoteSnapshotRecord,
    QuoteSource,
    QuoteState,
    TokenBook,
    build_quote_snapshot,
    decide_quote_write,
    display_quote,
)

NOW = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)


def outcome_book(player_id: str, *, bid: str | None, ask: str | None) -> OutcomeBook:
    return OutcomeBook(
        outcome_player_id=player_id,
        bids=(BookLevel(price=Decimal(bid), size=Decimal("100")),) if bid else (),
        asks=(BookLevel(price=Decimal(ask), size=Decimal("100")),) if ask else (),
    )


def hot_book(
    *, a: tuple[str | None, str | None], b: tuple[str | None, str | None],
    received_at: datetime = NOW, is_stale: bool = False,
) -> OrderBookState:
    return OrderBookState(
        market_id="mkt_1",
        books=(outcome_book("ply_a", bid=a[0], ask=a[1]), outcome_book("ply_b", bid=b[0], ask=b[1])),
        sequence=5,
        book_hash="ws_hash",
        provider_timestamp=received_at,
        received_at=received_at,
        is_stale=is_stale,
    )


def snapshot_record(
    *,
    state: QuoteState = QuoteState.SNAPSHOT,
    source: QuoteSource = QuoteSource.SNAPSHOT,
    as_of: datetime = NOW,
    book_hash: str | None = "snap_hash",
) -> QuoteSnapshotRecord:
    return QuoteSnapshotRecord(
        market_id="mkt_1",
        source=source,
        state=state,
        book_hash=book_hash,
        as_of=as_of,
        expires_at=as_of + timedelta(seconds=300),
        outcome_bids=("0.58", "0.40"),
        outcome_asks=("0.60", "0.42"),
        best_bid=("ply_a", "0.58"),
        best_ask=("ply_a", "0.60"),
        spread="0.0200",
        depth_usd="306.00",
    )


def test_display_quote_prefers_a_fresh_realtime_book():
    quote = display_quote(
        hot_book=hot_book(a=("0.61", "0.63"), b=("0.37", "0.39")),
        snapshot=snapshot_record(),
        now=NOW + timedelta(seconds=2),
        realtime_fresh_seconds=5,
        snapshot_fresh_seconds=300,
    )
    assert quote.state is QuoteState.REALTIME
    assert quote.source is QuoteSource.REALTIME
    assert quote.outcome_asks == ("0.63", "0.39")
    assert quote.as_of == NOW


def test_display_quote_falls_back_to_the_snapshot_when_hot_state_is_old():
    quote = display_quote(
        hot_book=hot_book(a=("0.61", "0.63"), b=("0.37", "0.39")),
        snapshot=snapshot_record(),
        now=NOW + timedelta(seconds=30),
        realtime_fresh_seconds=5,
        snapshot_fresh_seconds=300,
    )
    assert quote.state is QuoteState.SNAPSHOT
    assert quote.source is QuoteSource.SNAPSHOT
    assert quote.outcome_asks == ("0.60", "0.42")


def test_display_quote_marks_an_expired_snapshot_stale_and_keeps_last_trusted_levels():
    quote = display_quote(
        hot_book=None,
        snapshot=snapshot_record(),
        now=NOW + timedelta(seconds=301),
        realtime_fresh_seconds=5,
        snapshot_fresh_seconds=300,
    )
    assert quote.state is QuoteState.STALE
    assert quote.as_of == NOW
    assert quote.outcome_bids == ("0.58", "0.40")


def test_display_quote_without_any_source_is_unavailable_not_zero():
    quote = display_quote(
        hot_book=None, snapshot=None, now=NOW,
        realtime_fresh_seconds=5, snapshot_fresh_seconds=300,
    )
    assert quote.state is QuoteState.UNAVAILABLE
    assert quote.source is None and quote.as_of is None
    assert quote.outcome_bids == (None, None)
    assert quote.best_bid is None and quote.depth_usd is None


def test_display_quote_reports_one_sided_books_as_partial():
    quote = display_quote(
        hot_book=None,
        snapshot=snapshot_record(state=QuoteState.PARTIAL),
        now=NOW,
        realtime_fresh_seconds=5,
        snapshot_fresh_seconds=300,
    )
    assert quote.state is QuoteState.PARTIAL
    # One outcome's real ask never hides the other outcome's missing ask.
    assert quote.outcome_asks == ("0.60", "0.42")


def test_display_quote_keeps_limited_state_with_the_last_trusted_time():
    quote = display_quote(
        hot_book=None,
        snapshot=snapshot_record(state=QuoteState.LIMITED),
        now=NOW + timedelta(seconds=10),
        realtime_fresh_seconds=5,
        snapshot_fresh_seconds=300,
    )
    assert quote.state is QuoteState.LIMITED
    assert quote.as_of == NOW
    assert quote.outcome_asks == ("0.60", "0.42")


def test_build_quote_snapshot_classifies_both_sides_partial_and_empty():
    tokens = ("tok_a", "tok_b")
    players = ("ply_a", "ply_b")
    both = ClobBooksBatch(
        books={
            "tok_a": TokenBook(token_id="tok_a", bids=(BookLevel(price=Decimal("0.58"), size=Decimal("10")),), asks=(BookLevel(price=Decimal("0.60"), size=Decimal("10")),), book_hash="ha", provider_timestamp=NOW),
            "tok_b": TokenBook(token_id="tok_b", bids=(BookLevel(price=Decimal("0.40"), size=Decimal("10")),), asks=(BookLevel(price=Decimal("0.42"), size=Decimal("10")),), book_hash="hb", provider_timestamp=NOW),
        },
        missing_tokens=(), malformed_tokens=(), raw=(),
    )
    record = build_quote_snapshot(
        market_id="mkt_1", token_ids=tokens, player_ids=players, batch=both,
        observed_at=NOW, expires_at=NOW + timedelta(seconds=300),
    )
    assert record.state is QuoteState.SNAPSHOT
    assert record.outcome_asks == ("0.60", "0.42")
    assert record.best_bid == ("ply_a", "0.58")
    assert record.book_hash is not None and len(record.book_hash) == 64
    assert len(record.levels or ()) == 2

    one_sided = ClobBooksBatch(
        books={
            "tok_a": TokenBook(token_id="tok_a", bids=(), asks=(BookLevel(price=Decimal("0.60"), size=Decimal("10")),), book_hash="ha", provider_timestamp=NOW),
            "tok_b": TokenBook(token_id="tok_b", bids=(), asks=(), book_hash="hb", provider_timestamp=NOW),
        },
        missing_tokens=(), malformed_tokens=(), raw=(),
    )
    partial = build_quote_snapshot(
        market_id="mkt_1", token_ids=tokens, player_ids=players, batch=one_sided,
        observed_at=NOW, expires_at=NOW + timedelta(seconds=300),
    )
    assert partial.state is QuoteState.PARTIAL
    assert partial.outcome_asks == ("0.60", None)

    empty = ClobBooksBatch(
        books={
            "tok_a": TokenBook(token_id="tok_a", bids=(), asks=(), book_hash="ha", provider_timestamp=NOW),
            "tok_b": TokenBook(token_id="tok_b", bids=(), asks=(), book_hash="hb", provider_timestamp=NOW),
        },
        missing_tokens=(), malformed_tokens=(), raw=(),
    )
    none_state = build_quote_snapshot(
        market_id="mkt_1", token_ids=tokens, player_ids=players, batch=empty,
        observed_at=NOW, expires_at=NOW + timedelta(seconds=300),
    )
    assert none_state.state is QuoteState.NO_LIQUIDITY
    assert none_state.outcome_asks == (None, None)

    unavailable = build_quote_snapshot(
        market_id="mkt_1", token_ids=tokens, player_ids=players,
        batch=ClobBooksBatch(books={}, missing_tokens=tokens, malformed_tokens=(), raw=()),
        observed_at=NOW, expires_at=NOW + timedelta(seconds=300),
    )
    assert unavailable.state is QuoteState.UNAVAILABLE
    assert unavailable.levels is None


def test_decide_quote_write_precedence_truth_table():
    current = snapshot_record(as_of=NOW)
    assert decide_quote_write(None, current) is True
    # Older never overwrites newer.
    older = snapshot_record(as_of=NOW - timedelta(seconds=1), book_hash="other")
    assert decide_quote_write(current, older) is False
    # Byte-identical rerun is idempotent.
    assert decide_quote_write(current, snapshot_record(as_of=NOW)) is False
    # Same instant: the realtime lane may take over, the snapshot lane may not.
    ws = snapshot_record(source=QuoteSource.REALTIME, state=QuoteState.REALTIME, as_of=NOW, book_hash="ws")
    assert decide_quote_write(current, ws) is True
    assert decide_quote_write(ws, snapshot_record(as_of=NOW, book_hash="newer_snapshot")) is False
    # Newer always wins.
    assert decide_quote_write(current, snapshot_record(as_of=NOW + timedelta(seconds=1), book_hash="next")) is True
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_market_quote_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.markets.quotes'`

- [ ] **Step 3: 实现 `app/markets/quotes.py`**

新建文件：

```python
"""Canonical display quotes and the durable latest-quote projection (T85).

Two lanes feed one display contract: the realtime lane (strictly mapped,
in-demand markets) supplies a Redis hot book refreshed by the public market
WebSocket; the coverage lane supplies a bounded batch snapshot of every
canonical market. `display_quote` is the single implementation of the seven
visible quote states from the design spec §5.3 — a bare `—` is only ever a
single missing field, never a state, and one outcome's missing side never
hides the other outcome's real quote.

Only internal IDs, decimal level text and timestamps live here. Provider
tokens, condition ids and raw payloads never enter these models.
"""

import hashlib
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from pydantic import AwareDatetime, Field

from app.domain import FrozenModel
from app.markets.models import BookLevel, OrderBookState, OutcomeBook

SPREAD_TEXT = Decimal("0.0001")
DEPTH_TEXT = Decimal("0.01")


class QuoteState(StrEnum):
    REALTIME = "realtime"
    SNAPSHOT = "snapshot"
    PARTIAL = "partial"
    NO_LIQUIDITY = "no_liquidity"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    LIMITED = "limited"


class QuoteSource(StrEnum):
    REALTIME = "realtime"
    SNAPSHOT = "snapshot"


class TokenBook(FrozenModel):
    """PRIVATE per-token book from the batch adapter. Never a public DTO."""

    token_id: str = Field(min_length=1)
    bids: tuple[BookLevel, ...] = ()
    asks: tuple[BookLevel, ...] = ()
    book_hash: str = ""
    provider_timestamp: AwareDatetime | None = None


class ClobBooksBatch(FrozenModel):
    """PRIVATE batch result: parsed per-token books plus the raw response."""

    books: Mapping[str, TokenBook] = {}
    missing_tokens: tuple[str, ...] = ()
    malformed_tokens: tuple[str, ...] = ()
    raw: tuple[dict, ...] = ()


class DisplayQuote(FrozenModel):
    """What the pages may show for one market. `as_of` is always the source
    timestamp of the levels that accompany it."""

    state: QuoteState
    source: QuoteSource | None = None
    as_of: AwareDatetime | None = None
    outcome_bids: tuple[str | None, str | None] = (None, None)
    outcome_asks: tuple[str | None, str | None] = (None, None)
    best_bid: tuple[str, str] | None = None
    best_ask: tuple[str, str] | None = None
    spread: str | None = None
    depth_usd: str | None = None


class QuoteSnapshotRecord(FrozenModel):
    """One durable latest-quote row (internal IDs only)."""

    market_id: str = Field(min_length=1)
    source: QuoteSource
    state: QuoteState
    book_hash: str | None = None
    as_of: AwareDatetime
    expires_at: AwareDatetime
    levels: tuple[OutcomeBook, OutcomeBook] | None = None
    outcome_bids: tuple[str | None, str | None] = (None, None)
    outcome_asks: tuple[str | None, str | None] = (None, None)
    best_bid: tuple[str, str] | None = None
    best_ask: tuple[str, str] | None = None
    spread: str | None = None
    depth_usd: str | None = None


_SOURCE_RANK = {QuoteSource.SNAPSHOT: 1, QuoteSource.REALTIME: 2}


def best_levels(book, outcome_player_id: str | None):
    """(best_bid, best_ask) as (player_id, price text) or None."""
    if book is None:
        return None, None
    side = None
    for candidate in book.books:
        if outcome_player_id is None or candidate.outcome_player_id == outcome_player_id:
            side = candidate
            break
    if side is None:
        return None, None
    best_bid = (side.outcome_player_id, str(side.bids[0].price)) if side.bids else None
    best_ask = (side.outcome_player_id, str(side.asks[0].price)) if side.asks else None
    return best_bid, best_ask


def outcome_levels(book, outcome_ids):
    """Per-outcome top levels aligned to outcome_ids, plus mean spread and
    top-of-book notional depth. Missing sides stay None."""
    if book is None:
        return None, None, None, None
    by_player = {side.outcome_player_id: side for side in book.books}
    bids: list[str | None] = []
    asks: list[str | None] = []
    spreads: list = []
    depth = Decimal("0")
    for player_id in outcome_ids:
        side = by_player.get(player_id) if player_id else None
        if side is None:
            bids.append(None)
            asks.append(None)
            continue
        bid = str(side.bids[0].price) if side.bids else None
        ask = str(side.asks[0].price) if side.asks else None
        bids.append(bid)
        asks.append(ask)
        if side.bids:
            depth += side.bids[0].price * side.bids[0].size
        if side.asks:
            depth += side.asks[0].price * side.asks[0].size
        if bid is not None and ask is not None:
            spreads.append(Decimal(ask) - Decimal(bid))
    spread = (
        (sum(spreads) / Decimal(len(spreads))).quantize(SPREAD_TEXT) if spreads else None
    )
    return (
        (bids[0], bids[1]) if len(bids) == 2 else None,
        (asks[0], asks[1]) if len(asks) == 2 else None,
        spread,
        depth.quantize(DEPTH_TEXT) if (spreads or depth) else None,
    )


def _state_for_books(books: Sequence[OutcomeBook]) -> QuoteState:
    if all(side.bids or side.asks for side in books):
        return QuoteState.SNAPSHOT
    if any(side.bids or side.asks for side in books):
        return QuoteState.PARTIAL
    return QuoteState.NO_LIQUIDITY


def _is_fresh(stamp: datetime, now: datetime, bound_seconds: int) -> bool:
    return now - stamp <= timedelta(seconds=bound_seconds)


def display_quote(
    *,
    hot_book: OrderBookState | None,
    snapshot: QuoteSnapshotRecord | None,
    now: datetime,
    realtime_fresh_seconds: int,
    snapshot_fresh_seconds: int,
) -> DisplayQuote:
    """Single source of truth for the visible quote state (spec §5.3).

    A fresh WebSocket book always wins; otherwise the durable snapshot is
    shown with its own state, upgraded to `stale` once it outlives the
    configured freshness bound. Nothing is ever fabricated: with neither
    source the state is `unavailable`, not a zero quote.
    """
    if (
        hot_book is not None
        and not hot_book.is_stale
        and _is_fresh(hot_book.received_at, now, realtime_fresh_seconds)
    ):
        state = _state_for_books(hot_book.books)
        bids, asks, spread, depth = outcome_levels(
            hot_book, [side.outcome_player_id for side in hot_book.books]
        )
        best_bid, best_ask = best_levels(hot_book, hot_book.books[0].outcome_player_id)
        return DisplayQuote(
            state=state,
            source=QuoteSource.REALTIME,
            as_of=hot_book.received_at,
            outcome_bids=bids or (None, None),
            outcome_asks=asks or (None, None),
            best_bid=best_bid,
            best_ask=best_ask,
            spread=str(spread) if spread is not None else None,
            depth_usd=str(depth) if depth is not None else None,
        )
    if snapshot is None:
        return DisplayQuote(state=QuoteState.UNAVAILABLE)
    state = (
        snapshot.state
        if _is_fresh(snapshot.as_of, now, snapshot_fresh_seconds)
        else QuoteState.STALE
    )
    return DisplayQuote(
        state=state,
        source=snapshot.source,
        as_of=snapshot.as_of,
        outcome_bids=snapshot.outcome_bids,
        outcome_asks=snapshot.outcome_asks,
        best_bid=snapshot.best_bid,
        best_ask=snapshot.best_ask,
        spread=snapshot.spread,
        depth_usd=snapshot.depth_usd,
    )


def build_quote_snapshot(
    *,
    market_id: str,
    token_ids: tuple[str, str],
    player_ids: tuple[str, str],
    batch: ClobBooksBatch,
    observed_at: datetime,
    expires_at: datetime,
) -> QuoteSnapshotRecord:
    """Canonical two-outcome projection from a private token batch.

    Exactly one token may be absent or malformed without discarding the
    other side: the state becomes `partial` (with the parsed side's real
    levels) when that side has any level, `unavailable` when it does not.
    """
    parsed = [batch.books.get(token_id) for token_id in token_ids]
    books = tuple(
        OutcomeBook(
            outcome_player_id=player_id,
            bids=token_book.bids if token_book is not None else (),
            asks=token_book.asks if token_book is not None else (),
        )
        for token_book, player_id in zip(parsed, player_ids, strict=True)
    )
    hashes = [token_book.book_hash for token_book in parsed if token_book is not None]
    book_hash = (
        hashlib.sha256(":".join(hashes).encode("utf-8")).hexdigest() if hashes else None
    )
    present = sum(1 for token_book in parsed if token_book is not None)
    if present == 2:
        state = _state_for_books(books)
    elif present == 1:
        state = QuoteState.PARTIAL if any(side.bids or side.asks for side in books) else QuoteState.UNAVAILABLE
    else:
        state = QuoteState.UNAVAILABLE
    if state is QuoteState.UNAVAILABLE:
        return QuoteSnapshotRecord(
            market_id=market_id,
            source=QuoteSource.SNAPSHOT,
            state=state,
            book_hash=book_hash,
            as_of=observed_at,
            expires_at=expires_at,
        )
    book_state = OrderBookState(
        market_id=market_id,
        books=books,
        sequence=0,
        book_hash=book_hash or "batch",
        provider_timestamp=observed_at,
        received_at=observed_at,
    )
    bids, asks, spread, depth = outcome_levels(book_state, player_ids)
    best_bid, best_ask = best_levels(book_state, player_ids[0])
    return QuoteSnapshotRecord(
        market_id=market_id,
        source=QuoteSource.SNAPSHOT,
        state=state,
        book_hash=book_hash,
        as_of=observed_at,
        expires_at=expires_at,
        levels=(books[0], books[1]),
        outcome_bids=bids or (None, None),
        outcome_asks=asks or (None, None),
        best_bid=best_bid,
        best_ask=best_ask,
        spread=str(spread) if spread is not None else None,
        depth_usd=str(depth) if depth is not None else None,
    )


def decide_quote_write(
    existing: QuoteSnapshotRecord | None, incoming: QuoteSnapshotRecord
) -> bool:
    """Precedence rule for the shared projection (spec §5.2).

    Only newer content may replace stored content; at the same instant the
    realtime lane may take over the snapshot lane but never the reverse, and
    a byte-identical rerun writes nothing (idempotent).
    """
    if existing is None:
        return True
    if incoming.as_of < existing.as_of:
        return False
    if incoming.as_of == existing.as_of:
        if (
            incoming.book_hash == existing.book_hash
            and incoming.state is existing.state
            and incoming.source is existing.source
        ):
            return False
        return _SOURCE_RANK[incoming.source] >= _SOURCE_RANK[existing.source]
    return True
```

> 注：`build_quote_snapshot` 中 `zip(parsed, player_ids, strict=True)` 的顺序即 token→player 顺序，行为与测试断言一致。

- [ ] **Step 4: 让 `P3QueryService` 复用共享实现（DRY）**

在 `backend/app/service.py` 顶部 import 区加入 `from app.markets.quotes import best_levels, outcome_levels`，把 `P3QueryService._best_levels` 与 `_outcome_levels` 的两个静态方法体替换为委托：

```python
    @staticmethod
    def _best_levels(book, outcome_player_id: str | None):
        """(best_bid, best_ask) as (player_id, price text) or None."""
        return best_levels(book, outcome_player_id)

    @staticmethod
    def _outcome_levels(book, outcome_ids):
        """Per-outcome top levels aligned to outcome_ids, plus mean spread
        and top-of-book notional depth. Missing sides stay None."""
        return outcome_levels(book, outcome_ids)
```

- [ ] **Step 5: 运行测试确认通过（含既有回归）**

Run: `cd backend && uv run pytest tests/test_market_quote_snapshot.py -v`
Expected: PASS

Run: `cd backend && uv run pytest tests/test_market_overview_projection.py tests/test_market_stream_api.py tests/test_p3_api.py -v`
Expected: PASS（抽取共享实现不得改变既有格式）

- [ ] **Step 6: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add backend/app/markets/quotes.py backend/app/service.py backend/tests/test_market_quote_snapshot.py
git commit -m "feat: add canonical quote states and write precedence"
```

### Task T85.3: 公开只读 CLOB 批量 `POST /books` 适配器

**Files:**
- Modify: `backend/app/markets/polymarket.py`
- Test: `backend/tests/test_polymarket_batch_books.py`（新建）

**Interfaces:**
- Consumes: `app.markets.quotes.TokenBook`、`ClobBooksBatch`、既有 `BookDto`、`_canonical_levels`、`_raise_for_status`
- Produces: `PolymarketProvider.get_order_books(token_ids: Sequence[str]) -> ClobBooksBatch`

- [ ] **Step 1: 先写失败测试（httpx MockTransport，零真实网络）**

新建 `backend/tests/test_polymarket_batch_books.py`：

```python
"""CLOB batch `POST /books` adapter tests (T85). No real network calls."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from app.errors import AppError
from app.markets.polymarket import PolymarketProvider

NOW = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)
TOKEN_A = "111111111111111111111"
TOKEN_B = "222222222222222222222"


def provider(handler) -> PolymarketProvider:
    transport = httpx.MockTransport(handler)
    return PolymarketProvider(
        gamma_base_url="https://gamma.test",
        clob_base_url="https://clob.test",
        resolver=None,  # batch reads never resolve players
        transport=transport,
        now_fn=lambda: NOW,
    )


def book_payload(token: str, *, bids=None, asks=None, digest="h1") -> dict:
    return {
        "market": "0xcondition",
        "asset_id": token,
        "timestamp": "1758528000000",
        "hash": digest,
        "bids": bids if bids is not None else [{"price": "0.44", "size": "12"}],
        "asks": asks if asks is not None else [{"price": "0.56", "size": "10"}],
    }


async def test_batch_books_posts_every_token_once_in_order():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json=[
                book_payload(TOKEN_B, digest="hb"),
                book_payload(TOKEN_A, digest="ha"),
            ],
        )

    client = provider(handler)
    try:
        batch = await client.get_order_books([TOKEN_A, TOKEN_B, TOKEN_A])
    finally:
        await client.aclose()

    assert seen["method"] == "POST" and seen["path"] == "/books"
    assert seen["body"] == [{"token_id": TOKEN_A}, {"token_id": TOKEN_B}]
    assert seen["auth"] is None  # public read-only endpoint, no credentials
    assert set(batch.books) == {TOKEN_A, TOKEN_B}
    # Response order is never assumed: books are keyed by asset_id.
    assert batch.books[TOKEN_A].bids[0].price == Decimal("0.44")
    assert batch.books[TOKEN_A].book_hash == "ha"
    assert batch.missing_tokens == () and batch.malformed_tokens == ()
    assert len(batch.raw) == 2


async def test_batch_books_isolates_a_malformed_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                book_payload(TOKEN_A),
                {"asset_id": TOKEN_B, "bids": [{"price": "0.5", "size": "1"}, {"price": "0.5", "size": "2"}], "asks": []},
            ],
        )

    client = provider(handler)
    try:
        batch = await client.get_order_books([TOKEN_A, TOKEN_B])
    finally:
        await client.aclose()

    assert set(batch.books) == {TOKEN_A}
    assert batch.malformed_tokens == (TOKEN_B,)
    assert batch.missing_tokens == ()


async def test_batch_books_reports_missing_tokens_without_fabricating_them():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[book_payload(TOKEN_A)])

    client = provider(handler)
    try:
        batch = await client.get_order_books([TOKEN_A, TOKEN_B])
    finally:
        await client.aclose()

    assert set(batch.books) == {TOKEN_A}
    assert batch.missing_tokens == (TOKEN_B,)


async def test_batch_books_translates_429_with_retry_after():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "7"}, json={})

    client = provider(handler)
    try:
        with pytest.raises(AppError) as excinfo:
            await client.get_order_books([TOKEN_A])
    finally:
        await client.aclose()
    assert excinfo.value.code == "rate_limited"
    assert excinfo.value.details["retry_after"] == "7"


async def test_batch_books_rejects_a_non_list_payload():
    client = provider(lambda request: httpx.Response(200, json={"error": "nope"}))
    try:
        with pytest.raises(AppError) as excinfo:
            await client.get_order_books([TOKEN_A])
    finally:
        await client.aclose()
    assert excinfo.value.code == "provider_invalid_response"


async def test_batch_books_with_no_tokens_never_calls_the_provider():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request expected")

    client = provider(handler)
    try:
        batch = await client.get_order_books([])
    finally:
        await client.aclose()
    assert batch.books == {} and batch.raw == ()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/test_polymarket_batch_books.py -v`
Expected: FAIL — `AttributeError: 'PolymarketProvider' object has no attribute 'get_order_books'`

- [ ] **Step 3: 实现适配器方法**

在 `backend/app/markets/polymarket.py` 的 `get_order_book` 之前插入（并在顶部 import 区加入 `from collections.abc import AsyncIterator, Callable, Sequence` 与 `from app.markets.quotes import ClobBooksBatch, TokenBook`）：

```python
    async def get_order_books(self, token_ids: Sequence[str]) -> ClobBooksBatch:
        """Batch `POST /books` for the coverage lane (T85).

        One public, credential-free, read-only request per batch. Tokens are
        de-duplicated in first-seen order; a token that is missing from the
        response or whose levels cannot be parsed is reported instead of
        fabricated, and never affects the other tokens in the batch. The raw
        response is returned for the 14-day raw store only and must never
        reach a public DTO, log or page.
        """
        requested = tuple(dict.fromkeys(token for token in token_ids if token))
        if not requested:
            return ClobBooksBatch()
        try:
            response = await self._clob.post(
                "/books", json=[{"token_id": token} for token in requested]
            )
        except httpx.HTTPError as exc:
            raise AppError(
                "provider_unavailable", "Polymarket request failed", 503
            ) from exc
        self._raise_for_status(response)
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise AppError(
                "provider_invalid_response",
                "Polymarket response was not valid JSON",
                502,
            ) from exc
        if not isinstance(payload, list):
            raise AppError(
                "provider_invalid_response",
                "Polymarket books payload was malformed",
                502,
            )
        books: dict[str, TokenBook] = {}
        malformed: list[str] = []
        requested_set = set(requested)
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                dto = BookDto.model_validate(item)
            except ValidationError:
                if item.get("asset_id") in requested_set:
                    malformed.append(str(item["asset_id"]))
                continue
            token_id = dto.asset_id or ""
            if token_id not in requested_set:
                continue
            try:
                bids = self._canonical_levels(dto.bids, descending=True)
                asks = self._canonical_levels(dto.asks, descending=False)
            except AppError:
                # Per-token isolation: a malformed book affects only its own
                # market; the rest of the batch still lands.
                malformed.append(token_id)
                continue
            books[token_id] = TokenBook(
                token_id=token_id,
                bids=bids,
                asks=asks,
                book_hash=dto.hash or "",
                provider_timestamp=self._epoch_millis(dto.timestamp),
            )
        missing = tuple(
            token
            for token in requested
            if token not in books and token not in set(malformed)
        )
        return ClobBooksBatch(
            books=books,
            missing_tokens=missing,
            malformed_tokens=tuple(malformed),
            raw=tuple(payload),
        )

    def _epoch_millis(self, value: str | int | None) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(int(str(value)) / 1000, tz=UTC)
        except (ValueError, OSError, OverflowError):
            return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_polymarket_batch_books.py tests/test_polymarket_provider.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add backend/app/markets/polymarket.py backend/tests/test_polymarket_batch_books.py
git commit -m "feat: read batch order books from the public CLOB"
```

### Task T85.4: durable 投影写入（幂等 upsert、raw batch 保留）与 integration 证据

**Files:**
- Modify: `backend/app/persistence/market_repositories.py`（新增 `MarketQuoteSnapshotRepository`）
- Create: `backend/app/markets/quote_snapshot.py`
- Test: `backend/tests/integration/test_market_quote_persistence.py`（新建）

**Interfaces:**
- Consumes: `QuoteSnapshotRecord`、`decide_quote_write`、`ClobBooksBatch`、`RawProviderEventRepository`
- Produces: `MarketQuoteSnapshotRepository.upsert/load/load_many/mark_state`；`record_raw_batch(raw_repo, *, observed_at, batch, batch_index)`

- [ ] **Step 1: 先写失败测试（真实 PostgreSQL）**

新建 `backend/tests/integration/test_market_quote_persistence.py`：

```python
"""Latest-quote projection against real PostgreSQL (T85).

Proves idempotent upsert, source precedence, reversible migration ownership,
raw batch retention/purge and that the projection carries no provider
identity. Requires compose PostgreSQL + `uv run alembic upgrade head`.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.config import Settings
from app.markets.models import BookLevel
from app.markets.quote_snapshot import record_raw_batch
from app.markets.quotes import (
    ClobBooksBatch,
    QuoteSnapshotRecord,
    QuoteSource,
    QuoteState,
    TokenBook,
    build_quote_snapshot,
)
from app.persistence.database import Database
from app.persistence.market_repositories import (
    MarketQuoteSnapshotRepository,
    MarketRepository,
)
from app.persistence.repositories import RawProviderEventRepository
from p3_fakes import make_market

pytestmark = pytest.mark.infrastructure

NOW = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)


@pytest.fixture()
async def database():
    settings = Settings(_env_file=None)
    db = Database(settings.database_url)
    try:
        async with db.engine.connect() as connection:
            mapped = (
                await connection.execute(
                    text("SELECT to_regclass('public.market_quote_snapshots')")
                )
            ).scalar()
    except Exception as exc:  # pragma: no cover - environment dependent
        await db.dispose()
        pytest.skip(f"PostgreSQL not reachable ({type(exc).__name__})")
    if mapped is None:
        await db.dispose()
        pytest.skip("quote schema not migrated; run `uv run alembic upgrade head`")
    try:
        yield db
    finally:
        await db.dispose()


async def _market(database: Database) -> str:
    markets = MarketRepository(database)
    market_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev85_{uuid4().hex[:10]}",
        condition_id=f"cond85_{uuid4().hex}",
    )
    await markets.save_market(make_market(market_id, match_id=None))
    return market_id


def _record(market_id: str, *, as_of: datetime, digest: str, source: QuoteSource = QuoteSource.SNAPSHOT) -> QuoteSnapshotRecord:
    return QuoteSnapshotRecord(
        market_id=market_id,
        source=source,
        state=QuoteState.SNAPSHOT,
        book_hash=digest,
        as_of=as_of,
        expires_at=as_of + timedelta(seconds=300),
        outcome_bids=("0.58", "0.40"),
        outcome_asks=("0.60", "0.42"),
        best_bid=("ply_a", "0.58"),
        best_ask=("ply_a", "0.60"),
        spread="0.0200",
        depth_usd="306.00",
    )


async def test_quote_upsert_is_idempotent_and_precedence_ordered(database: Database) -> None:
    market_id = await _market(database)
    repo = MarketQuoteSnapshotRepository(database)

    assert await repo.upsert(_record(market_id, as_of=NOW, digest="h1")) is True
    # Identical rerun writes nothing.
    assert await repo.upsert(_record(market_id, as_of=NOW, digest="h1")) is False
    # An older quote never overwrites a newer one.
    assert (
        await repo.upsert(
            _record(market_id, as_of=NOW - timedelta(seconds=5), digest="h0")
        )
        is False
    )
    stored = await repo.load(market_id)
    assert stored is not None and stored.book_hash == "h1"

    # The realtime lane may take over at the same instant.
    assert (
        await repo.upsert(
            _record(market_id, as_of=NOW, digest="ws", source=QuoteSource.REALTIME)
        )
        is True
    )
    stored = await repo.load(market_id)
    assert stored is not None and stored.source is QuoteSource.REALTIME

    # A newer snapshot wins over an older realtime value.
    assert (
        await repo.upsert(
            _record(market_id, as_of=NOW + timedelta(seconds=1), digest="h2")
        )
        is True
    )
    stored = await repo.load(market_id)
    assert stored is not None and stored.book_hash == "h2"

    async with database.session() as session:
        count = await session.scalar(
            text("SELECT count(*) FROM market_quote_snapshots WHERE market_id = :m"),
            {"m": market_id},
        )
    assert int(count) == 1


async def test_quote_projection_stores_no_provider_identity(database: Database) -> None:
    market_id = await _market(database)
    repo = MarketQuoteSnapshotRepository(database)
    await repo.upsert(_record(market_id, as_of=NOW, digest="h1"))
    stored = await repo.load(market_id)
    blob = stored.model_dump_json().lower()
    for fragment in ("token", "condition", "0x", "wallet", "private"):
        assert fragment not in blob


async def test_raw_batch_is_written_once_per_batch_and_purged_by_age(
    database: Database,
) -> None:
    raw = RawProviderEventRepository(database)
    market_id = await _market(database)
    batch = ClobBooksBatch(
        books={
            "tok_a": TokenBook(
                token_id="tok_a",
                bids=(BookLevel(price=Decimal("0.58"), size=Decimal("10")),),
                asks=(BookLevel(price=Decimal("0.60"), size=Decimal("10")),),
                book_hash="ha",
                provider_timestamp=NOW,
            )
        },
        missing_tokens=("tok_b",),
        malformed_tokens=(),
        raw=({"asset_id": "tok_a", "hash": "ha"},),
    )
    await record_raw_batch(raw, observed_at=NOW, batch=batch, batch_index=0)

    rows = await raw.read_for_match(market_id, limit=5) if market_id else []
    assert rows == []  # raw batches are keyed by provider/channel, not by match
    purged = await raw.purge_raw_events(NOW + timedelta(days=14))
    assert purged >= 1


async def test_canonical_batch_projection_round_trips_through_postgres(
    database: Database,
) -> None:
    market_id = await _market(database)
    repo = MarketQuoteSnapshotRepository(database)
    batch = ClobBooksBatch(
        books={
            "tok_a": TokenBook(
                token_id="tok_a",
                bids=(BookLevel(price=Decimal("0.58"), size=Decimal("10")),),
                asks=(BookLevel(price=Decimal("0.60"), size=Decimal("10")),),
                book_hash="ha",
                provider_timestamp=NOW,
            ),
            "tok_b": TokenBook(
                token_id="tok_b",
                bids=(BookLevel(price=Decimal("0.40"), size=Decimal("10")),),
                asks=(BookLevel(price=Decimal("0.42"), size=Decimal("10")),),
                book_hash="hb",
                provider_timestamp=NOW,
            ),
        },
        missing_tokens=(),
        malformed_tokens=(),
        raw=(),
    )
    record = build_quote_snapshot(
        market_id=market_id,
        token_ids=("tok_a", "tok_b"),
        player_ids=("ply_a", "ply_b"),
        batch=batch,
        observed_at=NOW,
        expires_at=NOW + timedelta(seconds=300),
    )
    assert await repo.upsert(record) is True
    stored = await repo.load(market_id)
    assert stored is not None
    assert stored.state is QuoteState.SNAPSHOT
    assert stored.outcome_asks == ("0.60", "0.42")
    assert stored.levels is not None and len(stored.levels) == 2
    assert stored.levels[0].outcome_player_id == "ply_a"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && uv run pytest tests/integration/test_market_quote_persistence.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.markets.quote_snapshot'`

- [ ] **Step 3: 实现仓库**

在 `backend/app/persistence/market_repositories.py` 顶部 import 区加入：

```python
from app.markets.models import OutcomeBook  # 追加到既有 markets.models import
from app.markets.quotes import (
    QuoteSnapshotRecord,
    QuoteSource,
    QuoteState,
    decide_quote_write,
)
from app.persistence.models import MarketQuoteSnapshotRow  # 追加到既有 import
```

在文件末尾（`__all__` 之前）加入：

```python
def _quote_record(market_id: str, row: MarketQuoteSnapshotRow) -> QuoteSnapshotRecord:
    levels = None
    payload = row.payload or {}
    books = payload.get("books")
    if isinstance(books, list) and len(books) == 2:
        levels = (
            OutcomeBook.model_validate(books[0]),
            OutcomeBook.model_validate(books[1]),
        )
    return QuoteSnapshotRecord(
        market_id=market_id,
        source=QuoteSource(row.source),
        state=QuoteState(row.quote_state),
        book_hash=row.book_hash,
        as_of=row.as_of,
        expires_at=row.expires_at,
        levels=levels,
        outcome_bids=(row.outcome_a_bid, row.outcome_b_bid),
        outcome_asks=(row.outcome_a_ask, row.outcome_b_ask),
        best_bid=(levels[0].outcome_player_id, row.outcome_a_bid) if row.outcome_a_bid else None,
        best_ask=(levels[0].outcome_player_id, row.outcome_a_ask) if row.outcome_a_ask else None,
        spread=row.spread,
        depth_usd=row.depth_usd,
    )


def _quote_values(record: QuoteSnapshotRecord) -> dict[str, Any]:
    return {
        "source": record.source.value,
        "quote_state": record.state.value,
        "book_hash": record.book_hash,
        "as_of": record.as_of,
        "expires_at": record.expires_at,
        "outcome_a_bid": record.outcome_bids[0],
        "outcome_a_ask": record.outcome_asks[0],
        "outcome_b_bid": record.outcome_bids[1],
        "outcome_b_ask": record.outcome_asks[1],
        "spread": record.spread,
        "depth_usd": record.depth_usd,
        "payload": (
            {"books": [side.model_dump(mode="json") for side in record.levels]}
            if record.levels is not None
            else None
        ),
        "updated_at": datetime.now(UTC),
    }


class MarketQuoteSnapshotRepository:
    """Durable latest-quote projection: at most one row per market (T85).

    Single-writer by design (the runtime role): the coverage lane and the
    realtime mirror both come through `upsert`, which enforces the shared
    precedence rule inside one transaction. The API role only reads.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def upsert(self, record: QuoteSnapshotRecord) -> bool:
        """True when a row was written or replaced; False when the incoming
        quote is older, lower-precedence or byte-identical (idempotent)."""
        async with self._database.session() as session:
            async with session.begin():
                current = await session.get(
                    MarketQuoteSnapshotRow, record.market_id, with_for_update=True
                )
                existing = (
                    _quote_record(record.market_id, current)
                    if current is not None
                    else None
                )
                if not decide_quote_write(existing, record):
                    return False
                values = _quote_values(record)
                if current is None:
                    session.add(MarketQuoteSnapshotRow(market_id=record.market_id, **values))
                else:
                    for key, value in values.items():
                        setattr(current, key, value)
                return True

    async def load(self, market_id: str) -> QuoteSnapshotRecord | None:
        async with self._database.session() as session:
            row = await session.get(MarketQuoteSnapshotRow, market_id)
        return _quote_record(market_id, row) if row is not None else None

    async def load_many(self, market_ids: Sequence[str]) -> dict[str, QuoteSnapshotRecord]:
        ids = {market_id for market_id in market_ids if market_id}
        if not ids:
            return {}
        async with self._database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(MarketQuoteSnapshotRow).where(
                            MarketQuoteSnapshotRow.market_id.in_(ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
        return {row.market_id: _quote_record(row.market_id, row) for row in rows}

    async def mark_state(
        self, market_ids: Sequence[str], *, state: QuoteState, now: datetime
    ) -> int:
        """Retag existing rows (used for `limited`) without touching the
        stored levels, `as_of` or `expires_at` — the last trusted quote and
        its time are preserved."""
        ids = [market_id for market_id in market_ids if market_id]
        if not ids:
            return 0
        async with self._database.session() as session:
            async with session.begin():
                result = await session.execute(
                    update(MarketQuoteSnapshotRow)
                    .where(MarketQuoteSnapshotRow.market_id.in_(ids))
                    .values(quote_state=state.value, updated_at=now)
                )
                return result.rowcount or 0
```

并把 `MarketQuoteSnapshotRepository` 加入 `__all__`。

- [ ] **Step 4: 实现 `app/markets/quote_snapshot.py`**

新建：

```python
"""Coverage-lane snapshot plumbing (T85).

Turns a private token batch into durable latest-quote rows and keeps the
raw batch material in the existing 14-day raw store. Nothing here may touch
the realtime WebSocket lane, the prediction service, the decision worker or
the paper ledger: this lane only fills display quotes for the market pages.
"""

from collections.abc import Sequence
from datetime import datetime

from app.markets.quotes import ClobBooksBatch

RAW_CHANNEL = "market"
RAW_KIND = "clob_books_batch"


async def record_raw_batch(
    raw_repo,
    *,
    observed_at: datetime,
    batch: ClobBooksBatch,
    batch_index: int,
) -> None:
    """Persist one raw batch response (never per token) for diagnostics.

    The payload is private diagnostic material under the existing 14-day
    retention; it never reaches a public DTO, log or page. `match_id` and
    `external_match_id` stay None because a batch spans several markets.
    """
    if not batch.raw:
        return
    await raw_repo.append(
        provider="polymarket",
        channel=RAW_CHANNEL,
        kind=RAW_KIND,
        payload={"batch_index": int(batch_index), "books": list(batch.raw)},
        observed_at=observed_at,
    )


def batch_tokens(token_pairs: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    """Flatten, de-duplicate and stable-order the private tokens of many
    markets (one market contributes exactly two tokens)."""
    seen: dict[str, None] = {}
    for token_a, token_b in token_pairs:
        for token in (token_a, token_b):
            if token:
                seen.setdefault(token, None)
    return tuple(seen)
```

- [ ] **Step 5: 运行 integration 与确定性测试**

Run: `cd backend && uv run pytest tests/integration/test_market_quote_persistence.py -v`
Expected: PASS

Run: `cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure and not player_alias_llm_live and not player_directory_e2e_live and not polymarket_live and not local_runtime_live" -q`
Expected: 全部通过

- [ ] **Step 6: ruff**

Run: `cd backend && uv run ruff check app/markets/quotes.py app/markets/quote_snapshot.py app/markets/polymarket.py app/persistence/market_repositories.py app/persistence/models.py tests/test_market_quote_snapshot.py tests/test_polymarket_batch_books.py tests/integration/test_market_quote_persistence.py && uv run ruff format --check app/markets/quotes.py app/markets/quote_snapshot.py app/markets/polymarket.py app/persistence/market_repositories.py app/persistence/models.py tests/test_market_quote_snapshot.py tests/test_polymarket_batch_books.py tests/integration/test_market_quote_persistence.py`
Expected: 无输出

- [ ] **Step 7: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add backend/app/markets/quote_snapshot.py backend/app/persistence/market_repositories.py \
        backend/tests/integration/test_market_quote_persistence.py
git commit -m "feat: persist idempotent latest quotes with raw batch retention"
```

### Task T85.5: T85 收口（总控 + 推送）

- [ ] **Step 1: 更新 `CURRENT.md`**：T85 `done` + 实际验证证据（各测试文件通过数、migration 往返 exit 0、integration 计数），下一步指向 T86。

- [ ] **Step 2: 更新 `ROADMAP.md`**：T85 行 `done` + 四个实现提交；T86 行保持 `planned`。

- [ ] **Step 3: 提交并推送**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add CURRENT.md ROADMAP.md
git commit -m "docs: close T85 batch quote coverage"
git push origin main
```

---

# T86 — Snapshot Scheduling, Coverage Health and Market Stream Hardening

**交付物**：有界 120 秒 snapshot 作业（公平轮转、分批、429/Retry-After/backoff、`limited` 诚实聚合）；runtime health 增加聚合 market coverage；WebSocket 正常关闭/keepalive/overflow→gap→REST reconcile 的显式生命周期与恢复证据；WebSocket 热 book 镜像进共享投影（source precedence 唯一实现）。

**不改变**：decision WebSocket roster（不新增任何订阅）；prediction/decision/paper 语义。

### Task T86.1: 有界配置贯通与两个批量读助手

**Files:**
- Modify: `backend/app/config.py`、`backend/app/runtime/models.py`、`backend/app/runtime/config.py`、`.env.example`
- Modify: `backend/app/persistence/market_repositories.py`（`MarketOverviewRow.event_start` + `list_external_ids`）
- Test: `backend/tests/test_config.py`（追加）、`backend/tests/test_runtime_config.py`（追加）、`backend/tests/test_market_overview_projection.py`（同步 helper）

**Interfaces:**
- Produces: `Settings.local_runtime_market_snapshot_seconds/max_markets/token_batch_size/quote_fresh_seconds`；`LocalRuntimeSettings.market_snapshot_seconds/market_snapshot_max_markets/market_snapshot_token_batch_size/market_quote_fresh_seconds`；`MarketOverviewRow.event_start: datetime | None`；`MarketRepository.list_external_ids(market_ids) -> dict[str, MarketExternalId]`

- [ ] **Step 1: 先写失败测试（配置边界与贯通）**

在 `backend/tests/test_config.py` 追加：

```python
def test_market_snapshot_configuration_bounds():
    base = Settings(_env_file=None)
    assert base.local_runtime_market_snapshot_seconds == 120
    assert base.local_runtime_market_snapshot_max_markets == 250
    assert base.local_runtime_market_snapshot_token_batch_size == 100
    assert base.local_runtime_market_quote_fresh_seconds == 300
    for field, value in (
        ("local_runtime_market_snapshot_seconds", 30),
        ("local_runtime_market_snapshot_max_markets", 501),
        ("local_runtime_market_snapshot_token_batch_size", 1),
        ("local_runtime_market_quote_fresh_seconds", 60),
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **{field: value})
```

在 `backend/tests/test_runtime_config.py` 追加（沿用该文件既有的合法配置 fixture/工厂）：

```python
def test_live_local_settings_carry_the_bounded_snapshot_configuration(...):
    ...
    assert live.market_snapshot_seconds == settings.local_runtime_market_snapshot_seconds
    assert live.market_snapshot_max_markets == settings.local_runtime_market_snapshot_max_markets
    assert live.market_snapshot_token_batch_size == settings.local_runtime_market_snapshot_token_batch_size
    assert live.market_quote_fresh_seconds == settings.local_runtime_market_quote_fresh_seconds
```

> 实现时按该文件既有写法补全 fixture（不得新建独立的设置构造方式）。

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/test_config.py tests/test_runtime_config.py -q`
Expected: FAIL — `AttributeError`/`ValidationError`（字段不存在）

- [ ] **Step 3: 实现配置**

`backend/app/config.py` 在 `local_runtime_market_discovery_seconds` 之后加入：

```python
    # P4.3 coverage lane: bounded public batch quote snapshots. The lane only
    # fills display quotes; it never subscribes a WebSocket, calls the LLM or
    # touches prediction/decision/paper.
    local_runtime_market_snapshot_seconds: int = Field(default=120, ge=60, le=900)
    local_runtime_market_snapshot_max_markets: int = Field(default=250, ge=1, le=500)
    local_runtime_market_snapshot_token_batch_size: int = Field(
        default=100, ge=2, le=100
    )
    local_runtime_market_quote_fresh_seconds: int = Field(default=300, ge=120, le=1800)
```

`backend/app/runtime/models.py` 的 `LocalRuntimeSettings` 追加：

```python
    market_snapshot_seconds: int = Field(default=120, ge=60, le=900)
    market_snapshot_max_markets: int = Field(default=250, ge=1, le=500)
    market_snapshot_token_batch_size: int = Field(default=100, ge=2, le=100)
    market_quote_fresh_seconds: int = Field(default=300, ge=120, le=1800)
```

`backend/app/runtime/config.py` 的 `require_live_local` 返回值追加：

```python
        market_snapshot_seconds=settings.local_runtime_market_snapshot_seconds,
        market_snapshot_max_markets=settings.local_runtime_market_snapshot_max_markets,
        market_snapshot_token_batch_size=(
            settings.local_runtime_market_snapshot_token_batch_size
        ),
        market_quote_fresh_seconds=settings.local_runtime_market_quote_fresh_seconds,
```

`.env.example` 在 `TENNIX_LOCAL_RUNTIME_MARKET_DISCOVERY_SECONDS=120` 之后加入：

```
TENNIX_LOCAL_RUNTIME_MARKET_SNAPSHOT_SECONDS=120
TENNIX_LOCAL_RUNTIME_MARKET_SNAPSHOT_MAX_MARKETS=250
TENNIX_LOCAL_RUNTIME_MARKET_SNAPSHOT_TOKEN_BATCH_SIZE=100
TENNIX_LOCAL_RUNTIME_MARKET_QUOTE_FRESH_SECONDS=300
```

- [ ] **Step 4: 两个批量读助手**

`MarketOverviewRow` 增加 `event_start: datetime | None` 字段（放在 `observed_at` 之前），`list_market_overviews` 的 SELECT 增加 `MarketRow.event_start` 并把 `MarketOverviewRow(...)` 构造补上 `event_start=row[5]`（其余索引顺延）。同步更新 `backend/tests/test_market_overview_projection.py` 的 `overview()` helper：`event_start=None`。

在 `list_external_ids` 位置（`get_external_id` 之后）加入：

```python
    async def list_external_ids(
        self, market_ids: Sequence[str]
    ) -> dict[str, MarketExternalId]:
        """PRIVATE mapping for many markets in ONE query (no per-row reads).

        The returned model carries provider identity; callers must keep it
        inside the adapter/runtime boundary.
        """
        ids = {market_id for market_id in market_ids if market_id}
        if not ids:
            return {}
        async with self._database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(MarketExternalIdRow).where(
                            MarketExternalIdRow.market_id.in_(ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
        return {
            row.market_id: MarketExternalId(
                market_id=row.market_id,
                provider=row.provider,
                provider_event_id=row.provider_event_id,
                condition_id=row.condition_id,
                token_ids=(row.token_a_id, row.token_b_id),
            )
            for row in rows
        }
```

- [ ] **Step 5: 运行测试**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/test_config.py tests/test_runtime_config.py tests/test_market_overview_projection.py -q`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add backend/app/config.py backend/app/runtime/models.py backend/app/runtime/config.py .env.example \
        backend/app/persistence/market_repositories.py backend/tests/test_config.py \
        backend/tests/test_runtime_config.py backend/tests/test_market_overview_projection.py
git commit -m "feat: add bounded market snapshot configuration"
```

### Task T86.2: 聚合 coverage 健康（模型 + registry + 公开 DTO）

**Files:**
- Modify: `backend/app/runtime/models.py`、`backend/app/runtime/health.py`、`backend/app/api/schemas.py`
- Test: `backend/tests/test_runtime_health.py`（追加）

**Interfaces:**
- Produces: `MarketQuoteCoverage`；`RuntimeHealth.market_coverage`；`RuntimeHealthRegistry.set_market_coverage()`；`MarketQuoteCoverageDto`；`RuntimeHealthDto.market_coverage`

- [ ] **Step 1: 先写失败测试**

在 `backend/tests/test_runtime_health.py` 追加（沿用该文件既有的 registry/stub-state 构造）：

```python
async def test_market_coverage_is_persisted_as_aggregate_counts(...):
    ...
    coverage = MarketQuoteCoverage(
        generated_at=NOW,
        candidate=181,
        attempted=181,
        fresh_snapshot=150,
        no_liquidity=20,
        unavailable=11,
        batch_failures=0,
        rate_limited=False,
        last_successful_batch_at=NOW,
    )
    registry.set_market_coverage(coverage)
    health = await registry.persist()
    assert health.market_coverage is not None
    assert health.market_coverage.candidate == 181
    assert health.market_coverage.fresh_snapshot == 150
    blob = health.model_dump_json().lower()
    for fragment in ("token", "condition", "0x", "http"):
        assert fragment not in blob
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/test_runtime_health.py -q`
Expected: FAIL — `ImportError: cannot import name 'MarketQuoteCoverage'`

- [ ] **Step 3: 实现模型与 registry**

`backend/app/runtime/models.py` 在 `RuntimeHealth` 之前加入：

```python
class MarketQuoteCoverage(FrozenModel):
    """Aggregate coverage facts for the batch quote lane (T86).

    Counts and timestamps only: candidate/attempted markets, the display
    state buckets the pages would show, batch failures and the 429 backoff
    window. Provider identity, tokens, URLs and payloads never appear here.
    """

    generated_at: datetime
    candidate: int = Field(default=0, ge=0)
    attempted: int = Field(default=0, ge=0)
    fresh_realtime: int = Field(default=0, ge=0)
    fresh_snapshot: int = Field(default=0, ge=0)
    partial: int = Field(default=0, ge=0)
    no_liquidity: int = Field(default=0, ge=0)
    unavailable: int = Field(default=0, ge=0)
    stale: int = Field(default=0, ge=0)
    limited: int = Field(default=0, ge=0)
    batch_failures: int = Field(default=0, ge=0)
    rate_limited: bool = False
    retry_after_until: datetime | None = None
    last_successful_batch_at: datetime | None = None

    @field_validator("generated_at", "retry_after_until", "last_successful_batch_at")
    @classmethod
    def require_coverage_timezone(cls, value: datetime | None) -> datetime | None:
        return _require_timezone(value)
```

`RuntimeHealth` 追加字段：

```python
    market_coverage: MarketQuoteCoverage | None = None
```

`backend/app/runtime/health.py`：import 增加 `MarketQuoteCoverage`，`RuntimeHealthRegistry` 增加字段与 setter，并在 `persist()` 传入：

```python
    _market_coverage: MarketQuoteCoverage | None = None
```

```python
    def set_market_coverage(self, coverage: MarketQuoteCoverage | None) -> None:
        """Store the latest coverage round for the next `persist()`.

        A failed round never erases the last truthful coverage; callers pass
        `None` only when the lane was never run.
        """
        self._market_coverage = coverage
```

```python
            counters=counters,
            paper_status=self.paper_status,
            model_status=self.model_status,
            market_coverage=self._market_coverage,
        )
```

- [ ] **Step 4: 公开 DTO**

`backend/app/api/schemas.py` 在 `RuntimeHealthDto` 之前加入：

```python
class MarketQuoteCoverageDto(BaseModel):
    generated_at: datetime
    candidate: int = 0
    attempted: int = 0
    fresh_realtime: int = 0
    fresh_snapshot: int = 0
    partial: int = 0
    no_liquidity: int = 0
    unavailable: int = 0
    stale: int = 0
    limited: int = 0
    batch_failures: int = 0
    rate_limited: bool = False
    retry_after_until: datetime | None = None
    last_successful_batch_at: datetime | None = None


class RuntimeHealthDto(BaseModel):
```

并给 `RuntimeHealthDto` 追加 `market_coverage: MarketQuoteCoverageDto | None = None`（`/runtime/health` 路由用 `model_validate(health.model_dump())`，字段自动带出，无需改路由）。

- [ ] **Step 5: 运行测试**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/test_runtime_health.py tests/test_runtime_api_role.py -q`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add backend/app/runtime/models.py backend/app/runtime/health.py backend/app/api/schemas.py \
        backend/tests/test_runtime_health.py
git commit -m "feat: expose aggregate market quote coverage health"
```

### Task T86.3: 有界 snapshot 作业

**Files:**
- Create: `backend/app/runtime/market_snapshot.py`
- Modify: `backend/app/markets/quotes.py`（新增 `realtime_quote_record`）、`backend/app/persistence/market_repositories.py`（新增 `mark_limited`）
- Test: `backend/tests/test_market_snapshot_job.py`（新建）

**Interfaces:**
- Consumes: `MarketRepository.list_market_overviews/list_external_ids`、`MarketQuoteSnapshotRepository.upsert/load_many/mark_limited`、`PolymarketProvider.get_order_books`、`RawProviderEventRepository.append`、`MatchCatalogRepository.list_matches`、`MarketHotPublisher.get_hot_books`
- Produces: `MarketQuoteSnapshotJob.run_once() -> MarketQuoteCoverage`、`realtime_quote_record(book, *, fresh_seconds) -> QuoteSnapshotRecord`

- [ ] **Step 1: 先写失败测试**

新建 `backend/tests/test_market_snapshot_job.py`：

```python
"""Bounded coverage-lane snapshot job tests (T86). No real network."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.errors import AppError
from app.markets.models import BookLevel
from app.markets.quotes import (
    ClobBooksBatch,
    QuoteSnapshotRecord,
    QuoteSource,
    QuoteState,
    TokenBook,
)
from app.persistence.market_repositories import MarketOverviewRow
from app.runtime.market_snapshot import MarketQuoteSnapshotJob

NOW = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)
TOKENS = {f"mkt_{index}": (f"tok_a{index}", f"tok_b{index}") for index in range(5)}


def overview(market_id: str, *, status: str = "open") -> MarketOverviewRow:
    return MarketOverviewRow(
        market_id=market_id,
        question=f"Question {market_id}",
        status=status,
        rules_version=1,
        observed_at=NOW,
        updated_at=NOW,
        outcome_a_player_id=f"ply_a_{market_id}",
        outcome_a_name="Provider A",
        outcome_b_player_id=f"ply_b_{market_id}",
        outcome_b_name="Provider B",
        active_match_id=f"mat_{market_id}",
        link_evidence_available=True,
        event_start=NOW + timedelta(hours=1),
    )


class FakeMarkets:
    def __init__(self, rows, *, tokens=None):
        self._rows = list(rows)
        self._tokens = dict(tokens or TOKENS)
        self.external_calls: list[tuple[str, ...]] = []

    async def list_market_overviews(self):
        return list(self._rows)

    async def list_external_ids(self, market_ids):
        self.external_calls.append(tuple(market_ids))
        from app.markets.models import MarketExternalId

        return {
            market_id: MarketExternalId(
                market_id=market_id,
                provider="polymarket",
                provider_event_id=f"ev_{market_id}",
                condition_id=f"cond_{market_id}",
                token_ids=self._tokens[market_id],
            )
            for market_id in market_ids
            if market_id in self._tokens
        }


class FakeProjections:
    def __init__(self, stored=None):
        self.stored = dict(stored or {})
        self.writes: list[QuoteSnapshotRecord] = []
        self.limited: list[tuple[str, ...]] = []
        self.load_many_calls = 0

    async def upsert(self, record):
        self.writes.append(record)
        self.stored[record.market_id] = record
        return True

    async def load_many(self, market_ids):
        self.load_many_calls += 1
        return {mid: self.stored[mid] for mid in market_ids if mid in self.stored}

    async def mark_limited(self, market_ids, *, now, expires_at):
        self.limited.append(tuple(market_ids))
        return len(list(market_ids))


class FakeProvider:
    def __init__(self, *, fail_with=None, rate_after=None):
        self.calls: list[tuple[str, ...]] = []
        self._fail_with = fail_with
        self._rate_after = rate_after
        self.sent_prediction = False

    async def get_order_books(self, token_ids):
        self.calls.append(tuple(token_ids))
        if self._rate_after is not None and len(self.calls) > self._rate_after:
            raise AppError("rate_limited", "rate limited", 429, {"retry_after": "30"})
        if self._fail_with is not None:
            raise self._fail_with
        books = {}
        for token in token_ids:
            books[token] = TokenBook(
                token_id=token,
                bids=(BookLevel(price=Decimal("0.58"), size=Decimal("10")),),
                asks=(BookLevel(price=Decimal("0.60"), size=Decimal("10")),),
                book_hash=f"h_{token[:4]}",
                provider_timestamp=NOW,
            )
        return ClobBooksBatch(books=books, raw=({"asset_id": token_ids[0]},))


class FakeRaw:
    def __init__(self):
        self.batches: list[tuple[int, int]] = []

    async def append(self, *, provider, channel, kind, payload, observed_at, **kwargs):
        self.batches.append((payload["batch_index"], len(payload["books"])))


class FakeCatalog:
    async def list_matches(self, status):
        return []


class FakeHot:
    async def get_hot_books(self, market_ids):
        return {}


def job(*, markets, projections, provider=None, raw=None, max_markets=250,
        token_batch_size=100, hot=None) -> MarketQuoteSnapshotJob:
    return MarketQuoteSnapshotJob(
        markets=markets,
        projections=projections,
        provider=provider or FakeProvider(),
        raw=raw or FakeRaw(),
        catalog=FakeCatalog(),
        hot_books=hot or FakeHot(),
        clock=lambda: NOW,
        max_markets=max_markets,
        token_batch_size=token_batch_size,
        quote_fresh_seconds=300,
        realtime_fresh_seconds=5,
    )


async def test_snapshot_job_splits_batches_and_writes_every_candidate():
    markets = FakeMarkets([overview(market_id) for market_id in TOKENS])
    projections = FakeProjections()
    provider = FakeProvider()
    raw = FakeRaw()
    runner = job(
        markets=markets, projections=projections, provider=provider, raw=raw,
        token_batch_size=4,
    )

    coverage = await runner.run_once()

    # 5 markets x 2 tokens split into batches of <= 4 tokens => 3 requests.
    assert len(provider.calls) == 3
    assert all(len(call) <= 4 for call in provider.calls)
    assert len(raw.batches) == 3  # one raw row per batch, never per token
    assert markets.external_calls and len(markets.external_calls) == 1
    assert len(projections.writes) == 5
    assert all(record.state is QuoteState.SNAPSHOT for record in projections.writes)
    assert coverage.candidate == 5 and coverage.attempted == 5
    assert coverage.fresh_snapshot == 5
    assert sum(
        [
            coverage.fresh_realtime,
            coverage.fresh_snapshot,
            coverage.partial,
            coverage.no_liquidity,
            coverage.unavailable,
            coverage.stale,
            coverage.limited,
        ]
    ) == coverage.candidate
    assert coverage.last_successful_batch_at == NOW


async def test_snapshot_job_marks_the_overflow_as_limited_without_dropping_it():
    markets = FakeMarkets([overview(market_id) for market_id in TOKENS])
    projections = FakeProjections()
    runner = job(markets=markets, projections=projections, max_markets=3)

    coverage = await runner.run_once()

    assert projections.limited == [tuple(sorted(TOKENS)[3:])]
    assert coverage.candidate == 5 and coverage.attempted == 3
    assert coverage.limited == 2


async def test_snapshot_job_respects_429_and_skips_the_next_round():
    markets = FakeMarkets([overview(market_id) for market_id in TOKENS])
    projections = FakeProjections()
    provider = FakeProvider(rate_after=1)
    runner = job(
        markets=markets, projections=projections, provider=provider,
        token_batch_size=4,
    )

    first = await runner.run_once()
    assert first.rate_limited is True
    assert first.retry_after_until == NOW + timedelta(seconds=30)
    assert len(provider.calls) == 2  # no busy retry inside the round

    second = await runner.run_once()
    assert len(provider.calls) == 2  # the whole next round is skipped
    assert second.rate_limited is True
    assert second.attempted == 0


async def test_snapshot_job_counts_batch_failures_and_keeps_going():
    markets = FakeMarkets([overview(market_id) for market_id in TOKENS])
    projections = FakeProjections()
    provider = FakeProvider(fail_with=AppError("provider_unavailable", "down", 503))
    runner = job(
        markets=markets, projections=projections, provider=provider,
        token_batch_size=4,
    )

    coverage = await runner.run_once()

    assert coverage.batch_failures == 3
    assert coverage.attempted == 0
    assert projections.writes == []
    # Nothing was fabricated for the failed markets.
    assert all(
        record.state is QuoteState.UNAVAILABLE
        for record in projections.stored.values()
    ) or projections.stored == {}


async def test_snapshot_job_skips_markets_without_canonical_identity_or_tokens():
    rows = [overview("mkt_0"), overview("mkt_closed", status="closed")]
    markets = FakeMarkets(rows, tokens={"mkt_0": TOKENS["mkt_0"]})
    projections = FakeProjections()
    runner = job(markets=markets, projections=projections)

    coverage = await runner.run_once()

    assert coverage.candidate == 1
    assert [record.market_id for record in projections.writes] == ["mkt_0"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/test_market_snapshot_job.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.runtime.market_snapshot'`

- [ ] **Step 3: 实现 `mark_limited` 与 `realtime_quote_record`**

`backend/app/persistence/market_repositories.py` 的 `MarketQuoteSnapshotRepository` 追加：

```python
    async def mark_limited(
        self, market_ids: Sequence[str], *, now: datetime, expires_at: datetime
    ) -> int:
        """Retag markets the protection cap did not reach this round.

        Stored levels and their `as_of` are preserved (the page keeps showing
        the last trusted quote with a `limited` label); a market without a
        row yet gets a minimal limited row so the cap is explained instead of
        showing an unexplained `—`.
        """
        ids = [market_id for market_id in market_ids if market_id]
        if not ids:
            return 0
        written = 0
        async with self._database.session() as session:
            async with session.begin():
                present = set(
                    (
                        await session.execute(
                            select(MarketQuoteSnapshotRow.market_id).where(
                                MarketQuoteSnapshotRow.market_id.in_(ids)
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                if present:
                    result = await session.execute(
                        update(MarketQuoteSnapshotRow)
                        .where(MarketQuoteSnapshotRow.market_id.in_(present))
                        .values(
                            quote_state=QuoteState.LIMITED.value, updated_at=now
                        )
                    )
                    written += result.rowcount or 0
                for market_id in ids:
                    if market_id in present:
                        continue
                    session.add(
                        MarketQuoteSnapshotRow(
                            market_id=market_id,
                            source=QuoteSource.SNAPSHOT.value,
                            quote_state=QuoteState.LIMITED.value,
                            book_hash=None,
                            as_of=now,
                            expires_at=expires_at,
                            updated_at=now,
                        )
                    )
                    written += 1
        return written
```

`backend/app/markets/quotes.py` 追加：

```python
def realtime_quote_record(
    book: OrderBookState, *, fresh_seconds: int
) -> QuoteSnapshotRecord:
    """Mirror a fresh WebSocket hot book into the shared projection.

    Used by the runtime's realtime mirror so pages read ONE precedence rule
    for both lanes; the record never carries provider identity.
    """
    bids, asks, spread, depth = outcome_levels(
        book, [side.outcome_player_id for side in book.books]
    )
    best_bid, best_ask = best_levels(book, book.books[0].outcome_player_id)
    return QuoteSnapshotRecord(
        market_id=book.market_id,
        source=QuoteSource.REALTIME,
        state=_state_for_books(book.books),
        book_hash=book.book_hash,
        as_of=book.received_at,
        expires_at=book.received_at + timedelta(seconds=fresh_seconds),
        levels=(book.books[0], book.books[1]),
        outcome_bids=bids or (None, None),
        outcome_asks=asks or (None, None),
        best_bid=best_bid,
        best_ask=best_ask,
        spread=str(spread) if spread is not None else None,
        depth_usd=str(depth) if depth is not None else None,
    )
```

在 `backend/tests/test_market_quote_snapshot.py` 追加一个 unit 断言：

```python
def test_realtime_quote_record_mirrors_levels_with_precedence_metadata():
    record = realtime_quote_record(
        hot_book(a=("0.61", "0.63"), b=("0.37", "0.39")), fresh_seconds=300
    )
    assert record.source is QuoteSource.REALTIME
    assert record.state is QuoteState.SNAPSHOT
    assert record.as_of == NOW
    assert record.expires_at == NOW + timedelta(seconds=300)
    assert record.outcome_asks == ("0.63", "0.39")
```

- [ ] **Step 4: 实现作业**

新建 `backend/app/runtime/market_snapshot.py`：

```python
"""Bounded coverage-lane snapshot job (T86).

Every round ranks the canonical open/scheduled markets fairly, takes at most
`max_markets`, batches their private tokens, calls the public CLOB
`POST /books` sequentially and writes the canonical result into the shared
latest-quote projection. A 429 ends the round and suppresses the following
rounds until the server-provided instant — never a busy retry.

This lane has exactly one job: fill display quotes. It never subscribes a
market WebSocket, never calls the LLM, and never touches prediction,
decision or paper.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.domain import CircuitTier, MatchStatus
from app.errors import AppError
from app.markets.quote_snapshot import batch_tokens, record_raw_batch
from app.markets.quotes import (
    QuoteState,
    build_quote_snapshot,
    display_quote,
)
from app.runtime.models import MarketQuoteCoverage

TIER_RANK: dict[CircuitTier, int] = {
    CircuitTier.ATP: 0,
    CircuitTier.WTA: 0,
    CircuitTier.CHALLENGER: 1,
    CircuitTier.ITF: 2,
    CircuitTier.OTHER: 3,
}

STATE_BUCKETS: dict[QuoteState, str] = {
    QuoteState.SNAPSHOT: "fresh_snapshot",
    QuoteState.PARTIAL: "partial",
    QuoteState.NO_LIQUIDITY: "no_liquidity",
    QuoteState.UNAVAILABLE: "unavailable",
    QuoteState.STALE: "stale",
    QuoteState.LIMITED: "limited",
}

ELIGIBLE_MARKET_STATUSES = frozenset({"open", "scheduled"})
DEFAULT_RETRY_AFTER_SECONDS = 60
MAX_RETRY_AFTER_SECONDS = 900


def retry_after_seconds(error: AppError) -> int:
    """Bounded, server-provided backoff; never an unbounded sleep."""
    raw = (error.details or {}).get("retry_after")
    try:
        seconds = int(str(raw))
    except (TypeError, ValueError):
        return DEFAULT_RETRY_AFTER_SECONDS
    return max(1, min(seconds, MAX_RETRY_AFTER_SECONDS))


@dataclass(frozen=True)
class SnapshotCandidate:
    market_id: str
    tokens: tuple[str, str]
    player_ids: tuple[str, str]
    sort_key: tuple


class MarketQuoteSnapshotJob:
    def __init__(
        self,
        *,
        markets,
        projections,
        provider,
        raw,
        catalog,
        hot_books,
        clock: Callable[[], datetime],
        max_markets: int = 250,
        token_batch_size: int = 100,
        quote_fresh_seconds: int = 300,
        realtime_fresh_seconds: int = 5,
    ) -> None:
        self._markets = markets
        self._projections = projections
        self._provider = provider
        self._raw = raw
        self._catalog = catalog
        self._hot_books = hot_books
        self._clock = clock
        self._max_markets = max_markets
        self._token_batch_size = token_batch_size
        self._quote_fresh_seconds = quote_fresh_seconds
        self._realtime_fresh_seconds = realtime_fresh_seconds
        self._retry_after_until: datetime | None = None
        self._last_successful_batch_at: datetime | None = None

    async def run_once(self) -> MarketQuoteCoverage:
        now = self._clock()
        backoff_active = (
            self._retry_after_until is not None and now < self._retry_after_until
        )
        candidates = await self._candidates()
        selected = candidates[: self._max_markets]
        beyond = candidates[self._max_markets :]
        if beyond:
            await self._projections.mark_limited(
                [candidate.market_id for candidate in beyond],
                now=now,
                expires_at=now + timedelta(seconds=self._quote_fresh_seconds),
            )
        written: dict[str, object] = {}
        attempted: list[str] = []
        batch_failures = 0
        rate_limited = False
        if not backoff_active:
            for index, group in enumerate(self._batches(selected)):
                tokens = batch_tokens([candidate.tokens for candidate in group])
                try:
                    batch = await self._provider.get_order_books(tokens)
                except AppError as exc:
                    if exc.code == "rate_limited":
                        rate_limited = True
                        self._retry_after_until = now + timedelta(
                            seconds=retry_after_seconds(exc)
                        )
                        break
                    batch_failures += 1
                    continue
                await record_raw_batch(
                    self._raw, observed_at=now, batch=batch, batch_index=index
                )
                self._last_successful_batch_at = now
                for candidate in group:
                    record = build_quote_snapshot(
                        market_id=candidate.market_id,
                        token_ids=candidate.tokens,
                        player_ids=candidate.player_ids,
                        batch=batch,
                        observed_at=now,
                        expires_at=now + timedelta(seconds=self._quote_fresh_seconds),
                    )
                    await self._projections.upsert(record)
                    written[candidate.market_id] = record
                    attempted.append(candidate.market_id)
        return await self._coverage(
            now,
            candidates=candidates,
            attempted=attempted,
            written=written,
            batch_failures=batch_failures,
            rate_limited=rate_limited or backoff_active,
        )

    # -- candidate selection and fair rotation ---------------------------

    async def _candidates(self) -> list[SnapshotCandidate]:
        overviews = await self._markets.list_market_overviews()
        eligible = [
            row
            for row in overviews
            if row.status in ELIGIBLE_MARKET_STATUSES
            and row.outcome_a_player_id
            and row.outcome_b_player_id
        ]
        if not eligible:
            return []
        externals = await self._markets.list_external_ids(
            [row.market_id for row in eligible]
        )
        ranks = await self._match_ranks()
        candidates: list[SnapshotCandidate] = []
        for row in eligible:
            external = externals.get(row.market_id)
            if external is None or not external.token_ids[0] or not external.token_ids[1]:
                # No private token target yet: never invent one.
                continue
            is_live, tier = ranks.get(row.active_match_id or "", (False, CircuitTier.OTHER))
            candidates.append(
                SnapshotCandidate(
                    market_id=row.market_id,
                    tokens=external.token_ids,
                    player_ids=(row.outcome_a_player_id, row.outcome_b_player_id),
                    sort_key=(
                        0 if is_live else 1,
                        row.event_start or datetime.max.replace(tzinfo=UTC),
                        TIER_RANK.get(tier, TIER_RANK[CircuitTier.OTHER]),
                        row.market_id,
                    ),
                )
            )
        candidates.sort(key=lambda candidate: candidate.sort_key)
        return candidates

    async def _match_ranks(self) -> dict[str, tuple[bool, CircuitTier]]:
        live = await self._catalog.list_matches(MatchStatus.LIVE)
        upcoming = await self._catalog.list_matches(MatchStatus.SCHEDULED)
        ranks = {
            match.id: (False, match.tournament.circuit) for match in upcoming
        }
        ranks.update({match.id: (True, match.tournament.circuit) for match in live})
        return ranks

    def _batches(
        self, candidates: Sequence[SnapshotCandidate]
    ) -> Iterator[Sequence[SnapshotCandidate]]:
        per_batch = max(1, self._token_batch_size // 2)
        for start in range(0, len(candidates), per_batch):
            yield candidates[start : start + per_batch]

    # -- coverage aggregation --------------------------------------------

    async def _coverage(
        self,
        now: datetime,
        *,
        candidates: Sequence[SnapshotCandidate],
        attempted: Sequence[str],
        written,
        batch_failures: int,
        rate_limited: bool,
    ) -> MarketQuoteCoverage:
        ids = [candidate.market_id for candidate in candidates]
        stored = dict(await self._projections.load_many(ids)) if ids else {}
        stored.update(written)
        try:
            hot = await self._hot_books.get_hot_books(tuple(ids))
        except Exception:  # noqa: BLE001 - coverage must never break the round
            hot = {}
        buckets = {
            "fresh_realtime": 0,
            "fresh_snapshot": 0,
            "partial": 0,
            "no_liquidity": 0,
            "unavailable": 0,
            "stale": 0,
            "limited": 0,
        }
        for market_id in ids:
            quote = display_quote(
                hot_book=hot.get(market_id),
                snapshot=stored.get(market_id),
                now=now,
                realtime_fresh_seconds=self._realtime_fresh_seconds,
                snapshot_fresh_seconds=self._quote_fresh_seconds,
            )
            if quote.state is QuoteState.REALTIME:
                buckets["fresh_realtime"] += 1
            else:
                buckets[STATE_BUCKETS[quote.state]] += 1
        return MarketQuoteCoverage(
            generated_at=now,
            candidate=len(ids),
            attempted=len(attempted),
            batch_failures=batch_failures,
            rate_limited=rate_limited,
            retry_after_until=self._retry_after_until,
            last_successful_batch_at=self._last_successful_batch_at,
            **buckets,
        )
```

- [ ] **Step 5: 运行测试**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/test_market_snapshot_job.py tests/test_market_quote_snapshot.py -q`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add backend/app/runtime/market_snapshot.py backend/app/markets/quotes.py \
        backend/app/persistence/market_repositories.py backend/tests/test_market_snapshot_job.py \
        backend/tests/test_market_quote_snapshot.py
git commit -m "feat: run the bounded batch quote snapshot job"
```

### Task T86.4: WebSocket 生命周期加固（正常关闭、每连接 keepalive、overflow 恢复）

**Files:**
- Modify: `backend/app/markets/live.py`、`backend/app/markets/worker.py`
- Test: `backend/tests/test_market_live_feed.py`（追加）、`backend/tests/test_market_worker.py`（追加）

**Interfaces:**
- Produces: `MarketFeedClosed`（正常关闭）；`PolymarketMarketFeed.shutdown()` 语义不变（取消全部在途 keepalive）；`MarketWorker.subscription_state()` 新增 `"closed"` 语义（正常关闭后保持关闭，直到 demand 撤销）

- [ ] **Step 1: 先写失败测试（feed 层）**

在 `backend/tests/test_market_live_feed.py` 追加：

```python
class NormalCloseConnection(FakeWebSocketConnection):
    async def recv(self) -> str:
        if self._frames:
            return self._frames.pop(0)
        import websockets.exceptions

        raise websockets.exceptions.ConnectionClosedOK(None, None)


async def test_normal_close_is_reported_as_a_typed_lifecycle_event():
    feed = PolymarketMarketFeed(
        websocket_factory=lambda url: NormalCloseConnection([book_frame()]),
        ping_interval_seconds=3600,
        now_fn=lambda: NOW,
    )
    events = [
        event
        async for event in feed.subscribe((TOKEN_A,))
    ]
    # The frame is delivered, then the stream ends with an explicit typed
    # normal-close signal instead of a transport error.
    assert len(events) == 1
    assert events[0].event_type == "book"


async def test_normal_close_raises_market_feed_closed():
    from app.markets.live import MarketFeedClosed

    feed = PolymarketMarketFeed(
        websocket_factory=lambda url: NormalCloseConnection([]),
        ping_interval_seconds=3600,
        now_fn=lambda: NOW,
    )
    with pytest.raises(MarketFeedClosed):
        async for _event in feed.subscribe((TOKEN_A,)):
            pass


async def test_each_subscription_owns_its_keepalive_and_leaves_no_task():
    feed = PolymarketMarketFeed(
        websocket_factory=lambda url: FakeWebSocketConnection([], close_after=True),
        ping_interval_seconds=0.01,
        now_fn=lambda: NOW,
        sleep_fn=asyncio.sleep,
    )
    before = asyncio.all_tasks()
    streams = [feed.subscribe((TOKEN_A,)) for _ in range(3)]
    for stream in streams:
        with pytest.raises(MarketFeedDisconnected):
            async for _event in stream:
                pass
    await asyncio.sleep(0.05)
    leaked = [
        task
        for task in asyncio.all_tasks() - before
        if not task.done() and "keep_alive" in repr(task.get_coro())
    ]
    assert leaked == []
    await feed.shutdown()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/test_market_live_feed.py -q`
Expected: FAIL — `ImportError: cannot import name 'MarketFeedClosed'`

- [ ] **Step 3: 实现 feed 加固**

`backend/app/markets/live.py` 增加类型：

```python
class MarketFeedClosed(Exception):
    """The provider closed this subscription normally (a finished market).

    Not a fault: the worker stops that subscription without recording a gap
    and without marking the whole market source as failed.
    """
```

`__init__` 增加 `self._ping_tasks: set[asyncio.Task] = set()`；`shutdown()` 改为取消全部在途 keepalive：

```python
    async def shutdown(self) -> None:
        """Cancel every in-flight keepalive task for this feed instance."""
        tasks = [task for task in self._ping_tasks if not task.done()]
        self._ping_tasks.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
```

订阅生成器改为（保留既有的 typing 与 `feed.` 前缀风格）：

```python
        async def generator() -> AsyncIterator[RawMarketEvent]:
            async with feed._connect(feed._ws_url) as connection:  # type: ignore[operator]
                subscribe_frame = json.dumps(
                    {"type": "market", "assets_ids": list(asset_ids)}
                )
                await connection.send(subscribe_frame)

                async def keep_alive() -> None:
                    # One task per connection: a second subscription must
                    # never clobber the first one's keepalive.
                    while True:
                        await feed._sleep(feed._ping_interval)
                        try:
                            await connection.send("PING")
                        except Exception:
                            # A dead socket ends the subscription through the
                            # normal receive path instead of a silent task.
                            with contextlib.suppress(Exception):
                                await connection.close()
                            return

                ping_task = asyncio.create_task(keep_alive())
                feed._ping_tasks.add(ping_task)
                try:
                    while True:
                        try:
                            raw = await connection.recv()
                        except websockets.exceptions.ConnectionClosedOK as error:
                            raise MarketFeedClosed("normal_close") from error
                        except websockets.exceptions.ConnectionClosed as error:
                            raise MarketFeedDisconnected("connection_closed") from error
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8", errors="replace")
                        if raw in ("PONG", "PING"):
                            continue
                        try:
                            payload = json.loads(raw)
                        except ValueError:
                            continue
                        if not isinstance(payload, dict):
                            continue
                        event_type = str(payload.get("event_type") or "")
                        if event_type not in CONSUMED_EVENT_TYPES:
                            continue
                        yield RawMarketEvent(
                            event_type=event_type,
                            asset_id=str(payload.get("asset_id") or ""),
                            payload=payload,
                            received_at=feed._now(),
                        )
                finally:
                    feed._ping_tasks.discard(ping_task)
                    if not ping_task.done():
                        ping_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await ping_task
```

> `ConnectionClosedOK` 必须比 `ConnectionClosed` 先捕获（前者是后者子类）；不得用 `error.code` 判断，`rcvd is None` 时 code 为 1006。

- [ ] **Step 4: 先写失败测试（worker 层）**

在 `backend/tests/test_market_worker.py` 追加：

```python
class NormalCloseMarketFeed(FakeMarketFeed):
    def stream_market(self, market_id: str, asset_ids: tuple[str, ...]):
        self.subscribed[market_id] = asset_ids
        queue = self.queues.setdefault(market_id, asyncio.Queue())
        feed = self

        async def generator():
            from app.markets.live import MarketFeedClosed

            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        raise MarketFeedClosed("normal_close")
                    yield item
            finally:
                feed.closed.add(market_id)

        return generator()


async def test_normal_close_stops_the_subscription_without_a_gap():
    feed = NormalCloseMarketFeed()
    worker, publisher, observations = worker_with(feed)
    await worker.reconcile_demand_once()  # subscribe MKT_1
    assert worker.subscription_state(MKT_1) == "live"

    await feed.disconnect(MKT_1)  # normal close
    await worker.reconcile_demand_once()

    # No gap, no reconnect, no fabricated book, subscription parked closed.
    assert [event["type"] for event in publisher.events if event["type"] == "market_gap"] == []
    assert worker.subscription_state(MKT_1) == "closed"
    assert worker.dropped_events(MKT_1) == 0
    assert connections_notified == []

    # The demand source dropping the market releases the parked entry.
    await worker.reconcile_demand_once(demand=set())
    assert worker.active_market_ids() == ()
```

> 上面的 `worker_with(...)`、`connections_notified` 需按该文件既有 fixture/fake 组装方式接入（既有文件已有 `FakeRest`、`FakeMarketFeed`、`RecordingPublisher`、`RecordingObservations` 与 on_connection spy；不要新建第二套 fake）。

- [ ] **Step 5: 实现 worker 生命周期分支**

`backend/app/markets/worker.py`：

1. import 增加 `from app.markets.live import MarketFeedClosed, MarketFeedDisconnected`。
2. `_read` 增加分支（放在 `MarketFeedDisconnected` 之前）：

```python
        except MarketFeedClosed:
            # Provider-side normal end (finished market): stop this stream
            # without a gap and without marking the source failed. The entry
            # stays parked until the demand source drops it.
            sub.state = "closed"
```

3. `reconcile_demand_once` 的 reconcile 段跳过已正常关闭的订阅：

```python
        for sub in list(self._subs.values()):
            if sub.state == "closed":
                continue
            if sub.state == "reconnecting":
```

- [ ] **Step 6: 运行测试**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/test_market_live_feed.py tests/test_market_worker.py -q`
Expected: PASS（既有 overflow/gap/reconcile 用例保持不变）

- [ ] **Step 7: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add backend/app/markets/live.py backend/app/markets/worker.py \
        backend/tests/test_market_live_feed.py backend/tests/test_market_worker.py
git commit -m "fix: handle normal market closes and per-connection keepalive"
```

### Task T86.5: 运行时接线（job + coverage + 实时镜像）与端到端证据

**Files:**
- Modify: `backend/app/runtime/daemon.py`、`backend/app/runtime/assembly.py`
- Test: `backend/tests/test_runtime_daemon.py`（追加）、`backend/tests/integration/test_runtime_recovery.py`（追加一条真实 PG 证据）

**Interfaces:**
- Consumes: `MarketQuoteSnapshotJob`、`MarketQuoteSnapshotRepository`、`realtime_quote_record`
- Produces: `LocalRuntimeDaemon` 新增可选参数 `quote_job=None`、`quote_snapshots=None`、`quote_fresh_seconds=300`、`market_snapshot_seconds=120`（默认 None/既有值 ⇒ 既有构造零漂移）

- [ ] **Step 1: 先写失败测试（daemon 层）**

在 `backend/tests/test_runtime_daemon.py` 追加：

```python
class SpyQuoteProjections:
    def __init__(self):
        self.writes = []
        self.fail = False

    async def upsert(self, record):
        if self.fail:
            raise RuntimeError("projection down")
        self.writes.append(record)
        return True


class SpyQuoteJob:
    def __init__(self, coverage):
        self._coverage = coverage
        self.runs = 0

    async def run_once(self):
        self.runs += 1
        return self._coverage


async def test_daemon_runs_the_snapshot_job_at_its_own_interval():
    coverage = MarketQuoteCoverage(generated_at=NOW, candidate=3, attempted=3, fresh_snapshot=3)
    quote_job = SpyQuoteJob(coverage)
    daemon, health = build_daemon(quote_job=quote_job, market_snapshot_seconds=120)

    await daemon.tick_once()
    assert quote_job.runs == 1
    assert health._market_coverage is not None  # persisted on the next persist

    await daemon.tick_once()  # same instant: interval not elapsed
    assert quote_job.runs == 1

    daemon._clock_advance(121)
    await daemon.tick_once()
    assert quote_job.runs == 2


async def test_realtime_hot_books_are_mirrored_into_the_shared_projection():
    projections = SpyQuoteProjections()
    daemon, _health = build_daemon(
        quote_snapshots=projections, hot_book=book_for(MKT_1)
    )

    await daemon.tick_once()

    assert [record.market_id for record in projections.writes] == [MKT_1]
    assert projections.writes[0].source is QuoteSource.REALTIME


async def test_projection_mirror_failure_degrades_health_without_stopping_the_tick():
    projections = SpyQuoteProjections()
    projections.fail = True
    daemon, health = build_daemon(
        quote_snapshots=projections, hot_book=book_for(MKT_1)
    )

    await daemon.tick_once()

    record = health._record(MARKET_SOURCE)
    assert record.status is RuntimeSourceStatus.DEGRADED
    assert record.reason_code == "RUNTIME_ERROR"


async def test_snapshot_lane_never_touches_decision_or_paper():
    decision_spy = SpyDecisionWorker()
    paper_spy = SpyPaper()
    quote_job = SpyQuoteJob(MarketQuoteCoverage(generated_at=NOW, candidate=0))
    daemon, _health = build_daemon(quote_job=quote_job, decision_worker=decision_spy, paper=paper_spy)

    await daemon.tick_once()

    assert decision_spy.sports_calls == [] and decision_spy.book_calls == []
    assert paper_spy.calls == []
    assert daemon._market_worker.active_market_ids() == ()
```

> `build_daemon(...)`、`daemon._clock_advance(...)`、`book_for(...)`、`SpyDecisionWorker`、`SpyPaper` 必须复用该文件既有的 clock/fake 组装方式；如既有 helper 名称不同，按既有名称接入，不要新建平行 helper。

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/test_runtime_daemon.py -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'quote_job'`

- [ ] **Step 3: 实现 daemon 接线**

`backend/app/runtime/daemon.py`：

1. import 增加 `from app.markets.quotes import realtime_quote_record`。
2. `LocalRuntimeDaemon.__init__` 参数追加：

```python
        quote_job: Any = None,
        quote_snapshots: Any = None,
        quote_fresh_seconds: int = 300,
        market_snapshot_seconds: int = 120,
```

3. 构造函数体追加：

```python
        self._quote_job = quote_job
        self._quote_snapshots = quote_snapshots
        self._quote_fresh_seconds = quote_fresh_seconds
```

4. jobs 列表追加（保持既有顺序，snapshot 作业排在 discovery 之后）：

```python
                RuntimeJob(
                    "market_snapshot",
                    timedelta(seconds=market_snapshot_seconds),
                    self._run_market_snapshot,
                ),
```

5. 新方法：

```python
    async def _run_market_snapshot(self) -> None:
        """Run one bounded coverage round and publish its coverage facts.

        The lane writes display quotes only: no prediction, no decision, no
        paper, no WebSocket. A failed round keeps the previous coverage and
        the previous projection rows (the scheduler marks the job degraded).
        """
        if self._quote_job is None:
            return
        coverage = await self._quote_job.run_once()
        self._health.set_market_coverage(coverage)

    async def _mirror_hot_book(self, market_id: str) -> None:
        """Mirror the realtime hot book into the shared projection so pages
        read one precedence rule for both lanes. A missing book writes
        nothing; a store failure degrades health without suppressing the
        just-published decision book."""
        if self._quote_snapshots is None:
            return
        try:
            book = await self._hot_books.get_hot_book(market_id)
        except Exception as exc:  # noqa: BLE001 - isolate the mirror
            await self._health.mark_degraded(MARKET_SOURCE, stable_reason_code(exc))
            return
        try:
            if book is not None:
                await self._quote_snapshots.upsert(
                    realtime_quote_record(
                        book, fresh_seconds=self._quote_fresh_seconds
                    )
                )
        except Exception as exc:  # noqa: BLE001 - isolate the mirror
            await self._health.mark_degraded(MARKET_SOURCE, stable_reason_code(exc))
```

6. `_pump_markets` 的 per-market try 块追加一行（在 `_execute_due_intents` 之后）：

```python
                await self._mirror_hot_book(market_id)
```

- [ ] **Step 4: 实现装配**

`backend/app/runtime/assembly.py`：

1. import 增加：

```python
from app.persistence.market_repositories import (
    MarketQuoteSnapshotRepository,
    MarketRepository,
)  # 把 MarketQuoteSnapshotRepository 追加到既有 import
from app.runtime.market_snapshot import MarketQuoteSnapshotJob
```

2. `build_local_runtime_daemon` 中，在 `market_worker` 构建之后、`daemon` 构建之前加入：

```python
    quote_snapshots = MarketQuoteSnapshotRepository(database)
    quote_job = MarketQuoteSnapshotJob(
        markets=markets,
        projections=quote_snapshots,
        provider=market_provider,
        raw=raw_events,
        catalog=catalog,
        hot_books=market_publisher,
        clock=clock,
        max_markets=live.market_snapshot_max_markets,
        token_batch_size=live.market_snapshot_token_batch_size,
        quote_fresh_seconds=live.market_quote_fresh_seconds,
        realtime_fresh_seconds=settings.p3_market_book_freshness_seconds,
    )
```

3. `LocalRuntimeDaemon(...)` 调用追加：

```python
        quote_job=quote_job,
        quote_snapshots=quote_snapshots,
        quote_fresh_seconds=live.market_quote_fresh_seconds,
        market_snapshot_seconds=live.market_snapshot_seconds,
```

4. `LocalRuntimeDaemonGraph` 增加字段 `quote_snapshots: MarketQuoteSnapshotRepository`（供测试与 status 查询引用），并在返回处传入。

- [ ] **Step 5: 运行 daemon 与装配测试**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/test_runtime_daemon.py tests/test_runtime_daemon_main.py tests/test_runtime_workers.py tests/test_p3_assembly.py -q`
Expected: PASS

- [ ] **Step 6: 真实 PostgreSQL 的接线证据**

在 `backend/tests/integration/test_runtime_recovery.py` 追加一条：

```python
async def test_snapshot_lane_writes_projection_without_touching_the_realtime_roster(...):
    """The coverage lane fills the projection while the decision roster is
    unchanged, and a realtime hot book later takes precedence."""
    ...
    await daemon.tick_once()
    stored = await quote_snapshots.load(market_id)
    assert stored is not None and stored.source is QuoteSource.SNAPSHOT
    assert market_worker.active_market_ids() == ()   # roster unchanged
    ...
```

> 按该文件既有 scratch DB / assembly 构造方式补全（沿用既有 fixture 与 fake provider，不得引入真实网络）。

- [ ] **Step 7: 全量确定性 + infrastructure + ruff**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure and not player_alias_llm_live and not player_directory_e2e_live and not polymarket_live and not local_runtime_live" -q`
Expected: 全部通过

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest -m infrastructure -q`
Expected: 全部通过

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run ruff check app/runtime/market_snapshot.py app/runtime/daemon.py app/runtime/assembly.py app/markets/live.py app/markets/worker.py app/markets/quotes.py app/persistence/market_repositories.py tests/test_market_snapshot_job.py tests/test_market_live_feed.py tests/test_market_worker.py tests/test_runtime_daemon.py tests/integration/test_runtime_recovery.py && uv run ruff format --check app/runtime/market_snapshot.py app/runtime/daemon.py app/runtime/assembly.py app/markets/live.py app/markets/worker.py app/markets/quotes.py app/persistence/market_repositories.py`
Expected: 无输出

- [ ] **Step 8: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add backend/app/runtime/daemon.py backend/app/runtime/assembly.py \
        backend/tests/test_runtime_daemon.py backend/tests/integration/test_runtime_recovery.py
git commit -m "feat: schedule snapshots and mirror realtime books into the projection"
```

### Task T86.6: T86 收口（总控 + 推送）

- [ ] **Step 1: 更新 `CURRENT.md`**：T86 `done` + 实际证据（配置边界测试、job 测试计数、feed/worker 生命周期测试、daemon 接线测试、infrastructure 计数），下一步指向 T87。

- [ ] **Step 2: 更新 `ROADMAP.md`**：T86 行 `done` + 实现提交；T87 行保持 `planned`。

- [ ] **Step 3: 提交并推送**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add CURRENT.md ROADMAP.md
git commit -m "docs: close T86 snapshot coverage and stream hardening"
git push origin main
```

---

# T87 — Explicit Market and Opportunity Semantics

**交付物**：Markets/Opportunities 的 REST/SSE/Next 契约显式化 —— active link、quote state/source/as-of、model availability、真实 decision action 四者分离；旧「null action 当 MARKET_ONLY」的推断彻底删除；机会端点带 aggregate availability。

**不改变**：Opportunity 行内容（仍只有 `BUY`/`WAIT`）、Match Workbench 与 Paper 端点、SSE cursor 语义、公共面零 provider identity。

### Task T87.1: 后端 DTO 与 assemble 语义

**Files:**
- Modify: `backend/app/api/schemas.py`、`backend/app/api/routes.py`、`backend/app/service.py`
- Modify: `backend/app/main.py`、`backend/app/runtime/assembly.py`（查询服务接线）
- Test: `backend/tests/test_p3_api.py`（追加）、`backend/tests/test_market_stream_api.py`（追加）、`backend/tests/integration/test_p3_query_service.py`（追加）

**Interfaces:**
- Produces: `MarketQuoteDto`；`MarketSummaryDto.{quote, model_availability, decision_action}`（删除 `model_covered`、`action` 与扁平 quote 字段）；`OpportunityAvailabilityDto`；`OpportunityListResponse.availability`；`P3QueryService.opportunity_view()`；`markets_snapshot()` 增加 `availability` reason

- [ ] **Step 1: 先写失败测试（契约）**

在 `backend/tests/integration/test_p3_query_service.py` 追加：

```python
async def test_market_rows_expose_explicit_quote_and_model_semantics(
    database: Database,
) -> None:
    """Active link, quote state, model availability and the real decision
    action are separate facts; none of them is inferred from a null action."""
    seeded = await _seed(database)
    market_id = seeded["market_id"]
    queries = P3QueryService(
        database=database,
        markets=MarketRepository(database),
        paper=PaperLedgerRepository(database),
        hot_books=None,
        quote_snapshots=MarketQuoteSnapshotRepository(database),
        snapshot_fresh_seconds=300,
        realtime_fresh_seconds=5,
    )

    page = await queries.markets(page=1, page_size=50)
    summary = next(item for item in page.markets if item.market_id == market_id)
    assert summary.match_id == seeded["match_id"]
    assert summary.model_availability == "available"
    assert summary.decision_action == "buy"          # from the real observation
    # No stored quote and no hot book yet: an explicit `unavailable`, never a zero.
    assert summary.quote.state == "unavailable"
    assert summary.quote.source is None and summary.quote.as_of is None
    assert summary.quote.outcome_asks is None

    # A stored durable snapshot becomes a real snapshot quote with its own time.
    repo = MarketQuoteSnapshotRepository(database)
    await repo.upsert(
        QuoteSnapshotRecord(
            market_id=market_id,
            source=QuoteSource.SNAPSHOT,
            state=QuoteState.SNAPSHOT,
            book_hash="stored",
            as_of=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(seconds=300),
            outcome_bids=("0.58", "0.40"),
            outcome_asks=("0.60", "0.42"),
            spread="0.0200",
            depth_usd="306.00",
        )
    )
    page = await queries.markets(page=1, page_size=50)
    summary = next(item for item in page.markets if item.market_id == market_id)
    assert summary.quote.state == "snapshot"
    assert summary.quote.source == "snapshot"
    assert summary.quote.as_of is not None
    assert summary.quote.outcome_asks == ("0.60", "0.42")


async def test_unmapped_market_has_no_action_and_no_fabricated_navigation(
    database: Database,
) -> None:
    seeded = await _seed(database)
    markets = MarketRepository(database)
    market_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev87_{uuid4().hex[:10]}",
        condition_id=f"cond87_{uuid4().hex}",
    )
    await markets.save_market(make_market(market_id, match_id=None))
    queries = P3QueryService(
        database=database, markets=markets, paper=PaperLedgerRepository(database),
        hot_books=None, quote_snapshots=MarketQuoteSnapshotRepository(database),
        snapshot_fresh_seconds=300, realtime_fresh_seconds=5,
    )

    page = await queries.markets(page=1, page_size=50)
    summary = next(item for item in page.markets if item.market_id == market_id)
    assert summary.match_id is None
    assert summary.decision_action is None            # never inferred MARKET_ONLY
    assert summary.model_availability == "not_evaluated"
    assert seeded["market_id"] != market_id


async def test_opportunity_view_explains_the_unpromoted_empty_state(
    database: Database,
) -> None:
    seeded = await _seed(database)
    markets = MarketRepository(database)
    # A main-tour linked market whose model is explicitly unpromoted.
    unpromoted = make_observation(
        seeded["match_id"], seeded["market_id"], observation_version=5
    ).model_copy(
        update={
            "action": DecisionAction.NO_BET,
            "reason_code": "MODEL_UNPROMOTED",
            "quote": None,
            "conservative_net_edge": None,
        }
    )
    await markets.save_decision_observation(unpromoted)
    queries = P3QueryService(
        database=database, markets=markets, paper=PaperLedgerRepository(database),
        hot_books=None, quote_snapshots=MarketQuoteSnapshotRepository(database),
        snapshot_fresh_seconds=300, realtime_fresh_seconds=5,
    )

    rows, availability = await queries.opportunity_view()
    assert availability.reason in {"ELIGIBLE_UNPROMOTED", "HAS_OPPORTUNITIES"}
    assert availability.model_status in {"not_promoted", "unknown"}
    if availability.reason == "ELIGIBLE_UNPROMOTED":
        assert all(row.action in ("buy", "wait") for row in rows)
```

在 `backend/tests/test_market_stream_api.py` 追加对 ready 帧的断言：

```python
    assert payload["availability"] in {
        "HAS_OPPORTUNITIES",
        "ELIGIBLE_UNPROMOTED",
        "NO_ELIGIBLE_ACTION",
        "NO_COVERED_MARKET",
        "DECISION_GAP",
    }
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/integration/test_p3_query_service.py -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'quote_snapshots'`

- [ ] **Step 3: 新增 DTO**

`backend/app/api/schemas.py`：把 `MarketSummaryDto` 整体替换为：

```python
class MarketQuoteDto(BaseModel):
    """One market's display quote: state, source, time and independent
    per-outcome levels. A missing side stays None — never a zero."""

    state: str  # realtime | snapshot | partial | no_liquidity | unavailable | stale | limited
    source: str | None = None  # realtime | snapshot | None
    as_of: datetime | None = None
    outcome_bids: tuple[str | None, str | None] | None = None
    outcome_asks: tuple[str | None, str | None] | None = None
    best_bid: tuple[str, str] | None = None
    best_ask: tuple[str, str] | None = None
    spread: str | None = None
    depth_usd: str | None = None


class MarketSummaryDto(BaseModel):
    market_id: str
    # Only ever the ACTIVE `market_match_links` match; navigable when set.
    match_id: str | None = None
    question: str | None = None
    status: str
    tournament_name: str | None = None
    tier: str | None = None
    gender: str | None = None
    phase: str | None = None
    # available | eligible_unpromoted | out_of_scope | not_evaluated
    model_availability: str = "not_evaluated"
    # Only a real DecisionObservation may set this; a null action is not
    # MARKET_ONLY and the pages must never infer one from the other.
    decision_action: str | None = None
    reason_code: str | None = None
    player_ids: tuple[str, str] | None = None
    player_names: tuple[str, str] | None = None
    model_probability: float | None = None
    quote: MarketQuoteDto
    is_stale: bool = False
    has_gap: bool = False
    as_of: datetime | None = None
```

在 `OpportunityDto` 之后加入：

```python
class OpportunityAvailabilityDto(BaseModel):
    """Why the opportunities view currently looks the way it does.

    A stable reason code only: the page owns the copy. NEVER used to
    synthesize an action — an unpromoted model produces zero rows here.
    """

    reason: str  # HAS_OPPORTUNITIES | ELIGIBLE_UNPROMOTED | NO_ELIGIBLE_ACTION | NO_COVERED_MARKET | DECISION_GAP
    model_status: str  # not_promoted | promoted | unknown
```

并把 `OpportunityListResponse` 改为（该响应模型在 `backend/app/api/schemas.py` 中定义）：

```python
class OpportunityListResponse(BaseModel):
    data: list[OpportunityDto]
    availability: OpportunityAvailabilityDto | None = None
```

- [ ] **Step 4: 服务侧语义**

`backend/app/service.py` 顶部加入：

```python
from app.markets.quotes import DisplayQuote, best_levels, display_quote, outcome_levels
from app.markets.quotes import QuoteSource, QuoteState  # 按实际使用精确 import

UNPROMOTED_REASONS = frozenset(
    {"MODEL_UNPROMOTED", "PROMOTION_NOT_GRANTED", "ARTIFACT_INVALID"}
)
MAIN_TOUR_TIERS = frozenset({"atp", "wta"})


def p3_model_availability(*, tier, prediction, observation) -> str:
    """Explicit model availability for one market row (spec §6.1)."""
    if tier is None:
        return "not_evaluated"          # no active link: nothing was evaluated
    if tier not in MAIN_TOUR_TIERS:
        return "out_of_scope"           # deliberately outside the model domain
    if prediction is not None:
        if prediction.availability.value in ("available", "degraded"):
            return "available"
        if prediction.availability.value in ("unpromoted", "unavailable"):
            return "eligible_unpromoted"
    if observation is not None and (observation.reason_code or "") in UNPROMOTED_REASONS:
        return "eligible_unpromoted"
    return "not_evaluated"
```

`P3QueryService.__init__` 追加参数与字段：

```python
    def __init__(
        self,
        *,
        database,
        markets,
        paper,
        hot_books=None,
        quote_snapshots=None,
        snapshot_fresh_seconds: int = 300,
        realtime_fresh_seconds: int = 5,
    ) -> None:
        ...
        self._quote_snapshots = quote_snapshots
        self._snapshot_fresh_seconds = snapshot_fresh_seconds
        self._realtime_fresh_seconds = realtime_fresh_seconds
```

`markets()` 中把 prediction/hot-book 段替换为（其余不动）：

```python
        stored_quotes = (
            await self._quote_snapshots.load_many([row.market_id for row in market_rows])
            if self._quote_snapshots is not None
            else {}
        )
        ...
            quote = display_quote(
                hot_book=hot_books.get(row.market_id),
                snapshot=stored_quotes.get(row.market_id),
                now=datetime.now(UTC),
                realtime_fresh_seconds=self._realtime_fresh_seconds,
                snapshot_fresh_seconds=self._snapshot_fresh_seconds,
            )
            ...
                model_availability=p3_model_availability(
                    tier=match_facts.get("tier"),
                    prediction=prediction,
                    observation=observation,
                ),
                decision_action=(
                    observation.action.value if observation is not None else None
                ),
                reason_code=(observation.reason_code if observation is not None else None),
                quote=MarketQuoteDto(
                    state=quote.state.value,
                    source=quote.source.value if quote.source is not None else None,
                    as_of=quote.as_of,
                    outcome_bids=quote.outcome_bids,
                    outcome_asks=quote.outcome_asks,
                    best_bid=quote.best_bid,
                    best_ask=quote.best_ask,
                    spread=quote.spread,
                    depth_usd=quote.depth_usd,
                ),
                is_stale=(
                    (observation.is_stale if observation is not None else False)
                    or quote.state is QuoteState.STALE
                ),
                has_gap=observation.has_gap if observation is not None else False,
```

（`model_covered`、旧的扁平 `action`/`best_bid`/`outcome_bids`/`spread`/`depth_usd` 字段与对应的 `_outcome_levels` 调用从该 DTO 构造中删除；`_best_levels`/`_outcome_levels` 的委托保持不变，供 `match_decision`/`_position_dtos` 继续使用。）

`opportunities()` 之后加入：

```python
    async def opportunity_view(self):
        """Rows plus the aggregate availability reason (spec §6.2).

        `opportunities()` keeps returning the plain row list for the Chat
        tools; the page uses this view so an empty tab can explain itself.
        """
        from app.api.schemas import OpportunityAvailabilityDto

        rows = await self.opportunities()
        if rows:
            return rows, OpportunityAvailabilityDto(
                reason="HAS_OPPORTUNITIES", model_status="unknown"
            )
        observations = await self._markets.latest_decision_observations()
        unpromoted = any(
            (observation.reason_code or "") in UNPROMOTED_REASONS
            for observation in observations
        )
        if unpromoted:
            return rows, OpportunityAvailabilityDto(
                reason="ELIGIBLE_UNPROMOTED", model_status="not_promoted"
            )
        if observations and all(
            observation.is_stale or observation.has_gap
            for observation in observations
        ):
            return rows, OpportunityAvailabilityDto(
                reason="DECISION_GAP", model_status="unknown"
            )
        overviews = await self._markets.list_market_overviews()
        linked = [row for row in overviews if row.active_match_id]
        facts = await self._match_facts([row.active_match_id for row in linked])
        covered = [
            row
            for row in linked
            if facts.get(row.active_match_id, {}).get("tier") in MAIN_TOUR_TIERS
        ]
        if not covered:
            return rows, OpportunityAvailabilityDto(
                reason="NO_COVERED_MARKET", model_status="unknown"
            )
        predictions = await self._markets.latest_predictions_for_matches(
            [row.active_match_id for row in covered]
        )
        promoted = any(
            snapshot.availability.value in ("available", "degraded")
            for snapshot in predictions.values()
        )
        return rows, OpportunityAvailabilityDto(
            reason="NO_ELIGIBLE_ACTION", model_status="promoted" if promoted else "unknown"
        )
```

`markets_snapshot()` 的返回字典追加：

```python
            "availability": availability.reason,
```

并在该方法内先取 availability：

```python
        _, availability = await self.opportunity_view()
```

（`markets_snapshot` 因此多打两次批量查询，仍是常数条数。）

- [ ] **Step 5: 路由与装配**

`backend/app/api/routes.py`：

```python
@router.get("/markets/opportunities", response_model=OpportunityListResponse)
async def market_opportunities(queries=Depends(get_p3_queries)):
    rows, availability = await queries.opportunity_view()
    return OpportunityListResponse(data=list(rows), availability=availability)
```

`backend/app/main.py` 的 `P3QueryService(...)` 追加：

```python
                quote_snapshots=MarketQuoteSnapshotRepository(database),
                snapshot_fresh_seconds=settings.local_runtime_market_quote_fresh_seconds,
                realtime_fresh_seconds=settings.p3_market_book_freshness_seconds,
```

（并 import `MarketQuoteSnapshotRepository`。）

`backend/app/runtime/assembly.py` 的 `P3QueryService(...)` 追加：

```python
        quote_snapshots=MarketQuoteSnapshotRepository(database),
        snapshot_fresh_seconds=settings.local_runtime_market_quote_fresh_seconds,
        realtime_fresh_seconds=settings.p3_market_book_freshness_seconds,
```

- [ ] **Step 6: 运行后端契约与回归**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/test_p3_api.py tests/test_market_stream_api.py tests/test_p3_chat_tools.py tests/integration/test_p3_query_service.py -q`
Expected: PASS（Chat 工具仍走 `opportunities()` 行列表，形状不变）

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure and not player_alias_llm_live and not player_directory_e2e_live and not polymarket_live and not local_runtime_live" -q`
Expected: 全部通过

- [ ] **Step 7: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add backend/app/api/schemas.py backend/app/api/routes.py backend/app/service.py \
        backend/app/main.py backend/app/runtime/assembly.py \
        backend/tests/test_p3_api.py backend/tests/test_market_stream_api.py \
        backend/tests/integration/test_p3_query_service.py
git commit -m "feat: expose explicit quote, model and decision semantics"
```

### Task T87.2: 前端 typed transport 与 view model

**Files:**
- Modify: `frontend/lib/api/p3-types.ts`、`frontend/lib/api/client.ts`、`frontend/lib/p3-view-models.ts`
- Modify: `frontend/components/markets/market-row.tsx`、`opportunities-view.tsx`、`markets-state.tsx`（最小接线，完整状态渲染在 T88）
- Test: `frontend/lib/api/p3-types.test.ts`、`frontend/lib/p3-view-models.test.ts`、`frontend/components/markets/markets-page.test.tsx`
- Modify: `frontend/e2e/p3-markets.spec.ts`（只更新 fixture 到新形状，不新增用例）

**Interfaces:**
- Consumes: T87.1 的 DTO 形状
- Produces: `MarketQuoteDto`、`ModelAvailabilityValue`、`OpportunityAvailabilityDto`、`decodeMarketQuote`、`decodeOpportunityList() -> {rows, availability}`、`MarketRowModel.{modelAvailability, decisionAction, quoteLabel, modelAvailabilityLabel, quote}`

> 动手前先按 `frontend/AGENTS.md` 阅读 `frontend/node_modules/next/dist/docs/` 中与本次改动相关的指南（App Router / client component 与数据获取约定），不得依赖训练数据里的 Next.js 约定。

- [ ] **Step 1: 先写失败测试**

在 `frontend/lib/api/p3-types.test.ts` 追加：

```ts
it('decodes the explicit quote, model and decision fields', () => {
  const page = decodeMarketPage({
    data: [
      {
        ...base,
        model_availability: 'eligible_unpromoted',
        decision_action: null,
        quote: {
          state: 'snapshot',
          source: 'snapshot',
          as_of: NOW,
          outcome_bids: ['0.58', '0.40'],
          outcome_asks: ['0.60', '0.42'],
          best_bid: ['ply_a', '0.58'],
          best_ask: ['ply_a', '0.60'],
          spread: '0.0200',
          depth_usd: '306.00',
        },
      },
    ],
    page: 1,
    page_size: 20,
    total: 1,
  })
  expect(page.markets[0].quote.state).toBe('snapshot')
  expect(page.markets[0].model_availability).toBe('eligible_unpromoted')
  expect(page.markets[0].decision_action).toBeNull()
})

it('fails closed on an unknown quote state', () => {
  expect(() =>
    decodeMarketPage({
      data: [{ ...base, quote: { ...quoteFixture, state: 'maybe' } }],
      page: 1,
      page_size: 20,
      total: 1,
    }),
  ).toThrow(P3DecodeError)
})

it('decodes the opportunity availability envelope', () => {
  const view = decodeOpportunityList({
    data: [],
    availability: { reason: 'ELIGIBLE_UNPROMOTED', model_status: 'not_promoted' },
  })
  expect(view.rows).toEqual([])
  expect(view.availability.reason).toBe('ELIGIBLE_UNPROMOTED')
})

it('keeps the availability optional for older payloads', () => {
  const view = decodeOpportunityList({ data: [] })
  expect(view.availability).toBeNull()
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/frontend && pnpm test -- lib/api/p3-types.test.ts`
Expected: FAIL

- [ ] **Step 3: 实现解码器**

`frontend/lib/api/p3-types.ts`：

```ts
const QUOTE_STATES = [
  'realtime',
  'snapshot',
  'partial',
  'no_liquidity',
  'unavailable',
  'stale',
  'limited',
] as const
const QUOTE_SOURCES = ['realtime', 'snapshot'] as const
const MODEL_AVAILABILITIES = [
  'available',
  'eligible_unpromoted',
  'out_of_scope',
  'not_evaluated',
] as const
const OPPORTUNITY_AVAILABILITY_REASONS = [
  'HAS_OPPORTUNITIES',
  'ELIGIBLE_UNPROMOTED',
  'NO_ELIGIBLE_ACTION',
  'NO_COVERED_MARKET',
  'DECISION_GAP',
] as const

export type QuoteStateValue = (typeof QUOTE_STATES)[number]
export type QuoteSourceValue = (typeof QUOTE_SOURCES)[number]
export type ModelAvailabilityValue = (typeof MODEL_AVAILABILITIES)[number]
export type OpportunityAvailabilityReason = (typeof OPPORTUNITY_AVAILABILITY_REASONS)[number]

export type MarketQuoteDto = {
  state: QuoteStateValue
  source: QuoteSourceValue | null
  as_of: string | null
  outcome_bids: [string | null, string | null] | null
  outcome_asks: [string | null, string | null] | null
  best_bid: [string, string] | null
  best_ask: [string, string] | null
  spread: string | null
  depth_usd: string | null
}

export function decodeMarketQuote(value: unknown, path: string): MarketQuoteDto {
  const item = raw(value, path)
  return {
    state: oneOf(item.state, QUOTE_STATES, `${path}.state`),
    source: oneOfOrNull(item.source, QUOTE_SOURCES, `${path}.source`),
    as_of: strOrNull(item.as_of, `${path}.as_of`),
    outcome_bids: nullableLevelPair(item.outcome_bids, `${path}.outcome_bids`),
    outcome_asks: nullableLevelPair(item.outcome_asks, `${path}.outcome_asks`),
    best_bid: levelTuple(item.best_bid, `${path}.best_bid`),
    best_ask: levelTuple(item.best_ask, `${path}.best_ask`),
    spread: decimalOrNull(item.spread, `${path}.spread`),
    depth_usd: decimalOrNull(item.depth_usd, `${path}.depth_usd`),
  }
}
```

`decodeMarketSummary` 改为（替换 `model_covered`/`action`/扁平报价字段）：

```ts
    model_availability: oneOf(
      item.model_availability ?? 'not_evaluated',
      MODEL_AVAILABILITIES,
      `${path}.model_availability`,
    ),
    decision_action: oneOfOrNull(
      item.decision_action,
      DECISION_ACTIONS,
      `${path}.decision_action`,
    ) as DecisionActionValue | null,
    reason_code: strOrNull(item.reason_code, `${path}.reason_code`),
    quote: decodeMarketQuote(item.quote, `${path}.quote`),
```

`decodeOpportunityList` 改为：

```ts
export function decodeOpportunityList(body: unknown): {
  rows: OpportunityDto[]
  availability: OpportunityAvailabilityDto | null
} {
  const envelope = raw(body, 'opportunities')
  const availability = envelope.availability
  return {
    rows: rawList(envelope.data, 'opportunities.data').map((item, index) =>
      decodeOpportunity(item, `opportunities.data[${index}]`),
    ),
    availability:
      availability === undefined || availability === null
        ? null
        : decodeOpportunityAvailability(availability, 'opportunities.availability'),
  }
}
```

并新增：

```ts
export function decodeOpportunityAvailability(
  value: unknown,
  path: string,
): OpportunityAvailabilityDto {
  const item = raw(value, path)
  return {
    reason: oneOf(item.reason, OPPORTUNITY_AVAILABILITY_REASONS, `${path}.reason`),
    model_status: oneOf(
      item.model_status,
      ['not_promoted', 'promoted', 'unknown'] as const,
      `${path}.model_status`,
    ),
  }
}
```

`decodeMarketsSnapshot` 追加 `availability: oneOfOrDefault(...)`（缺省时保持既有 fixture 可用，但后端始终发送）。

- [ ] **Step 4: view model**

`frontend/lib/p3-view-models.ts`：

```ts
const QUOTE_STATE_LABELS: Record<QuoteStateValue, string> = {
  realtime: '实时盘口',
  snapshot: '快照报价',
  partial: '部分报价',
  no_liquidity: '暂无挂单',
  unavailable: '报价暂不可用',
  stale: '最后可信报价已过期',
  limited: '覆盖受限 · 等待下一轮',
}

const TIME_AWARE_QUOTE_STATES: QuoteStateValue[] = ['snapshot', 'partial']

const MODEL_AVAILABILITY_LABELS: Record<ModelAvailabilityValue, string | null> = {
  available: '主巡覆盖',
  eligible_unpromoted: '模型未晋升 · 不产生 BUY/WAIT',
  out_of_scope: null, // low tiers carry no negative "uncovered" label
  not_evaluated: '待下一决策周期',
}

function quoteLabel(state: QuoteStateValue, asOf: string | null, now: Date): string {
  const base = QUOTE_STATE_LABELS[state]
  if (!TIME_AWARE_QUOTE_STATES.includes(state) || asOf === null) return base
  return `${base} · ${formatRelativeTime(asOf, now)}`
}
```

（`formatRelativeTime` 用既有 `formatFreshness` 的同一时间格式实现；如该文件已有等价函数则复用它，不新增第二套。）

`MarketRowModel` 改为携带：

```ts
  modelAvailability: ModelAvailabilityValue
  modelAvailabilityLabel: string | null
  decisionAction: DecisionActionValue | null
  quoteLabel: string
  quoteState: QuoteStateValue
  playerOneBid: number | null
  playerTwoBid: number | null
  playerOneAsk: number | null
  playerTwoAsk: number | null
  spread: number | null
  depth: number | null
```

`toMarketRow` 相应重写：不再有 `covered`、不再有 `state: dto.action ?? 'market_only'`；`href` 仍只在 `dto.match_id` 存在时给出。

- [ ] **Step 5: 最小组件接线**

`frontend/components/markets/market-row.tsx`：`MarketRowData` 换用新字段；徽章区改为

```tsx
        <div className="flex items-center justify-between gap-2 md:justify-end">
          {market.decisionAction !== null ? (
            <DecisionStatusBadge state={market.decisionAction} overlay={overlay} />
          ) : (
            <Badge variant="outline" data-quote-state={market.quoteState}>
              {market.quoteLabel}
            </Badge>
          )}
          {market.href !== null ? (
            <ArrowRight aria-hidden="true" className="size-4 shrink-0 text-foreground transition-transform group-hover:translate-x-0.5" />
          ) : null}
        </div>
```

并在模型列渲染 `market.modelAvailabilityLabel`（`null` 时不渲染该行说明）。

`frontend/components/markets/markets-state.tsx`：

```ts
      const view = await listMarketOpportunities()
      ...
      setOpportunities({ status: 'ready', errorCode: null, rows: view.rows.map(...), availability: view.availability })
```

（`OpportunitiesState` 增加 `availability: OpportunityAvailabilityDto | null`；`opportunities-view.tsx` 在 T88 消费它。）

`frontend/e2e/p3-markets.spec.ts`：把 `MARKETS.data[*]` 与 `OPPORTUNITIES` 更新为新形状（`model_availability`、`decision_action`、`quote` 对象），`SSE_READY` 增加 `"availability":"ELIGIBLE_UNPROMOTED"`。**只改 fixture，不新增用例**。

- [ ] **Step 6: 运行前端门**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/frontend && pnpm test && pnpm typecheck && pnpm build`
Expected: 全部通过（`pnpm test` 计数按新增用例增加）

Run: `cd /Users/daibin/Documents/Coding/TennixAI/frontend && pnpm test:e2e --grep "P3 production"`
Expected: PASS（形状更新后既有断言仍成立）

- [ ] **Step 7: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add frontend/lib/api/p3-types.ts frontend/lib/api/client.ts frontend/lib/p3-view-models.ts \
        frontend/components/markets/market-row.tsx frontend/components/markets/opportunities-view.tsx \
        frontend/components/markets/markets-state.tsx frontend/lib/api/p3-types.test.ts \
        frontend/lib/p3-view-models.test.ts frontend/components/markets/markets-page.test.tsx \
        frontend/e2e/p3-markets.spec.ts
git commit -m "feat: decode explicit market quote and availability semantics"
```

### Task T87.3: T87 收口（总控 + 推送）

- [ ] **Step 1: 更新 `CURRENT.md`**：T87 `done` + 实际证据（后端契约测试、integration、前端 vitest/typecheck/build 计数），下一步指向 T88。
- [ ] **Step 2: 更新 `ROADMAP.md`**：T87 行 `done` + 两个实现提交。
- [ ] **Step 3: 提交并推送**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add CURRENT.md ROADMAP.md
git commit -m "docs: close T87 explicit market semantics"
git push origin main
```

---

# T88 — Truthful Markets and Opportunity Rendering

**交付物**：保持 v0 几何不变的前提下，全部市场按真实 quote 状态渲染（含逐边缺失的 `—`）、低级别赛事无负向模型标签、未晋升机会空态讲清原因、内部导航只在有 active link 时出现、双视口功能与受审视觉门。

**不改变**：`?preview=p3` 冻结原型（52 张基线是视觉真源）、布局几何与断点、任何交易 CTA。

### Task T88.1: 全部市场行与空态渲染

**Files:**
- Modify: `frontend/components/markets/market-row.tsx`、`frontend/components/markets/opportunities-view.tsx`、`frontend/components/markets/markets-state.tsx`
- Test: `frontend/components/markets/markets-page.test.tsx`、`frontend/lib/p3-view-models.test.ts`

**Interfaces:**
- Consumes: T87.2 的 `MarketRowModel`、`OpportunitiesState.availability`
- Produces: 用户可见的状态标签与空态文案（本任务的核心交付物）

- [ ] **Step 1: 先写失败测试（组件层）**

在 `frontend/components/markets/markets-page.test.tsx` 追加：

```tsx
it('renders a snapshot quote with its own time and both real asks', async () => {
  marketsMock.mockResolvedValue(pageWith([
    marketDto({
      quote: quote({ state: 'snapshot', source: 'snapshot', as_of: minutesAgo(2) }),
    }),
  ]))
  render(<MarketsWorkspace initialView="all" />)
  expect(await screen.findByText(/快照报价 · 2 分钟前/)).toBeInTheDocument()
  expect(screen.getByText('60.0%')).toBeInTheDocument()   // player one ask
  expect(screen.getByText('42.0%')).toBeInTheDocument()   // player two ask
})

it('never hides one outcome because the other side is missing', async () => {
  marketsMock.mockResolvedValue(pageWith([
    marketDto({ quote: quote({ state: 'partial', outcome_asks: ['0.60', null] }) }),
  ]))
  render(<MarketsWorkspace initialView="all" />)
  expect(await screen.findByText(/部分报价/)).toBeInTheDocument()
  expect(screen.getByText('60.0%')).toBeInTheDocument()
  expect(screen.getAllByText('—').length).toBeGreaterThan(0)
})

it('labels no-liquidity, stale and unavailable markets explicitly', async () => {
  marketsMock.mockResolvedValue(pageWith([
    marketDto({ market_id: 'mkt_empty', quote: quote({ state: 'no_liquidity' }) }),
    marketDto({ market_id: 'mkt_stale', quote: quote({ state: 'stale' }) }),
    marketDto({ market_id: 'mkt_gone', quote: quote({ state: 'unavailable', source: null, as_of: null }) }),
  ]))
  render(<MarketsWorkspace initialView="all" />)
  expect(await screen.findByText('暂无挂单')).toBeInTheDocument()
  expect(screen.getByText('最后可信报价已过期')).toBeInTheDocument()
  expect(screen.getByText('报价暂不可用')).toBeInTheDocument()
})

it('shows no negative model label for low-tier markets', async () => {
  marketsMock.mockResolvedValue(pageWith([
    marketDto({ tier: 'challenger', model_availability: 'out_of_scope' }),
  ]))
  render(<MarketsWorkspace initialView="all" />)
  await screen.findByText('E2E Challenger Moneyline')
  expect(screen.queryByText(/未覆盖/)).not.toBeInTheDocument()
  expect(screen.queryByText(/不伪造模型值/)).not.toBeInTheDocument()
})

it('explains an unpromoted model instead of showing an unexplained empty tab', async () => {
  opportunitiesMock.mockResolvedValue({
    rows: [],
    availability: { reason: 'ELIGIBLE_UNPROMOTED', model_status: 'not_promoted' },
  })
  render(<MarketsWorkspace initialView="opportunities" />)
  expect(await screen.findByText('模型尚未完成验证')).toBeInTheDocument()
  expect(
    screen.getByText('模型尚未完成验证，当前不生成 BUY / WAIT；全部市场的真实报价仍可查看。'),
  ).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /查看全部市场/ })).toHaveAttribute(
    'href',
    expect.stringContaining('view=all'),
  )
})

it('explains each other empty reason with its own copy', async () => {
  for (const [reason, copy] of [
    ['NO_ELIGIBLE_ACTION', '当前没有满足策略门的机会。'],
    ['NO_COVERED_MARKET', '当前没有可评估的主巡单打市场。'],
    ['DECISION_GAP', '决策数据正在恢复，暂不生成新机会。'],
  ] as const) {
    opportunitiesMock.mockResolvedValue({
      rows: [],
      availability: { reason, model_status: 'unknown' },
    })
    const { unmount } = render(<MarketsWorkspace initialView="opportunities" />)
    expect(await screen.findByText(copy)).toBeInTheDocument()
    unmount()
  }
})

it('links only rows with an active match link', async () => {
  marketsMock.mockResolvedValue(pageWith([
    marketDto({ market_id: 'mkt_linked', match_id: 'mat_1' }),
    marketDto({ market_id: 'mkt_free', match_id: null, question: 'Unlinked moneyline' }),
  ]))
  render(<MarketsWorkspace initialView="all" />)
  expect(await screen.findByRole('link', { name: /查看 E2E Alpha vs\. E2E Beta 市场/ })).toHaveAttribute(
    'href',
    '/matches/mat_1',
  )
  expect(screen.queryByRole('link', { name: /Unlinked moneyline 市场/ })).not.toBeInTheDocument()
  expect(screen.getByText('Unlinked moneyline')).toBeInTheDocument()
})
```

> `marketDto(...)`/`quote(...)`/`pageWith(...)`/`minutesAgo(...)` 按该文件既有 fixture 工厂风格补一个最小的 builder（放在文件顶部，与既有 `opportunityDto()` 并列），不得引入第二套 mock 结构。

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/frontend && pnpm test -- components/markets/markets-page.test.tsx`
Expected: FAIL

- [ ] **Step 3: 实现空态文案表**

在 `frontend/components/markets/opportunities-view.tsx` 加入（保持文件既有的导出与命名风格）：

```tsx
export const OPPORTUNITY_EMPTY_STATES: Record<
  OpportunityAvailabilityReason,
  { title: string; body: string }
> = {
  HAS_OPPORTUNITIES: {
    title: '暂无符合门槛的机会',
    body: '覆盖市场仍在监测中；下一次通过 hard gate 的 BUY 或 WAIT 会出现在这里。',
  },
  ELIGIBLE_UNPROMOTED: {
    title: '模型尚未完成验证',
    body: '模型尚未完成验证，当前不生成 BUY / WAIT；全部市场的真实报价仍可查看。',
  },
  NO_ELIGIBLE_ACTION: {
    title: '当前没有机会',
    body: '当前没有满足策略门的机会。',
  },
  NO_COVERED_MARKET: {
    title: '暂无可评估市场',
    body: '当前没有可评估的主巡单打市场。',
  },
  DECISION_GAP: {
    title: '决策数据恢复中',
    body: '决策数据正在恢复，暂不生成新机会。',
  },
}
```

在 `markets-state.tsx` 的机会空态分支中改为按 `data.opportunities.availability?.reason ?? 'HAS_OPPORTUNITIES'` 取文案，并在 `ELIGIBLE_UNPROMOTED` 时给出通往全部市场的入口：

```tsx
                    <Button variant="outline" asChild={false} onClick={() => selectView('all')}>
                      查看全部市场
                    </Button>
```

> 若 `Button` 不支持 `asChild`，用该文件既有的 `Button` + `onClick={() => selectView('all')}` 写法（与既有「重置筛选」按钮一致），不要引入新的按钮原语。

- [ ] **Step 4: 运行组件测试**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/frontend && pnpm test -- components/markets/markets-page.test.tsx lib/p3-view-models.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add frontend/components/markets/market-row.tsx frontend/components/markets/opportunities-view.tsx \
        frontend/components/markets/markets-state.tsx frontend/components/markets/markets-page.test.tsx \
        frontend/lib/p3-view-models.test.ts
git commit -m "feat: render truthful market quotes and opportunity empty states"
```

### Task T88.2: 双视口 Playwright 功能门

**Files:**
- Modify: `frontend/e2e/p3-markets.spec.ts`

**Interfaces:**
- Consumes: T88.1 的文案与标签
- Produces: 桌面与移动两套新场景断言

- [ ] **Step 1: 把 fixture 变成可替换的 per-test payload**

在 `frontend/e2e/p3-markets.spec.ts` 中把 `MARKETS`/`OPPORTUNITIES` 改成模块级可变对象，并让 `interceptP3` 读取它们：

```ts
let MARKETS: MarketPagePayload = marketsPayload(defaultMarketRows())
let OPPORTUNITIES: OpportunityPayload = opportunitiesPayload([...])
```

并加一个 helper：

```ts
async function showMarkets(page: Page, rows: MarketRowPayload[]) {
  MARKETS = marketsPayload(rows)
  await interceptP3(page)
  await page.goto('/markets?view=all')
  await page.getByRole('heading', { name: '市场决策支持' }).waitFor()
}
```

- [ ] **Step 2: 新增场景（同时覆盖 desktop 与 mobile 两个 project）**

```ts
  test('all markets show a real snapshot quote with its own time', async ({ page }) => {
    await showMarkets(page, [
      row({ market_id: 'mkt_snap', quote: { state: 'snapshot', source: 'snapshot', as_of: minutesAgo(2) } }),
    ])
    await expect(page.getByText(/快照报价/)).toBeVisible()
    await expect(page.getByText('57.0%')).toBeVisible()
    await expect(page.getByText(/分钟前/)).toBeVisible()
  })

  test('partial, no-liquidity, stale and unavailable states stay distinct', async ({ page }) => {
    await showMarkets(page, [
      row({ market_id: 'mkt_partial', quote: { state: 'partial', outcome_asks: ['0.60', null] } }),
      row({ market_id: 'mkt_empty', quote: { state: 'no_liquidity' } }),
      row({ market_id: 'mkt_stale', quote: { state: 'stale' } }),
      row({ market_id: 'mkt_gone', quote: { state: 'unavailable', source: null, as_of: null } }),
    ])
    await expect(page.getByText(/部分报价/)).toBeVisible()
    await expect(page.getByText('暂无挂单')).toBeVisible()
    await expect(page.getByText('最后可信报价已过期')).toBeVisible()
    await expect(page.getByText('报价暂不可用')).toBeVisible()
  })

  test('low-tier markets keep quotes and carry no negative model label', async ({ page }) => {
    await showMarkets(page, [
      row({ market_id: 'mkt_challenger', tier: 'challenger', model_availability: 'out_of_scope', quote: { state: 'snapshot', source: 'snapshot', as_of: minutesAgo(1) } }),
    ])
    await expect(page.getByText('Challenger')).toBeVisible()
    await expect(page.getByText(/快照报价/)).toBeVisible()
    await expect(page.getByText(/未覆盖/)).toHaveCount(0)
    await expect(page.getByText(/不伪造模型值/)).toHaveCount(0)
  })

  test('row navigation follows the active link only', async ({ page }) => {
    await showMarkets(page, [
      row({ market_id: 'mkt_linked', match_id: 'mat_e2e_1' }),
      row({ market_id: 'mkt_free', match_id: null, question: 'E2E Unlinked Moneyline', tier: 'itf' }),
    ])
    await expect(page.getByRole('link', { name: /查看 E2E Alpha vs\. E2E Beta 市场/ })).toHaveAttribute('href', '/matches/mat_e2e_1')
    await expect(page.getByText('E2E Unlinked Moneyline')).toBeVisible()
    await expect(page.getByRole('link', { name: /E2E Unlinked Moneyline 市场/ })).toHaveCount(0)
  })

  test('the opportunities tab explains an unpromoted model', async ({ page }) => {
    OPPORTUNITIES = opportunitiesPayload([], {
      reason: 'ELIGIBLE_UNPROMOTED',
      model_status: 'not_promoted',
    })
    await interceptP3(page)
    await page.goto('/markets?view=opportunities')
    await expect(page.getByText('模型尚未完成验证')).toBeVisible()
    await expect(page.getByText(/当前不生成 BUY \/ WAIT/)).toBeVisible()
    await expect(page.getByText('BUY', { exact: true })).toHaveCount(0)
  })

  test('a real actionable opportunity still renders as BUY', async ({ page }) => {
    await interceptP3(page)
    await page.goto('/markets?view=opportunities')
    await expect(page.getByRole('link', { name: /查看 E2E Alpha vs\. E2E Beta 的 buy 决策/ })).toBeVisible()
  })
```

并在 `P3 production mobile` describe 中加一条与桌面同源的检查：

```ts
  test('mobile keeps the quote labels and the unpromoted empty state legible', async ({ page }) => {
    await showMarkets(page, [row({ market_id: 'mkt_snap', quote: { state: 'snapshot', source: 'snapshot', as_of: minutesAgo(2) } })])
    await expect(page.getByText(/快照报价/)).toBeVisible()
    OPPORTUNITIES = opportunitiesPayload([], { reason: 'ELIGIBLE_UNPROMOTED', model_status: 'not_promoted' })
    await page.goto('/markets?view=opportunities')
    await expect(page.getByText('模型尚未完成验证')).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
  })
```

- [ ] **Step 3: 运行功能 lane**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/frontend && pnpm test:e2e:functional`
Expected: 全部通过（新用例计入 desktop + mobile 两个 project）

- [ ] **Step 4: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add frontend/e2e/p3-markets.spec.ts
git commit -m "test: cover market quote states and unpromoted opportunities"
```

### Task T88.3: 视觉门与 T88 收口

- [ ] **Step 1: 运行完整 Playwright（功能并行 + 视觉串行）两次**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/frontend && pnpm test:e2e`
Expected: 两次均 0 failed，视觉 lane 全部通过

- [ ] **Step 2: 证明批准基线零变化**

Run: `cd /Users/daibin/Documents/Coding/TennixAI && git status --short -- frontend/e2e/__screenshots__ && git diff --exit-code -- frontend/e2e/__screenshots__ && echo "PNG ZERO DIFF"`
Expected: 无变更输出 + `PNG ZERO DIFF`（本次不改预览原型，因此不应有任何 PNG 变化）

若出现任何 PNG 变化：**停止**，逐张产出 expected/actual/diff 并交用户审阅；不得使用 mask、阈值调整、skip、retry 或盲目重录；不得提交未经审阅的基线变化。

- [ ] **Step 3: 全量前端门**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/frontend && pnpm test && pnpm typecheck && pnpm build`
Expected: 全部通过

- [ ] **Step 4: 更新 `CURRENT.md` 与 `ROADMAP.md`**：T88 `done` + 实际证据（组件测试计数、e2e 计数、两次完整 Playwright 结果、PNG 零 diff），下一步指向 T89。

- [ ] **Step 5: 提交并推送**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add CURRENT.md ROADMAP.md
git commit -m "docs: close T88 truthful markets rendering"
git push origin main
```

---

# T89 — Local Market Coverage Gate and Phase Closure

**交付物**：确定性/integration/frontend/E2E 全绿；`verify` 增加有界只读 `market_quote_snapshot`；一次有界真实本地 coverage run（零 LLM）；runbook 与三份总控收口，`CURRENT.md` 无 active 任务。

### Task T89.1: `verify` 增加有界批量报价检查

**Files:**
- Modify: `backend/app/runtime/verify.py`
- Test: `backend/tests/test_runtime_verify.py`

**Interfaces:**
- Produces: `VerifyOutcome("market_quote_snapshot", ...)`；`VerifyDependencies.quote_batch_lookup`（对已发现且已映射的市场取 ≤2 个私有 token 对并做恰好一次批量请求）

- [ ] **Step 1: 先写失败测试**

在 `backend/tests/test_runtime_verify.py` 追加：

```python
async def test_market_quote_snapshot_is_bounded_and_honest():
    calls: list[tuple[str, ...]] = []

    class FakeMarkets:
        async def list_tennis_moneylines(self):
            return (make_market("mkt_1"), make_market("mkt_2"), make_market("mkt_3"))

        async def get_order_book(self, market_id):
            return book_for(market_id)

        async def get_order_books(self, token_ids):
            calls.append(tuple(token_ids))
            return batch_for(token_ids)

    outcomes = await verify_runtime(
        with_llm=False,
        tennis=FakeTennis(),
        identities=FakeIdentities(),
        live_feed_factory=lambda: FakeFeed(),
        markets=FakeMarkets(),
        market_token_lookup=token_lookup,
        market_feed_factory=lambda: FakeFeed(),
        llm_factory=None,
        receive_timeout_seconds=0.01,
    )
    names = [outcome.name for outcome in outcomes]
    assert "market_quote_snapshot" in names
    assert len(calls) == 1                     # exactly one batch request
    assert len(calls[0]) <= 4                  # bounded to two markets
    quote_outcome = next(o for o in outcomes if o.name == "market_quote_snapshot")
    assert quote_outcome.status in {"passed", "skipped", "failed"}
```

（并补一条：provider 抛 429 时 `market_quote_snapshot` 为 `failed` 且 reason code 为 `RATE_LIMITED`，且不重试。）

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/test_runtime_verify.py -q`
Expected: FAIL — `market_quote_snapshot` 不在结果里

- [ ] **Step 3: 实现**

`backend/app/runtime/verify.py`：

1. 常量：

```python
QUOTE_BATCH_MARKETS = 2
NO_QUOTE_TARGETS = "NO_QUOTE_TARGETS"
```

2. `VerifyDependencies` 增加 `quote_batch_lookup: Callable[[str], Awaitable[tuple[str, str] | None]]`（可复用既有 `market_token_lookup`；`verify_kwargs()` 同步带上）。

3. 新检查：

```python
async def _check_market_quote_snapshot(
    *,
    markets: Any,
    discovered: tuple,
    quote_batch_lookup: Callable[[str], Awaitable[tuple[str, str] | None]],
) -> VerifyOutcome:
    """One bounded batch quote request for the coverage lane (T89).

    At most `QUOTE_BATCH_MARKETS` discovered markets contribute their two
    private tokens; a quiet or unmapped catalog skips honestly instead of
    fabricating a quote.
    """
    name = "market_quote_snapshot"
    token_ids: list[str] = []
    for market in discovered[:QUOTE_BATCH_MARKETS]:
        pair = await quote_batch_lookup(market.id)
        if pair:
            token_ids.extend(token for token in pair if token)
    if not token_ids:
        return _skipped(name, NO_QUOTE_TARGETS)
    try:
        batch = await markets.get_order_books(tuple(token_ids))
    except Exception as exc:  # noqa: BLE001 - honest failure, sanitized code
        return _failed(name, stable_reason_code(exc))
    if not getattr(batch, "books", None):
        return _skipped(name, EMPTY_RESULT)
    return _passed(name)
```

4. `verify_runtime(...)` 在 `market_websocket` 之后调用它，并把它加入返回元组（顺序固定在最后一位之前，`llm` 保持最后）：

```python
    quote_snapshot = await _check_market_quote_snapshot(
        markets=markets,
        discovered=discovered,
        quote_batch_lookup=quote_batch_lookup,
    )
    ...
    return (rankings, catalog, tennis_ws, discovery, book, market_ws, quote_snapshot, llm)
```

5. `build_verify_dependencies` 传入 `quote_batch_lookup=token_lookup`（同一私有 token 查询，不新增凭据路径）。

- [ ] **Step 4: 运行**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest tests/test_runtime_verify.py tests/live/test_local_runtime_verify.py -q -m "not local_runtime_live"`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add backend/app/runtime/verify.py backend/tests/test_runtime_verify.py
git commit -m "feat: verify the batch quote lane within bounds"
```

### Task T89.2: runbook 更新

**Files:**
- Modify: `docs/runbooks/local-real-runtime.md`

- [ ] **Step 1: 更新内容**

在同一份 runbook 中加入：

1. 「两条数据车道」小节：车道 A（快照报价，覆盖全部 canonical 市场，不触发模型/决策/paper）与车道 B（严格映射 + 主巡单打 + tracking demand 的 WebSocket），并写明“浏览器打开与否不改变后台采集”。
2. `TENNIX_LOCAL_RUNTIME_MARKET_SNAPSHOT_SECONDS / _MAX_MARKETS / _TOKEN_BATCH_SIZE / _MARKET_QUOTE_FRESH_SECONDS` 四个键的默认值与边界。
3. quote 状态口径表（`realtime / snapshot / partial / no_liquidity / unavailable / stale / limited` 各一句页面含义）。
4. `runtime health` 的 `market_coverage` 聚合字段说明（candidate/attempted/各状态计数/batch_failures/rate_limited/last_successful_batch_at），并声明它只含聚合数字。
5. 正常事实状态补充：低级别市场无报价、无挂单、429 退避、模型未晋升机会空态都属正常，不得伪造成通过。
6. `verify` 新增 `market_quote_snapshot` 一项（至多一次批量请求、至多两个已映射市场）。

- [ ] **Step 2: 提交**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add docs/runbooks/local-real-runtime.md
git commit -m "docs: document the dual market data lanes"
```

### Task T89.3: 全链回归门

- [ ] **Step 1: 后端确定性 + infrastructure**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure and not player_alias_llm_live and not player_directory_e2e_live and not polymarket_live and not local_runtime_live" -q`
Expected: 0 failed；计数写入证据

Run: `cd /Users/daibin/Documents/Coding/TennixAI/backend && uv run pytest -m infrastructure -q`
Expected: 0 failed

- [ ] **Step 2: 前端**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/frontend && pnpm test && pnpm typecheck && pnpm build`
Expected: 全部通过

- [ ] **Step 3: 完整 Playwright 两次（默认 lane）**

Run: `cd /Users/daibin/Documents/Coding/TennixAI/frontend && pnpm test:e2e`
Run: `cd /Users/daibin/Documents/Coding/TennixAI/frontend && pnpm test:e2e`
Expected: 两次均为 0 failed、skipped 数一致

- [ ] **Step 4: 泄漏扫描**

Run: `cd /Users/daibin/Documents/Coding/TennixAI && git grep -nEi "condition_id|token_id|wallet|private_key|0x[0-9a-f]{8}" -- backend/app frontend/app frontend/components frontend/lib ':!*test*' | grep -v "market_external_ids\|token_a_id\|token_b_id\|clobTokenIds\|token_ids\|token_id\b.*PRIVATE" | head -20`
Expected: 只命中内部私有映射与适配层声明处；公共 DTO/页面/日志零命中

- [ ] **Step 5: 提交（若前几步有修正）**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add -A ':!.codex' ':!.superpowers' ':!REALTIME_LATENCY_INVESTIGATION.md' ':!frontend/next-env.d.ts'
git commit -m "chore: close T89 regression gates"
```

> 若本步骤没有文件改动，跳过提交（不要制造空提交）。

### Task T89.4: 有界真实本地 coverage run（零 LLM）

> 前提：根 `.env` 已配置（provider `api_tennis`、`p3_mode=paper`）。**全程不得调用 LLM**；不得开启 `--with-llm`。

- [ ] **Step 1: 启动**

```bash
cd /Users/daibin/Documents/Coding/TennixAI && ./scripts/tennix-live up
```
Expected: exit 0；打印浏览器地址

- [ ] **Step 2: 等待一个 snapshot 周期 + 启动余量**

Run: `cd /Users/daibin/Documents/Coding/TennixAI && sleep 180 && ./scripts/tennix-live status`
Expected: 服务 ok；`market_coverage` 出现 candidate/attempted 计数

- [ ] **Step 3: 采集 coverage 与页面证据**

```bash
cd /Users/daibin/Documents/Coding/TennixAI && curl -s http://127.0.0.1:8000/api/v1/runtime/health | python3 -m json.tool | sed -n '1,80p'
```
Expected: `market_coverage` 中 `candidate >= attempted`、`last_successful_batch_at` 非空、各状态计数之和等于 candidate；不得出现任何 token/URL/ID。

```bash
cd /Users/daibin/Documents/Coding/TennixAI && curl -s "http://127.0.0.1:8000/api/v1/markets?page=1&page_size=50" | python3 -c "
import json,sys
page=json.load(sys.stdin)
rows=page['data']
print('rows', len(rows), 'total', page['total'])
linked=[r for r in rows if r['match_id']]
print('linked', len(linked))
print('states', sorted({r['quote']['state'] for r in rows}))
print('availability', sorted({r['model_availability'] for r in rows}))
print('with_action', sum(1 for r in rows if r['decision_action']))
"
```
Expected: `linked > 0`（active link 生效）；`states` 只包含真实出现的状态；`with_action` 为 0（未晋升模型不产生动作）；输出中无 provider ID。

- [ ] **Step 4: 机会空态与零虚假动作**

```bash
cd /Users/daibin/Documents/Coding/TennixAI && curl -s http://127.0.0.1:8000/api/v1/markets/opportunities | python3 -m json.tool | sed -n '1,40p'
```
Expected: `data` 为空且 `availability.reason` 为真实原因（本机预期 `ELIGIBLE_UNPROMOTED`），`model_status` 为 `not_promoted`；零 `BUY`/`WAIT`。

- [ ] **Step 5: 浏览器双视口最小核验**

```bash
cd /Users/daibin/Documents/Coding/TennixAI/frontend && TENNIX_E2E_LOCAL_RUNTIME=1 pnpm exec playwright test e2e/local-real-runtime.spec.ts
```
Expected: 通过；若因外部安静或本机前端端口不同而失败，按 runbook 的排障表处理并**如实记录**

- [ ] **Step 6: B 车道（WebSocket/decision）诚实核验**

Run: `cd /Users/daibin/Documents/Coding/TennixAI && ./scripts/tennix-live logs runtime | tail -40`
Expected: 记录本轮是否出现市场 WebSocket 事件、gap、reconcile；若外部安静则如实记为“安静窗口”，**不得伪造成通过**。

- [ ] **Step 7: 关闭并确认数据保留**

```bash
cd /Users/daibin/Documents/Coding/TennixAI && ./scripts/tennix-live down && ./scripts/tennix-live status
```
Expected: `down` exit 0；容器与 `tennix_live_local`、paper ledger 保留

- [ ] **Step 8: 把真实结果写入证据**

在 `CURRENT.md`（关闭记录）与 `ROADMAP.md` 的 T89 行记录：运行日期、`market_coverage` 计数、quote 状态集合、`availability.reason`、B 车道结论（事件或诚实安静）、`down` 后的数据保留确认。真实的无挂单/安静/429 直接照实写。

### Task T89.5: 阶段收口（三份总控 + 推送）

- [ ] **Step 1: `ROADMAP.md`**：T89 行 `done` + 完成提交 + 上面全部实际证据；P4.3 阶段行改为 `done` 并写明 T84–T89 全部完成；`总体状态`/`当前里程碑`/`当前阶段` 同步为“P4.3 已关闭，等待用户排期下一个主任务”。

- [ ] **Step 2: `PROJECT.md`**：把 P4.3 段落更新为已交付事实（双通道、active-link 真相、七个 quote 状态、模型未晋升空态、零 provider 泄漏），保留“模型晋升与自动下单仍未授权”。

- [ ] **Step 3: `CURRENT.md`**：任务状态改为“无 active 任务”，写明 T89 完成提交、实际验证证据、当前本机栈状态（`down`）与下一步（模型晋升证据链需单独排期；自动下单保持 `deferred`）。

- [ ] **Step 4: 提交并推送**

```bash
cd /Users/daibin/Documents/Coding/TennixAI
git add CURRENT.md ROADMAP.md PROJECT.md
git commit -m "docs: close P4.3 market data truthfulness and coverage"
git push origin main
```

- [ ] **Step 5: 最终一致性核对**

Run: `cd /Users/daibin/Documents/Coding/TennixAI && git status --short --branch && git log --oneline -12 && grep -n "in_progress" CURRENT.md ROADMAP.md`
Expected: 与 `origin/main` 同步；`CURRENT.md` 无 active 任务；`ROADMAP.md` 仅 P4 里程碑整体保持 `in_progress`；受保护的未跟踪文件原样存在

---

## 自审（Self-Review）

**1. 规格覆盖**

| 规格条目 | 覆盖任务 |
|---|---|
| §2 根因 1（read-model 脱节） | T84.1/T84.2 |
| §2 根因 2/3（只有少量市场有 quote） | T85.1–T85.4、T86.3 |
| §2 根因 4（未晋升机会空态） | T87.1、T88.1 |
| §2 根因 5 + §4.2（WS 生命周期） | T86.4 |
| §3 全部产品决定（含低级别、视觉、资源预算、安全边界） | Global Constraints + T84–T88 |
| §4.1 车道 A 全部要求（对象范围、120 秒、100 token/批、250 上限与公平轮转、顺序批次、429/Retry-After、canonical 转换、raw batch + 14 天、零 ID 泄漏） | T85.2–T85.4、T86.1、T86.3 |
| §4.2 车道 B 与"API 优先 hot book、回退 fresh snapshot‖ | T85.2（display_quote）、T86.5（镜像）、T87.1（读路径） |
| §5.1 MarketOverview 与零 N+1 | T84.1、T84.2（含语句计数证据） |
| §5.2 latest-quote projection 与 source precedence | T85.1、T85.4 |
| §5.3 七个 quote 状态与逐 outcome 表达 | T85.2、T88.1、T88.2 |
| §6.1 DTO 语义（match_id/quote/model_availability/decision_action/overlay） | T87.1、T87.2 |
| §6.2 机会空态四类文案 | T87.1（reason）、T88.1（文案） |
| §6.3 页面行为（排序、真实 quote、低级别、导航、不新画原型） | T88.1–T88.3 |
| §7 配置与 coverage health | T86.1、T86.2、T86.5、T89.4 |
| §8 故障、安全、恢复（单批失败、单 token 隔离、Redis 丢失、gap 清除、浏览器不加连接、不改 P3 语义） | T85.4、T86.3、T86.4、T86.5 |
| §9.1 确定性测试七条 | T84–T87 各测试步骤 |
| §9.2 前端与浏览器（含视觉逐张审阅、禁 mask/阈值/skip） | T88.1–T88.3 + Global Constraints |
| §9.3 真实本地门六步 | T89.4 |
| §10 任务顺序与单一 current task | 任务顺序与依赖 + 各任务收口步骤 |
| §11 明确延期项 | Global Constraints（负面清单） |
| §12 官方接口依据 | T85.3（`POST /books` 数组 body、按 asset_id 取样、不假设顺序） |

**2. 占位符扫描**：全文无 TODO/TBD；每个代码步骤都给出可执行代码或精确 diff；`> 注：` 段落只用于指引接入既有 fixture/helper（并明确禁止新建平行 fake）。

**3. 类型一致性核对**

- `MarketOverviewRow` 字段在 T84.1 定义、T86.1 增加 `event_start`、T86.3 与 T87.1 使用一致。
- `display_quote` 参数名 `realtime_fresh_seconds`/`snapshot_fresh_seconds` 在 T85.2 定义，T86.3、T87.1 调用一致。
- `QuoteSnapshotRecord` 字段（`source/state/book_hash/as_of/expires_at/levels/outcome_bids/outcome_asks/best_bid/best_ask/spread/depth_usd`）在 T85.2 定义，T85.4/FakeProjections/T86.3 一致。
- `MarketQuoteCoverage` 字段与 `STATE_BUCKETS` 的七个桶名（`fresh_realtime/fresh_snapshot/partial/no_liquidity/unavailable/stale/limited`）在 T86.2、T86.3、T86.5、T89.4 一致。
- 前端 `MarketRowModel` 字段在 T87.2 定义，T88.1/T88.2 使用一致；`OPPORTUNITY_EMPTY_STATES` 的四个 reason 与后端 `ELIGIBLE_UNPROMOTED/NO_ELIGIBLE_ACTION/NO_COVERED_MARKET/DECISION_GAP` 逐字一致。
- `verify_runtime` 的返回顺序（`market_quote_snapshot` 在 `llm` 之前）与测试断言一致。

**4. 边界复核（负面清单）**

- 没有任何任务训练/晋升模型、改变阈值、产生虚假 BUY/WAIT、新增钱包/下单路径。
- 没有任何任务把 snapshot 接进 PredictionService/DecisionWorker/PaperTradingService（T86.3 显式断言零调用；T86.5 断言 roster 不变）。
- 没有任何任务扩大 WebSocket 订阅面（T86.4 只处理正常关闭与 keepalive；T86.5 断言 `active_market_ids()` 不变）。
- 没有任何任务引入 Kafka/Redis Streams/微服务/行情历史库/LLM 补全。
- 视觉真相路径：只改生产组件与 fixture，不改 `?preview=p3` 原型；T88.3 用零 PNG diff 作为门，并禁止 mask/阈值/skip/retry/盲录。