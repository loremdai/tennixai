# TennixAI 项目概况

> 本文件回答“这个项目是什么、为什么做、哪些原则不能被破坏”。
> 全局进度见 [ROADMAP.md](./ROADMAP.md)，唯一当前任务见 [CURRENT.md](./CURRENT.md)。

**最后更新：** 2026-09-22 15:50 CST

**产品阶段：** P1 — 比赛信息查询助手（`done`，2026-09-08）；P2.0–P2.6 全部 `done`（P2.6 于 2026-09-13 经 T54 修正门重新关闭）；P3 — Market & Decision Support（`done`，2026-09-17 经 T71 证据表关闭，P3.0–P3.3 已完成（T56–T65）；T66 只读 P3 REST/独立 SSE/Chat 工具已完成（`be17eea`+`3ef0cd3`）；T67 typed frontend transport/独立 stream hooks 已完成（`808b87e`）；T68 Home Pulse 与 `/markets` 三视图已完成（`39756f7`）；T69 Match Decision Workbench 已完成（`64bb505`）；T70 双流 replay/recovery/全回归/视觉门已完成（`01e6ba0`）；T71 真实只读 shadow gate 已完成（`3fde00a`））；P4 — Product Hardening & Optimization（P4.0 Local Real Runtime 设计与实施计划 `done`；P4.1 Local Real Runtime Implementation 已关闭，2026-09-18 经 T80 证据表与 Completion Gate 九条逐条核验关闭（T73–T80 全部 `done`）；T81 视觉 E2E 并行稳定性收口已 `done`（2026-09-18，原生 `@visual` tag + 功能并行/视觉串行两条顺序 CLI lane，默认 `pnpm test:e2e` 连续两次 110 passed/44 skipped/0 failed，批准 PNG 零变更）；T82 一键启动器修复已 `done`（`2cea490`：`up` 直接执行已安装 Next，不再调用 PATH 上的 pnpm；普通 `up → health → down` 真实门通过）；T81/T82 均不改变产品数据、paper-only 或自动下单边界）

**详细基线：** [产品与架构上下文](./docs/product-context.md) · [产品路线设计](./docs/superpowers/specs/2026-09-08-tennixai-product-roadmap-design.md) · [P1 实施计划](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md) · [P2 设计规格](./docs/superpowers/specs/2026-09-09-tennixai-p2-live-match-intelligence-design.md) · [P2 实施计划](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md) · [P2.6 球员目录设计](./docs/superpowers/specs/2026-09-12-tennixai-player-directory-multilingual-identity-design.md) · [P2.6 实施计划](./docs/superpowers/plans/2026-09-12-tennixai-player-directory-multilingual-identity-implementation.md) · [v0 球员页面 Prompt](./docs/v0/2026-09-12-player-pages-prompt.md) · [T54 Home 历史球员问答修正设计](./docs/superpowers/specs/2026-09-13-tennixai-home-historical-player-query-closure-design.md) · [T54 实施计划](./docs/superpowers/plans/2026-09-13-tennixai-home-historical-player-query-closure.md) · [P3 SOTA 调研](./docs/research/2026-09-15-tennis-win-probability-sota.md) · [P3 设计规格](./docs/superpowers/specs/2026-09-16-tennixai-p3-market-decision-support-design.md) · [P3 实施计划](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md) · [P3 v0 Prompt](./docs/v0/2026-09-16-p3-market-decision-pages-prompt.md) · [P4.0 本地真实运行设计](./docs/superpowers/specs/2026-09-17-tennixai-p4-local-real-runtime-design.md) · [P4.0 实施计划](./docs/superpowers/plans/2026-09-17-tennixai-p4-local-real-runtime-implementation.md)

**P4.3 设计：** [市场数据可信度与覆盖](./docs/superpowers/specs/2026-09-22-tennixai-p4-market-data-truthfulness-and-coverage-design.md)（T83 正在设计冻结；用户书面审阅后才写实施计划和产品代码）。

## 5 分钟恢复入口

- TennixAI 不是通用网球聊天机器人，而是以结构化网球数据为核心、AI 作为交互层的数据与决策产品。
- Home 负责全局发现、搜索和赛程入口；Match Page 负责单场比赛的事实、上下文问答和后续智能能力。
- P1 已完成：fake 模式全链路确定性地跑通；真实 LiveTennisAPI provider、真实 Qwen 单项与组合门均通过；真实 live 列表现在只把有限摘要交给 LLM，完整结构化数据仍通过 SSE 交给 UI，LLM 请求有 45 秒可配置总时限，真实 Djokovic 查询的重复实名/组合名也已稳定处理。
- P1 只处理当前、即将开始和正在进行的比赛；P2.4 已增加 API-Tennis 按需的昨天/近期结果、有限 H2H、compact fact packet 与版本化 Match Chat，但不建设完整历史镜像。
- P2 设计已冻结：API-Tennis WebSocket 是实时主路径，PostgreSQL 保存长期 canonical 事实，Redis 负责租约、热状态和 pub/sub，FastAPI 通过版本化 SSE 服务浏览器。
- Home 默认展示 ATP + WTA、全部性别、单打，并允许赛事级别、性别、单双打叠加筛选；赛事按 ATP/WTA → Challenger → ITF → other 排序。
- Match Page 将提供完整 PBP、尽可能多的可信技术统计、近期控制指数和带 `state_version/as_of` 的上下文问答。
- P2.6 的目录、球员详情、多语言身份和五赛季赛果页面已交付；T54 已关闭 Home Chat 的历史问答闭环：确定性能力路由识别昨天/上一场/近期/赛季/交手意图，`last`/`recent` 使用五赛季按需结果数语义（不再等同 30 天窗口），赛季战绩只读缓存 profile，`player_history` typed 结果经 SSE 逐条保序送达，Home 按球员分组渲染历史与赛季汇总（含专用双视口视觉基线），真实 API-Tennis/真实 LLM/真实浏览器均以内容级断言验收。
- 球员身份统一为“英文主名 + 中文辅名 + aliases → 内部 `player_id`”；中文名离线批量补齐（净库覆盖 100%，重跑零模型调用），Home/Match Chat 运行时只使用确定性 PlayerResolver，不调用翻译 LLM。
- P2.6 首要回归已关闭：`Ben Shelton`/`B. Shelton`/`Shelton`/`本·谢尔顿`/`谢尔顿` 等别名矩阵解析到同一内部 ID；`ambiguous` / `not_found` 为正常可恢复结果（自然澄清 + SSE `done`）。
- P2 仍严格排除 odds、预测、Polymarket、交易、认证和云部署；完成目标是本地完整运行与少量好友私人测试。
- P3 当前已确认：同时覆盖赛前与赛中，但第一版只处理单场比赛胜者市场。持仓前分开显示模型观点和交易动作：`BUY` 只在保守净 edge 过门时触发，`WAIT` 只表示已有明确低估方向但当前可执行价尚未过线并显示动态最高买入价，市场一致或硬门失败则显示带原因的 `NO BET`。每场第一条合格 `BUY` 只生成一次固定 `$10` paper entry intent；P3 按 FOK 语义模拟入场和全仓退出，delay 后不能完整成交则不产生 partial position 或残余仓位。entry `NO_FILL` 记为终态 `MISSED`，继续保存 observation 但不追价或重试。成交后由确定性的 EV-exit 作为主 paper 轨道，主动作只有 `HOLD / SELL`；首次 `SELL` 只产生一次全仓 FOK exit intent，`NO_FILL` 后记 `EXIT_MISSED` 并持有至结算，不再退出。`LOCK PROFIT` 是单独标注的可选降风险对照，不改变主账本；HODL 与 convergence-lock 完整保存为反事实，同场不加仓、不换边、不重新入场。用户可见主状态固定为 `MARKET_ONLY → NO BET / WAIT / BUY → ENTRY_PENDING → FILLED → HOLD / SELL → EXIT_PENDING → EXITED / EXIT_MISSED → SETTLED`，其中 `MISSED` 是 entry 未成交终态，`STALE / GAP` 是可叠加于任一运行状态的可信度覆盖层。
- T55 已冻结 P3 规格、v0 状态矩阵与 T56–T71 实施路线（`d7cc25e`）；用户已确认并推送 v0 原型 `9c868bf`。T56 已将 preview 页面、状态数据与验证用例连同 26 个场景 × desktop/mobile 的 52 张基线冻结（`f29a789`）；T57 已交付 P3 canonical domain、只读 `MarketDataProvider` protocol 与安全配置（`e7da341`）；T58 已交付可逆 migration `0004` 与幂等 market/paper ledger repositories（`02516c6`，PostgreSQL 是 paper 权威）；T59 已交付只读 Polymarket adapter 与 PlayerResolver 精确 mapping（`0d6728c`，真实公开 REST smoke 通过）；T60 已交付 market WebSocket reducer、Redis 热状态、有界 worker 与确定性 replay（`6aac68f`，真实公开 WS 通道经活跃市场对照验证），P3.2 关闭；T61 已交付审计 walk-forward benchmark 管线与 fail-closed CLI（`9ef4937`，合成 fixture 诚实 `not_promoted`）；T62 已交付确定性计分引擎、empirical-Bayes 收缩与 fail-closed PredictionService（`5031856`）；T63 已交付 `$10` 逐档可执行 quote、fail-closed versioned policy 与全 hard-gate 决策引擎（`6012fcc`）；T64 已交付 one-shot FOK paper lifecycle、provider-final settlement 与并发/崩溃恢复证明（`d5ae409`）；T65 已交付双流决策编排、durable tracking demand 与低基数管线指标（`8cc3c26`，本地延迟门 book→decision p95<500ms、sports→decision p95<1s 实测通过），P3.3 关闭；T66 已交付七个只读 P3 REST 端点、markets/decision 双独立 SSE（snapshot-first、各自 version cursor、gap 只重取自身）、两个只读 Chat 工具与真实 P3QueryService（PostgreSQL ledger 权威 + Redis hot book 补充）（`be17eea`，P2 `/matches/{id}/stream` 字节级回归不变、公共面零 provider/wallet 字段）；T67 已交付 typed frontend transport：全部 P3 DTO/SSE runtime 解码（未知 enum 显式失败）、七个薄代理路由、`useMarketStream`/`useDecisionStream` 独立 cursor 与 gap 只重取自身（`808b87e`，前端 313 passed、typecheck 干净、P2 match stream 回归不变）；T68 已交付生产 Home Pulse（≤3 行、紧急持仓预留、无轨迹/账本细节）与 `/markets` 三视图（canonical 筛选、整行内部导航、全套降级矩阵），服务端能力探测保证 P3 关闭时 P1/P2 Home 字节不变，52 张 P3 视觉基线与 P1/P2 基线原样通过（`39756f7`，前端 351 单测 + Playwright 84 passed）；T69 已交付生产 Match Decision Workbench（`64bb505`，后端补强 `32ab3bd`/`99c980e`/`e96e1a7`/`1f36773`）：全宽 DecisionSummary 以服务端快照为单一当前动作来源（12 状态 + STALE/GAP 正交 overlay、intent 后 entry 控件消失、零真实下注文案）、双边独立可执行 ask 与 $10 算术逐字展示、ledger 派生永久 Paper 时间线、evidence/gates 与留缺口不插值的模型—市场轨迹图，`useDecisionStream` gap 只降级自身；冻结 preview 保持 52 张基线原样，生产移除旧侧栏占位后 4 张 P1 match 基线逐张审阅重生成；T70 已交付双流 replay/recovery/延迟门/全量回归与 26 场景逐张视觉门（`01e6ba0`：dual-stream fixture 对真实 PostgreSQL+Redis 证明全链与 restart 恢复、双跑 digest 相同、公共面零 provider ID；52 张 P3 基线字节不变，4 张 P1 match 基线因生产移除旧侧栏占位逐张审阅后重生成；并修复 exit intent 在不可验证/过期短路下位置永久 exit_pending 的结算缺陷）；T71 已交付真实只读 shadow gate 并关闭 P3（`3fde00a`：配置零交易凭据、未晋升模型在真实 shadow 下只输出 NO BET/MARKET_ONLY、映射市场只读观察、REST/WS smoke 带日期诚实 skip、真实浏览器只读流零 provider ID；P3 Completion Gate 八条逐条有证据，自动下单与 P4 优化保持延期）。
- P3 实时性是首要运行目标：后端同时拥有 API-Tennis 与 Polymarket WebSocket 状态，按事件更新模型或可执行 edge；既有 sports stream 与新增 decision stream 使用独立版本游标和 SSE，任一缺口只重取自身 snapshot。浏览器生命周期不控制 paper tracking。进入追踪窗口且完成精确组合的模型覆盖比赛由后端持续跟踪，已有持仓跟踪至退出或结算；REST 只用于首次快照、重连和校准。任何断流、版本缺口或离线区间都必须显式降级并禁止新动作，不得补造信号或成交。
- P3 实时写入按事件价值和频率分流：WebSocket ingress 只入有界队列；低频 API-Tennis canonical reduction 首版保留 PostgreSQL DB-first；高频 Polymarket order book 走内存/Redis 热状态，只异步批量保存决策相关 observation；paper intent、成交/未成交、退出与结算必须以幂等键同步提交 PostgreSQL 后才对外确认。P3 本地阶段不新增 Kafka 或 Redis Streams。
- P3 的模型 champion、校准器和 BUY/SELL 阈值只能由许可/覆盖审计、chronological walk-forward、untouched test 和 shadow evidence 晋升；证据不足时生产保持 `NO BET`。paper 结算只服从各 Polymarket market 自身规则与最终 resolution，退赛、walkover、取消、延期、争议和 50–50 不由 API-Tennis winner 代替判定。
- P3 页面采用三层结构：Home 用最多三行的「市场脉搏」摘要少量高价值机会和未结持仓；独立 `/markets` 以“机会 / 全部市场 / Paper 账本”三视图负责跨比赛发现与跟踪；Match Page 是单场决策工作台，承载概率、市场、edge、动作、轨迹、依据与本场 position lifecycle。
- P4 用于基于真实使用和 paper-trading 证据统一打磨 P1–P3，包括事实查询体验、实时质量、模型校准、决策阈值、仓位管理、性能与产品细节；先搭完整框架，再做细致优化。P4.0 已冻结完整本地真实运行设计及其 T73–T80 实施路线：单一 `init/up/status/down` 入口、独立 `tennix_live_local` 数据库、runtime 独占两条上游 WebSocket、低频赛程/排名同步、显式 stale/gap 与 `paper` 边界；P4.1 已按该计划逐任务交付并关闭：`./scripts/tennix-live init/up/status/down/logs/verify` 全生命周期真实可用（真实 init 幂等、verify 7/7 真实通过、浏览器验收 6/6、两轮 up/down 后数据与 paper ledger 完整保留、浏览器刷新与 FastAPI 重启不产生第二条上游订阅），T82 又将日常 `up` 固定为直接运行已安装 Next，避免启动时触碰 `node_modules`；日常运行入口与人类 runbook 见 `docs/runbooks/local-real-runtime.md`；自动下单与模型晋升仍未授权。
- T81 是独立的测试基础设施收口：把既有视觉快照从并行功能 E2E 中隔离到串行通道；不改变任何产品 UI、批准 PNG、真实 runtime 或 paper-only 边界。已于 2026-09-18 完成（`2c1186c` 原生 `@visual` 组级 tag、`9f5a459` 功能并行/视觉串行两条顺序 CLI lane）：默认 `pnpm test:e2e` 连续两次 `110 passed/44 skipped/0 failed`，全部批准 PNG 零 diff，未调阈值、未加 mask/skip/retry、未运行 live/LLM 配额门。详细步骤见 [T81 计划](./docs/superpowers/plans/2026-09-18-tennixai-t81-playwright-visual-gate-stabilization.md)。
- P4.3 已确认双通道：`/markets` 的全部 canonical market 以有界公开 batch snapshot 获得真实、带时间的展示报价；严格映射且合格的主巡单打仍由 WebSocket 驱动模型/decision/paper。`market_match_links` 是 market→match 的查询真相，不能由空的 `markets.match_id` 代替。报价状态必须明确区分 realtime、snapshot、partial、no liquidity、unavailable、stale 和 limited；`机会`在模型未晋升时明确说明不会产生 `BUY/WAIT`。该优化不训练/晋升模型、不改变决策门、paper lifecycle 或自动交易边界。
- 不要从本文件猜当前做到哪里；以 [ROADMAP.md](./ROADMAP.md) 和 [CURRENT.md](./CURRENT.md) 为准。

## 产品定位

```text
Tennis Data / Intelligence Product
                +
     Conversational Interface
```

LLM 负责理解意图、选择业务工具和组织表达，不是网球事实来源。比分、赛程、球员、赛事、发球方、状态和内部 ID 必须来自结构化服务结果。

### Home Page

承担 Discovery、Search、Schedule、Live Now、Following，以及未来具备数据能力后的 Recent Results。P3 将现有市场情报占位升级为最多三行的「市场脉搏」：有开放 paper position 时为其保留一行并优先异常或需动作状态，其余按赛中 `BUY` → 赛前 `BUY` → 最强 `WAIT` 选取。每行只显示比赛、模型概率、可执行市场概率、当前动作与 freshness；点击进入 Match Page，“查看全部”进入 `/markets`。Home 不承载交易按钮、轨迹或详细 ledger，无机会时显示诚实空态。典型查询输出仍是：简短回答 + Structured Match Card + Open Match。

### Match Page

承担单场 Investigation：比分、状态、发球方、上下文问答，以及 P2/P3 的统计、PBP、走势、市场和决策支持。P3 采用“全宽决策条”布局：既有比赛 Hero 保持首位，其后用跨越主栏和侧栏的 `DecisionSummary` 先回答模型观点与唯一主动作，并以双边对照分别展示两位球员的模型概率、固定 `$10` 可执行平均买入价和保守净 edge；两侧实际 ask/depth 独立计算，不假设互补。paper 成交确认后，同一摘要原地切换为 position 管理，入场动作消失，只显示持仓方向、成本、当前可退出价值、P&L、稳健持有价值与 EV 主动作 `HOLD / SELL`；满足条件时另列非主动作 `LOCK PROFIT` 风险选项。下方继续沿用比赛事实主栏 + 粘性助手/关键事实侧栏；详细概率—市场轨迹、结构化依据、入场历史和本场 lifecycle 放入主栏，旧侧栏市场占位不再保留。`STALE / GAP` 不替换账本状态，而是在摘要上保留最后可信快照并撤销新的 `BUY / SELL`；pending intent 到期时若无法验证订单簿，只能记录带原因的不可验证 `NO_FILL`，不得伪造成交。页面必须携带内部 `match_id`，用户无需重复比赛上下文。

### Markets

`/markets` 承担跨比赛 Market Discovery 与 Paper Tracking，并固定为三个页面级视图：

- `机会` 是默认视图，只展示模型覆盖的大满贯及 ATP/WTA 主巡赛单打中当前为 `BUY` 或 `WAIT` 的项目，Live 在前、Upcoming 在后；`NO BET` 不占用机会流。
- `全部市场` 展示所有可用的 Polymarket 网球单场胜者市场，按 ATP/WTA → Challenger → ITF → other 排序，并提供赛事级别、性别和赛前/赛中筛选。模型覆盖项目的 `NO BET` 显示具体原因；Challenger/ITF 仅展示市场，不显示“未覆盖”等负向标签。
- `Paper 账本` 先展示开放持仓，再展示近期退出与结算；这里只做组合概览，单场详情回到 Match Page。

它不是自动交易终端，不替代 Match Page 的单场深度调查；点击任一市场、机会或持仓都进入对应内部 `match_id` 的 Match Page。

### Players

承担 Ranking Discovery 和 Player Investigation：`/players` 默认展示 ATP/WTA 单打 Top 200，可搜索本地目录中的全部已知单打球员；`/players/[playerId]` 展示英文主名/中文辅名、档案、当前排名、赛季统计、live/next 状态和按需历史赛果。第一版不做双打或独立 Player Chat。

## 四阶段产品路线

| 阶段 | 目标 | 主要数据能力 | 明确边界 |
|---|---|---|---|
| P1 | 比赛信息查询助手 | 今日/今晚/下一场、赛事、轮次、场地、状态、比分、发球方 | 不做任意历史结果、技术统计和自动轮询 |
| P2 | Live Match Intelligence | API-Tennis live/PBP/statistics、近期控制指数、轻量历史/H2H、多进程持久化与协调，以及球员目录、多语言身份和历史赛果入口 | 不接 odds、预测、市场或交易；不镜像完整供应商历史 |
| P3 | Market & Decision Support | 赛前与赛中的单场胜者市场、预测概率、edge、confidence、模型观点与 `BUY / WAIT / NO BET`，以及一次入场/最多一次退出的 paper trading；区分期望值 `SELL` 与风险降低 `LOCK PROFIT` | 不做其他市场类型、加仓、换边、重新入场或自动下单；自动执行必须另立阶段并单独批准 |
| P4 | Product Hardening & Optimization | 基于 P1–P3 的真实使用、回放和 paper 结果优化数据质量、模型、策略、体验与性能 | 以打磨既有框架为主；不默认引入自动下单或未经验证的新产品面 |

## 稳定架构

```text
Provider
   ↓
Canonical Domain Model
   ↓
TennisService
   ↓
Feature / Prediction / Decision
   ↓
Chat + UI
```

以下内容应保持稳定：

- canonical domain model
- service contract
- provider interface
- feature / prediction / decision semantics
- 结构化事实与 LLM 文本的边界

以下内容允许替换：数据供应商、LLM、预测模型和前端实现。业务代码不得依赖 `event_key`、`event_first_player`、`score[0][1]` 等供应商字段。

P2 的实时依赖方向进一步固定为：

```text
API-Tennis REST/WebSocket
          ↓
Provider adapters
          ↓
Canonical reducer
          ↓
PostgreSQL + Redis coordination
          ↓
FastAPI snapshot/SSE + TennisService
          ↓
Next.js structured UI + Chat
```

P2.6 的球员身份依赖方向固定为：

```text
API-Tennis rankings / players / fixtures
                  ↓
        PlayerDirectorySync
                  ↓
Player + External IDs + Ranking + Aliases
                  ↓
           PlayerResolver
   resolved | ambiguous | not_found
                  ↓
TennisService → REST DTO / Home Chat / Match Chat
```

前端、Chat 和比赛数据只能共享同一份球员主数据与 resolver，不能各自维护中文名或名字匹配表。解析成功后必须按内部 `player_id` 查 external ID，再调用 provider；不得让业务层按供应商字符串反查身份。

## P1 已批准方案

- 前端：Next.js、TypeScript、Tailwind CSS、现有 v0 原型；原型是视觉真源。
- 后端：Python、FastAPI、Pydantic、httpx。
- 前后端边界：浏览器只请求 Next.js `/api/*`；Route Handler 薄代理 FastAPI，并透传 SSE。
- 数据：LiveTennisAPI Free；进程内 identity 与 bounded TTL cache；不接 PostgreSQL/Redis。
- 时间：canonical UTC；自然语言时间按 `Asia/Macau`，`tonight` 为有效或下一段 18:00–05:59。
- Chat：OpenAI-compatible Chat Completions + Qwen `qwen3.8-max-0902`；最多两轮工具调用。
- 业务工具：仅 `find_player_matches`、`get_live_matches`、`get_match`。
- 刷新：初次加载、用户提问和手动刷新；P1 不自动轮询。
- 测试：确定性 fake provider/fake LLM 为默认；真实 provider/LLM 为 opt-in；Playwright 覆盖功能与视觉。
- 视觉视口：桌面 `1440×1000`，移动端 `390×844`。

## P2 已批准方案

- 供应商：API-Tennis 同时承担 Home/Match REST 和 per-match WebSocket；P1 provider 保留为备用 adapter。
- 进程：FastAPI 与独立 Realtime Worker，同仓库共享 domain/repository，不拆微服务。
- 持久化：PostgreSQL 保存稳定 identity、live state、PBP、统计变化、近期控制指数和 provenance；raw payload 14 天清理。
- 协调：Redis 保存 viewer lease、demand index、hot snapshot 和 pub/sub；Redis 丢失可由 PostgreSQL + REST 恢复。
- 实时协议：初始完整 snapshot + 版本化 SSE 增量；缺口、重连或 stale 时 REST 重同步。
- 订阅：只订阅被观看的比赛；同一比赛共享上游连接；隐藏标签页 60 秒释放，最后 viewer 离开后保留 60 秒 grace。
- 历史：使用 API-Tennis fixtures/H2H 按需查询，短 TTL cache，不做全量历史回填。
- 统计：支持 22 个语义明确的 canonical 指标；未知、缺失、partial 不猜测、不当作零。
- 走势：Recent Control v1 使用发球校正残差、校准参数和 EWMA；最近 20 分只是展示窗口，关键分不使用固定倍率。
- 测试：确定性 Replay 为主要实时门；真实 API-Tennis REST/WebSocket 和真实 LLM 为 opt-in smoke；Playwright 覆盖功能与双视口视觉。
- 配置：仓库根目录 `.env` 是 FastAPI、Next.js、Playwright 和真实测试的唯一本地配置入口；安全变量模板只保留根目录 `.env.example`。

## P2.6 已批准方案

- 排名页：ATP/WTA 单打 Top 200、官方顺序、每页 50、国家筛选和中国球员快捷筛选；不做双打。
- 搜索：无 query 时只展示 Top 200；有 query 时搜索全部本地已知单打球员，允许 Top 200 外或暂无当前排名的结果。
- Profile：英文主名、中文辅名、可用档案、当前排名/积分/变动、赛季胜负/胜率/冠军/分场地胜负，以及 live 优先、next 次之、否则“暂无比赛信息”的当前状态。
- 历史：默认当前赛季，可选当前及前四赛季，每页 20，按赛事级别和胜/负筛选；不提供场地筛选，不复制完整供应商历史。
- 身份：PostgreSQL 保存内部 Player、API-Tennis external ID、aliases 和有限排名快照；第三方 ID 不作为主键且不进入公共响应。
- 中文名：可信来源优先，缺失时使用现有 OpenAI-compatible LLM 离线批量生成；重复运行只补缺，严格 batch 校验失败时零写入，UI 不展示生成来源。
- 解析：同一 PlayerResolver 支持完整英文名、姓氏、供应商缩写、中文名、姓名顺序、大小写、标点和重音差异；Match context 可唯一消歧，其余冲突返回候选。
- Chat：Home/Match tools 先得到 resolver 领域结果再按内部 ID 查询；`ambiguous` 和 `not_found` 以自然澄清 + SSE `done` 结束。
- 页面：先由 v0 补齐并冻结 `/players` 与 `/players/[playerId]` 视觉，再由 ADE 严格按原型接真实数据；桌面 `1440×1000`、移动 `390×844`。
- 运行：本地显式执行目录同步与中文 enrichment；真实 API 启动不自动同步，不新增 cron、队列、daemon 或云部署。

## P1 成功标准

P1 完成时，用户可以从 Home 提问，得到可信结构化比赛卡片，打开内部 ID 对应的 Match Page，并继续当前比赛上下文问答。支持的问题必须由确定性 REST 和 LLM 工具路径共同验证；模型或供应商失败不得生成虚构事实。

验收问题与逐项门槛见 [ROADMAP.md](./ROADMAP.md)。

## 权威与冲突规则

| 信息类型 | 权威来源 |
|---|---|
| 产品定位、范围、优先级 | `PROJECT.md` 与 `ROADMAP.md` |
| 当前任务、执行者、分支和交接 | `CURRENT.md` |
| 运行事实、实现状态 | 代码、测试结果与 Git HEAD |
| 详细设计和实施步骤 | `docs/` 下已链接的规格与计划 |

如果总控与代码、测试或 Git HEAD 不一致，以已验证的实现事实为准并立即修正总控。`docs/` 中的详细说明不能静默覆盖根目录总控中的产品边界或优先级。

## 维护规则

仅当产品边界、架构原则、技术基线或长期成功标准变化时更新本文件。任务进度不得写在这里；阶段和任务状态写入 `ROADMAP.md`，日常执行和交接写入 `CURRENT.md`。
