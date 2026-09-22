# TennixAI P4.3 市场数据可信度与覆盖设计

> **状态：** 已完成设计草案；用户书面审阅后才可写实施计划和实现。
> **日期：** 2026-09-22
> **关联任务：** [T83](../../../ROADMAP.md)
> **产品边界：** [PROJECT.md](../../../PROJECT.md)
> **当前交接：** [CURRENT.md](../../../CURRENT.md)
> **前置基线：** P3 已关闭；P4.1 的本地真实 runtime、单一上游所有者和 `paper_only` 边界均已实际验证。

## 1. 一句话目标

让 `/markets` 的「全部市场」可靠地展示**尽可能广覆盖、可解释且有时间戳的真实报价**，同时让模型/decision/paper 继续只消费小而严格的实时市场集合；页面绝不把缺报价、未映射、未晋升模型或连接故障伪装成 `MARKET ONLY`、`—` 或虚假的机会。

这不是模型晋升、自动交易或市场历史库项目。它解决的是“我在页面上看到的价格、关联和空态，到底是否真实、来自哪里、还能不能用于决策”。

## 2. 已验证事实与根因

以下是本设计的输入事实，不是推测：

1. 真实本地库中有 181 个已发现市场和 162 条 active `market_match_links`，但 `MarketRepository.link_match()` 只写 link 表；`P3QueryService.markets()` 却读取 `MarketRow.match_id`。后者在这些行上为 `null`，因此有效的严格映射没有到达 API 或页面。
2. 现有 `MarketWorker` 只订阅 `TrackingDemand`：严格映射、主巡单打、进入 tracking window 或已有 paper position 的市场。它正确地服务实时 decision，但天生不会为全部市场填充订单簿。
3. `/markets` 查询只从 Redis hot book 读取价格；当前只有少数 `book_change` observation，因此大部分真实市场行显示 `—`。这表示“当前没有可显示 quote”，不表示“没有市场”。
4. 生产模型是 `not_promoted`，没有 prediction/decision。`/markets/opportunities` 返回空数组符合 P3 的 fail-closed 原则；问题在于用户看不到空的真实原因。
5. 真机诊断还出现 market WebSocket normal-close / keepalive 异常和 queue overflow。扩大 WebSocket 订阅范围会放大这个问题，不能当作覆盖方案。

## 3. 已确认的产品决定

| 主题 | 决定 |
|---|---|
| 全部市场 | 以公开 Polymarket CLOB 批量 order-book snapshot 建立广覆盖；当前默认每 120 秒刷新一次，不依赖浏览器是否打开 |
| 决策实时性 | 严格映射、ATP/WTA 主巡赛或大满贯单打、在既有 tracking window 内的市场继续使用 WebSocket；snapshot 不触发 prediction、decision 或 paper |
| 映射真相 | `market_match_links.status='active'` 是 market→match 的唯一查询真相；不回填或依赖冗余 `markets.match_id` |
| 低级别赛事 | Challenger / ITF 继续展示市场和报价；不显示负向“模型未覆盖”标签，也不进入模型建议 |
| 空态 | 模型未晋升时，「机会」明确说明当前不会产生 `BUY/WAIT`；没有机会不能被包装成故障，也不能伪造信号 |
| 页面改动 | 保持现有 v0 页面结构；只改善数据状态、文案、时间和链接。任何截图基线变化都须逐张审阅，不以 mask、阈值、skip/retry 或重录规避 |
| 资源预算 | 不调用 LLM；batch REST 受明确上限、`Retry-After` 和退避控制；不把全部市场升级为 WebSocket 订阅 |
| 安全边界 | 仍只读 Polymarket、仍为 paper-only、无钱包/私钥/签名/下单；未晋升模型仍不得输出 `BUY/SELL` |

## 4. 目标架构：两条数据车道

```text
公开 tennis moneyline discovery
              │
              ├── A. 广覆盖报价车道（所有 canonical open/scheduled 市场）
              │     CLOB POST /books 批量 snapshot
              │     → canonical latest-quote projection
              │     → /markets「全部市场」
              │
              └── B. 实时决策车道（严格映射 + 主巡单打 + tracking demand）
                    CLOB WebSocket + REST reconcile
                    → Redis hot book → Prediction / Decision / Paper
                    → Opportunities / Match workbench
```

车道 A 回答“市场现在有没有可显示的真实盘口”；车道 B 回答“这条实时盘口是否满足模型和 paper 的严格门”。二者可以共享 canonical `OrderBookState`，但绝不能共享“触发决策”的副作用。

### 4.1 车道 A：广覆盖报价

- 目标对象是已经通过现有 PlayerResolver 进入 canonical market catalog 的 `open` / `scheduled` 单场胜者市场；解析失败的上游 listing 不在本阶段悄悄以不可信身份展示。
- runtime 每 120 秒调用一次批量 CLOB `/books`；每批最多 100 个**私有 outcome token**，等价于最多 50 个两边齐全的网球市场。
- 默认最多处理 250 个市场。当前 181 个市场在一轮内可覆盖；未来超过上限时，按 live → 开赛时间 → ATP/WTA → Challenger → ITF → stable market ID 的公平轮转处理，并公开聚合 `limited` 状态，不能静默饿死尾部市场。
- 每轮使用顺序批次，不创建 WebSocket、LLM 请求、prediction、decision、intent 或 paper fill。HTTP 429 必须尊重 `Retry-After`，本轮标为 degraded，不能忙等重试。
- 每个成功的批量响应先转换为 canonical two-outcome `OrderBookState`，再写入 durable latest-quote projection。原始批量响应按 batch 而非逐 token 写入既有 raw provider event store，并沿用 14 天清理；公共 API、日志、Chat 和页面不出现 token / condition / event ID。

### 4.2 车道 B：实时决策

- 现有 `MarketWorker` 的 bounded demand、REST-first baseline、Redis hot state、queue overflow→gap→REST reconcile、decision/paper 语义保持。
- 只有现有严格 mapping、领域资格和 tracking demand 同时满足时，市场才可进入 WebSocket roster；车道 A 绝不能让低级别、未映射或未晋升模型市场占用 roster。
- API 查询优先读 fresh WebSocket hot book；没有时回退到 fresh snapshot projection。只有 B 车道的书可驱动 decision/paper。
- `ConnectionClosedOK` 或“已 resolve 的订阅自然关闭”必须是显式、已处理的生命周期分支：已结束市场停止订阅，不留下未捕获 task error，也不把整个 market source 误标为故障。非正常关闭、ping timeout、overflow 或回放缺口仍按既有 `GAP → REST baseline → resume` 处理。

## 5. 数据真相与持久化

### 5.1 活跃映射 read model

新增内部 `MarketOverview` / 等价 projection，由 `markets` 左连接 `market_match_links`，连接条件固定为 `status='active'`。它至少携带：

- canonical market；
- `active_match_id | None`；
- link evidence 的内部可用状态；
- 比赛 catalog facts（tier、gender、discipline、phase、赛事名、内部 player IDs）。

`MarketRow.match_id` 仅是历史兼容字段，不得再作为 Markets、Opportunity、Pulse 或 Match navigation 的权威来源；不做批量 backfill 来制造第二份真相。所有查询一次批量加载 links、match facts、latest quote 和 prediction/decision，禁止每行 N+1 SQL 或 Redis 调用。

### 5.2 最新报价 projection

增加可逆 migration，创建每个 market 最多一行的 canonical latest-quote projection（命名可为 `market_quote_snapshots`）。它保存：

- `market_id`（内部主键）；
- canonical `OrderBookState` 或等价的两个 outcome book；
- `source = snapshot | websocket`；
- `quote_state`、`as_of`、`expires_at`、`book_hash`、`updated_at`；
- 只用于公开展示的统计字段，例如最佳 bid/ask、spread、depth。

它不保存 token、condition、event ID、原始 provider JSON、模型概率、decision 或 paper 状态。它是“当前已知报价”的 durable read model，不是历史行情仓库；高频/原始材料仍遵循既有 observation/raw 14 天策略。

每次 snapshot 只在 `book_hash` 或 quote-state 语义变化时更新 projection；同一内容重跑幂等。WebSocket 车道更新可覆盖同一 projection 为 `source=websocket`，但绝不能让过期 WebSocket 值覆盖更新的 snapshot 值。

### 5.3 可见报价状态

`—` 只能是某个明确状态下的单个缺失字段，不能单独充当状态。每行必须带可读标签和 `quote_as_of`：

| quote state | 判定 | 页面含义 |
|---|---|---|
| `realtime` | fresh WebSocket hot book | 实时盘口 |
| `snapshot` | 未过期 batch snapshot，至少一侧有可显示 level | 快照报价 · N 分钟前 |
| `partial` | 响应可信，但仅一边/一侧有可显示 level | 部分报价 · N 分钟前 |
| `no_liquidity` | 响应可信，但两侧都没有可显示 level | 暂无挂单 |
| `unavailable` | 本轮请求、解析或 identity 失败，且无可用旧值 | 报价暂不可用 |
| `stale` | 最后可信 quote 超过配置 freshness 上限 | 最后可信报价已过期 |
| `limited` | 因保护上限本轮未轮到；保留上次状态和时间 | 覆盖受限 · 等待下一轮 |

状态必须按 market 和 outcome 两层表达：比如某一位球员 ask 缺失时，不应把另一位的真实 ask 一起隐藏。`no_liquidity` 仅表示没有可显示流动性，不表示比赛或 market 不存在。

## 6. 公共 API、SSE 与前端语义

### 6.1 Markets DTO

`MarketSummaryDto` / 前端 decoder 需增加或拆分以下语义，不得再由 `action is null` 猜状态：

- `match_id` 来自 active link；有值时才允许内部 Match Page 链接；
- `quote`（两边独立 levels/aggregate）、`quote_state`、`quote_source`、`quote_as_of`；
- `model_availability = available | eligible_unpromoted | out_of_scope | not_evaluated`；
- `decision_action` 仅在真实 `DecisionObservation` 存在时提供；`MARKET_ONLY` 只能来自真实 observation，不是前端 fallback；
- 既有 `is_stale` / `has_gap` 继续代表决策关键数据的安全 overlay，不与 quote state 混淆。

低级别 linked market 可以有 `match_id` 与实时/快照 quote，却使用 `out_of_scope`，前端不显示“未覆盖”贬义标签。未 linked market 继续显示其 canonical 球员与问题，但没有虚构 Match 链接。

### 6.2 Opportunities 的诚实空态

机会端点保留 `data`，并新增页面可消费的 aggregate availability：

| 条件 | 空态文案方向 |
|---|---|
| `eligible_unpromoted` | “模型尚未完成验证，当前不生成 BUY / WAIT；全部市场的真实报价仍可查看。” |
| 模型可用但无合格动作 | “当前没有满足策略门的机会。” |
| 没有合格主巡单打市场 | “当前没有可评估的主巡单打市场。” |
| 决策数据 gap / stale | “决策数据正在恢复，暂不生成新机会。” |

机会列表仍只显示已覆盖且当前 action 为 `BUY` 或 `WAIT` 的合格赛事；`NO BET`、`MARKET_ONLY`、Challenger、ITF 和 snapshot-only 市场永不进入。未晋升模型不能为了让 tab 不为空而产生测试 action。

### 6.3 页面行为

- 「全部市场」按既有 ATP/WTA → Challenger → ITF → other 排序，显示双方独立的真实 quote、quote label 与更新时间；不因模型不可用隐藏市场数据。
- 有 active link 的行进入内部 Match Page；无 link 的行保留市场信息但不出现错误的导航箭头。
- 「机会」空态使用上表解释；「Paper 账本」语义不变。
- Home Pulse 和 Match Workbench 只消费 B 车道的 decision 结果；不因 A 车道扩容改变三行限制、decision state 或 paper lifecycle。
- 不新画 v0 原型；布局几何、桌面 `1440×1000`、移动 `390×844` 保持。新增状态需要现有 Playwright 功能和视觉门覆盖。

## 7. 配置、容量与健康

root `.env.example` 新增有边界的 runtime 配置；根目录 `.env` 仍是唯一人工入口：

| 配置 | 默认 | 边界 | 作用 |
|---|---:|---:|---|
| `TENNIX_LOCAL_RUNTIME_MARKET_SNAPSHOT_SECONDS` | 120 | 60–900 | 车道 A 调度周期 |
| `TENNIX_LOCAL_RUNTIME_MARKET_SNAPSHOT_MAX_MARKETS` | 250 | 1–500 | 一轮最多 market 数 |
| `TENNIX_LOCAL_RUNTIME_MARKET_SNAPSHOT_TOKEN_BATCH_SIZE` | 100 | 2–100 | 每个 CLOB batch 的私有 token 数 |
| `TENNIX_LOCAL_RUNTIME_MARKET_QUOTE_FRESH_SECONDS` | 300 | 120–1800 | snapshot → stale 的阈值 |

当前 181 市场约 362 token，按默认需 4 个批次 / 120 秒，即约 120 个请求 / 小时，远低于官方 CLOB `/books` 的请求上限；实现仍必须尊重实际 429 与服务端变化，不能把这个估算当作永久保证。

runtime health 增加只含聚合数字的 market quote coverage：candidate、attempted、fresh realtime、fresh snapshot、partial、no liquidity、unavailable、stale、limited、batch failures、429/backoff 和 last successful batch。不得输出外部 ID、原始 URL、token 或凭据。

## 8. 故障、安全与恢复

- snapshot 单批失败不删除旧 projection；根据新鲜度保留 `snapshot`、升级为 `stale` 或 `unavailable`，并在下一轮有限重试。
- batch 中某个 token/market 无法解析时，只影响对应 market；其他 canonical market 可继续更新。
- Redis 热状态丢失时，B 车道按既有 REST reconcile 重建；A 车道 durable snapshot 仍可展示最后状态，但不能生成新 action。
- 每次 overflow、异常 WS close 或 reconnect 都必须在 source health 中留下 `gap`，且 REST baseline 成功后才清除；正常 resolved close 不得产生未处理异常或误导性的全局故障。
- 刷新浏览器、打开多个 tab、查询 `/markets` 或从 All Markets 链接到 Match 都不得增加第二条上游连接。
- 它不改变 P3 的 `BOOK_UNVERIFIABLE` / `NO_FILL`、FOK、one-shot intent、provider-final resolution、PostgreSQL ledger 权威和独立 SSE cursor 语义。

## 9. 验收与回归门

### 9.1 确定性测试

1. active `market_match_links` 的 `match_id`、tier、phase、player names 和 Match URL 在 Market overview 中正确出现；replaced / inactive link 不得泄漏。
2. CLOB batch 请求按 token 上限拆分、去重、稳定排序；两边 outcome 重组正确；空 book、单边 book、坏 payload、429、部分 batch 失败和相同 hash 重跑均有测试。
3. snapshot 更新不调用 WebSocket、LLM、PredictionService、DecisionWorker 或 PaperTradingService；低级别市场不会进入 realtime demand。
4. latest quote projection 的 upsert、source precedence、fresh/stale/limited 转换和 14 天 raw batch cleanup 可重放、幂等且不含公共 provider ID。
5. `ConnectionClosedOK` / resolved close、异常 close、keepalive timeout 和 queue overflow 都不会遗留 unhandled task；异常路径必须产生 gap、REST reconcile 和恢复后的 fresh 证据。
6. Opportunities 在 `not_promoted` 时有稳定 aggregate reason、空 `data`、零 `BUY/WAIT`；真正 `NO BET` 与 null action 不得被误渲染为同一状态。
7. 公开 API、SSE、Chat、URL、日志、错误和截图继续零 token / condition / event ID、密钥、钱包、签名和真实交易路径。

### 9.2 前端与浏览器

- unit/component 覆盖全部 quote state、model availability、link/no-link、未晋升机会空态和 low-tier 无负向模型标签；
- Next proxy / typed decoder 对未知 enum fail closed；
- Playwright 覆盖桌面与移动的 All Markets fresh snapshot、partial/no-liquidity/stale/unavailable、unpromoted Opportunities、真实 action Opportunities、Match navigation；
- 视觉变更必须先逐张产出 expected/actual/diff 并由用户审阅；不得用 mask、阈值、skip、retry 或盲目重录基线绕过。

### 9.3 真实本地门

在根 `.env` 已配置、且不调用 LLM 的前提下，执行一次有界真实 run：

1. `./scripts/tennix-live up`；
2. 等待最多一个 snapshot 周期加有限启动余量；
3. 读取 runtime health 与 `/markets`，证明 candidate/attempted 计数一致，当前候选都得到诚实的 quote state，active link 行能进入内部 Match；
4. 验证 Opportunities 在模型未晋升时显示解释性空态，零 BUY/WAIT，且不含 provider identity；
5. 验证一个 B 车道市场的 WebSocket 更新仍可驱动原有健康/decision 路径，或在外部安静窗口如实记录 skip；
6. `./scripts/tennix-live down`，确认数据、容器和 paper ledger 保留。

真实市场的无挂单、供应商安静或 429 是有效结果，必须诚实记录，不得为了“通过”改为 fixture 或伪造报价。

## 10. 实施顺序（T84–T89）

| 任务 | 交付物 | 完成条件 |
|---|---|---|
| T84 | Active-link market overview projection | query/API 使用 `market_match_links` 权威 join；无 N+1；link navigation 与 tier/phase 恢复 |
| T85 | Read-only CLOB batch adapter 与 durable latest-quote projection | 可逆 migration、private token target、batch `/books`、canonical parse、raw 14 天与幂等 upsert |
| T86 | Snapshot scheduler、coverage health 与 WebSocket lifecycle hardening | 120 秒 bounded job、429/backoff/fair rotation、normal close/overflow/reconcile 可重放 |
| T87 | Typed Markets/Opportunities REST+SSE contract | quote/model/decision 语义显式，旧 null fallback 删除，公共面零 provider ID |
| T88 | Markets UI、空态与受审视觉门 | 所有 quote state、低级别展示、unpromoted 空态、正确导航；双视口审阅 |
| T89 | 全链回归、真实本地 coverage gate 与文档关闭 | 确定性、integration、frontend、E2E、bounded live run、总控和 runbook 证据齐全 |

T84–T89 必须顺序领取、单一 current task、每项独立提交和推送。T83 之后下一执行者应先写详细实施计划；不得从本表直接跳到产品代码。

## 11. 明确延期

- 训练、评估、校准或晋升任何模型 artifact；
- 改变 BUY/WAIT/NO BET 阈值、退出策略、仓位或 paper lifecycle；
- 自动下单、钱包、签名、认证或交易凭据；
- 把所有市场改为 WebSocket、Kafka/Redis Streams、微服务或完整行情历史仓库；
- 允许未解析球员名称的原始供应商市场绕过 canonical identity；
- 用 LLM 估概率、补盘口、修映射或填充页面空值。

## 12. 官方接口依据

- [CLOB 批量 order books：`POST /books`](https://docs.polymarket.com/api-reference/market-data/get-order-books-request-body)
- [CLOB rate limits](https://docs.polymarket.com/api-reference/rate-limits)
- [Polymarket market WebSocket 实时数据](https://docs.polymarket.com/market-data/realtime-data)

这些接口只支撑公开只读 market data。任何未来交易相关能力仍需独立设计、权限和安全审查。
