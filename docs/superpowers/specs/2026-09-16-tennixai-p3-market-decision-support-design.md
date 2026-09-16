# TennixAI P3 Market & Decision Support 设计规格

**状态：** 已批准；2026-09-16 用户授权剩余设计项统一采用推荐方案，不再逐项确认
**日期：** 2026-09-16
**所属阶段：** P3 — Market & Decision Support
**交付目标：** 本地完整运行、私人 paper testing、最多分享给少量好友
**前置基线：** P2（含 T54）已关闭；T55 从 `7409806` 开始设计冻结
**研究依据：** [P3 网球胜率预测与决策支持调研](../../research/2026-09-15-tennis-win-probability-sota.md)
**实施计划：** [P3 实施计划](../plans/2026-09-16-tennixai-p3-implementation.md)
**v0 交付：** [P3 页面与状态矩阵 v0 Prompt](../../v0/2026-09-16-p3-market-decision-pages-prompt.md)

## 1. 结论

P3 把 TennixAI 从 Live Match Intelligence 扩展为只读市场情报与可审计 paper decision 产品。首版同时覆盖赛前和赛中，但只处理网球单场胜者市场；Polymarket 提供市场价格、订单簿、规则与最终判定，API-Tennis 提供比赛事实，独立网球模型估计胜率，Decision Engine 比较保守模型概率与固定 `$10` 的真实可执行成本。

系统不是自动交易机器人。它不连接钱包、不签名、不发送真实订单，也不承诺延迟套利。LLM 只解释已冻结的结构化事实，不能生成概率、edge、动作、成交或结算。

P3 的正确结果可以是 `NO BET`。若数据、许可、模型校准、市场映射、流动性或 shadow 证据不足，生产界面不得为了“功能完整”强行显示 `BUY`。

## 2. 产品范围

### 2.1 包含

- 赛前与赛中的网球单场胜者市场；
- Home 最多三行的「市场脉搏」；
- 独立 `/markets` 页面，包含“机会 / 全部市场 / Paper 账本”三视图；
- Match Page 全宽 `DecisionSummary`、概率—市场轨迹、结构化判断依据和 paper lifecycle；
- 大满贯与 ATP/WTA 主巡赛单打的模型覆盖；
- Challenger、ITF 和其他可识别赛事的市场展示，但不提供模型标记或建议；
- 固定 `$10`、每场最多一次 FOK 入场和一次 FOK 退出的自动 paper lifecycle；
- `HODL_BASELINE`、`EV_EXIT`、`CONVERGENCE_LOCK` 三条可比较轨道；
- API-Tennis 与 Polymarket 双 WebSocket、彼此独立的后端版本化 SSE；
- PostgreSQL 审计账本、Redis 热状态、Replay 与真实只读 smoke；
- Home/Match Chat 对 canonical P3 事实的只读解释。

### 2.2 明确不包含

- 盘口、总局数、单盘、局或球员 props 等其他市场；
- Challenger/ITF 的模型建议；
- 真实下单、钱包、签名、API trading credentials 或自动交易；
- 多次入场、追价、加仓、减仓、换边、重新入场或 partial position；
- 动态止损、任意止盈、Kelly 仓位或组合资金管理；
- 用当前 Polymarket 价格训练“独立”模型后再与同一价格比较；
- LLM 估概率、补统计、决定动作或推断成交；
- Kafka、Kubernetes、新微服务、Feature Store、Vector DB 或新搜索基础设施；
- 云部署、认证、多用户账本或好友之间共享 paper 仓位。

## 3. 稳定边界

P3 在现有稳定依赖方向上增加四个独立语义层：

1. `MarketDataProvider` 把 Polymarket 数据映射为 canonical market/order-book/rule/resolution；
2. `PredictionService` 只读取网球数据，输出校准概率、不确定性与结构化依据；
3. `DecisionService` 读取 prediction 与可执行市场状态，输出 observation 与动作；
4. `PaperTradingService` 只消费已提交的 decision/intents 和真实 delay 后订单簿，维护 paper ledger。

供应商 DTO、模型实现、LLM 和前端均可替换；以下语义必须稳定：

- internal `match_id` / `player_id`；
- market-to-match 的精确组合规则；
- prediction、quote、decision、intent、fill、position 和 settlement 的边界；
- 版本、freshness、stale/gap 与 provenance；
- 交易动作与风险降低选项的区分；
- 生产 paper 状态只能由后端和 PostgreSQL ledger 确认。

## 4. Canonical domain

供应商字段不得越过 adapter。公共 DTO 不出现 Gamma/CLOB event、condition、token 或 API-Tennis external ID。

| 模型 | 核心语义 |
|---|---|
| `Market` | 内部 `market_id`、问题、两个内部球员 outcome、market lifecycle、规则版本、开始/结束时间 |
| `MarketExternalId` | 内部 market 与 provider event/condition/token IDs 的私有映射 |
| `MarketRules` | 原始规则最小审计快照、规则 hash、resolution source、异常语义、抓取时间 |
| `OrderBookState` | 每侧 bids/asks、provider/received timestamp、sequence/hash、freshness |
| `ExecutableQuote` | 固定 stake/份额的逐档均价、费用、滑点、可成交量、book version |
| `PredictionSnapshot` | 双方校准概率、不确定性区间、model/calibration/data versions、输入 match version、依据与能力状态 |
| `DecisionObservation` | prediction + quote + policy version + gates + `BUY/WAIT/NO_BET/HOLD/SELL`，不等于持仓 |
| `PaperOrderIntent` | 唯一 entry/exit intent、FOK、触发 observation、delay、门槛和幂等键 |
| `PaperFill` | delay 后实际 book 上的全额 fill/no-fill、逐档均价、费用和原因 |
| `PaperPosition` | 单场唯一主 position、成本、份额、当前可退出价值和生命周期 |
| `PaperTrackResult` | EV 主轨道或 HODL/convergence-lock 反事实的退出/结算结果 |
| `MarketResolution` | provider 最终 outcome、payout、resolution status、规则版本和确认时间 |

业务动作和账本状态必须分开。`BUY`/`SELL` 是 Decision Engine 的瞬时结论；`ENTRY_PENDING`/`FILLED`/`EXITED` 是 ledger 事实。

## 5. Polymarket provider 与精确组合

### 5.1 Provider contract

`MarketDataProvider` 至少提供：

```python
class MarketDataProvider(Protocol):
    async def list_tennis_moneylines(self) -> tuple[Market, ...]: ...
    async def get_market(self, market_id: str) -> Market: ...
    async def get_order_book(self, market_id: str) -> OrderBookState: ...
    def subscribe_order_books(self, market_ids: tuple[str, ...]) -> AsyncIterator[MarketEnvelope]: ...
    async def get_resolution(self, market_id: str) -> MarketResolution | None: ...
```

首版只使用公开只读 Gamma、CLOB REST 与 market WebSocket。不得装配 authenticated trading client，也不得请求 wallet/private key。

### 5.2 Market-to-match

- Polymarket 与 API-Tennis 各自保留 provider identity；第三方 ID 不作为业务主键。
- moneyline 的两个完整 outcome 名称先经过现有 `PlayerResolver` 得到内部 Player ID。
- 只有无序 Player ID 对唯一一致、比赛时间处于允许窗口、赛事上下文无冲突时才能组成 `DecisionContext`。
- LLM、字符串模糊分数或人工永久绑定不能成为最终连接依据。
- 组合失败时市场仍可在“全部市场”展示，但不显示模型覆盖、概率、edge 或负向“未验证”标签；同步后可自动重试。
- intent 创建后关系冻结；市场 condition 被替换时不得把已有 intent/position 迁移到新市场。尚未产生 intent 时允许重新组合。

### 5.3 规则快照

每个可追踪市场保存当前规则文字的最小审计快照、hash、resolution source 与解析结果。raw provider payload 仍按 14 天清理；已用于 decision/intent/position 的规则快照作为 canonical ledger evidence 长期保留。

规则 hash 改变时，新的 `BUY/SELL` 立即被 `RULE_CHANGED` hard gate 抑制，直到新版本完成确定性解析；已有 position 不猜测结算，继续等待实际 resolution。

## 6. 独立概率体系

### 6.1 赛前候选

首轮统一 benchmark 保留：

- overall + surface Elo；
- Glicko 或 dynamic Bradley–Terry；
- HGBM challenger，特征只来自预测时点之前可得的结构化网球数据。

不先指定唯一 champion。深度神经网络不是首版必需依赖；只有在同一 benchmark 上胜出且可重放时才能晋升。

### 6.2 赛中结构模型

- `ScoringProbabilityEngine` 用当前盘、局、分、发球方、赛制和 tiebreak 规则确定性计算整场胜率；
- 发球分能力从赛前 prior 开始，用 beta-binomial 或等价 empirical-Bayes shrinkage 吸收当场证据；
- PBP 缺失时退化到比分 + prior，并降低 confidence；比分、发球方或赛制不足时弃权；
- hybrid HGBM 只学习结构模型残差，不能重新学习或猜测网球计分规则。

### 6.3 校准与解释

- Platt/logistic、isotonic 与 beta calibration 在 validation 上比较；
- 每个输出携带 model、feature、calibration、training-window 与 code version；
- 解释项由模型/特征引擎结构化生成，例如 surface rating、发球 prior、当前比分、live shrinkage 和数据降级；
- LLM 可把解释项改写成自然语言，但不能增删数值依据或创造 feature attribution。

### 6.4 市场隔离

当前 Polymarket price、spread、volume、order book 或后续 resolution 均不得进入 independent model。它们只进入 Decision Engine 和独立的 market-informed benchmark；后者不能被包装成独立 edge。

## 7. 数据、benchmark 与模型晋升门

### 7.1 许可与覆盖审计

在训练前先输出可版本化 audit：数据来源、许可、赛季、ATP/WTA、surface、赛制、球员冷启动、API-Tennis runtime 字段覆盖、PBP 缺口、修订、乱序和退赛比例。未获得明确训练许可的供应商 raw data 不得自动累积为长期商业训练集。

历史训练数据通过可替换 `HistoricalMatchSource` 从本地路径读入；仓库只提交脱敏、最小确定性 fixture，不提交受限完整数据集。

### 7.2 切分与指标

- chronological walk-forward；同一比赛的所有 point states 只能位于同一 split；
- train 拟合，validation 选择模型/校准器/策略阈值，untouched out-of-time test 只做最终报告；
- 主指标为 log loss，辅以 Brier、reliability/cumulative calibration、ECE + bootstrap 区间、accuracy；
- ATP/WTA、surface、赛前/赛中阶段、best-of-3/best-of-5 和 data-quality 分层报告；
- 决策层报告 risk–coverage、机会数、NO BET 原因、fill rate、net EV、ROI、最大回撤与三条 paper track；
- 市场回放必须使用当时可执行 book、实际 fee 与 sports delay，禁止 midpoint、未来价格或结算泄漏。

### 7.3 预先声明的选择规则

1. 淘汰不可重放、泄漏、许可不清或关键 subgroup 系统失准的候选；
2. 在 out-of-time proper scoring 上比较，差异落在 bootstrap 不确定区间内时选择更简单的模型；
3. calibrator 只由 validation 选择，不读取 test；
4. decision threshold 只由 validation + shadow order-book replay 选择，目标是扣成本后净 EV 的保守下界；
5. 若没有候选能证明可信正下界，则 production policy 只能输出 `NO BET`，不能降低门槛凑出 `BUY`；
6. 模型、校准器和 policy 只有在 versioned model card、benchmark report 与 artifact hash 齐全时才可装载。

P3 完成不以“必须盈利”为验收条件，而以不会把失准概率、未来信息或不可成交价格伪装成机会为条件。

## 8. 可执行价格与 Decision Engine

### 8.1 Quote

- entry 使用对应 outcome 的 ask/depth；exit 使用当前持仓 outcome 的 bid/depth；
- 固定 `$10` 逐档计算份额、平均价、真实 fee、price improvement 与可成交量；
- displayed midpoint、last trade 或 best level 不能替代整笔可执行 quote；
- fee schedule、minimum size、tick、sports delay 都来自当前 market metadata，不硬编码；
- book stale、hash/sequence 缺口或深度不足时 quote 不可执行。

### 8.2 持仓前动作

- `BUY A/B`：模型适用域、数据、映射、规则、freshness、流动性和 promotion hard gates 全部通过，保守净 edge 超过 versioned policy；
- `WAIT`：已有明确低估方向，但当前 `$10` 可执行均价未过门，同时显示动态最高可接受均价；
- `NO BET`：市场一致、模型未晋升或任一 hard gate 失败，并显示稳定 reason code；
- `MARKET_ONLY`：不在模型覆盖域或尚未精确组合，只显示市场事实。

### 8.3 持仓后动作

- `HOLD`：净可执行退出价值未高于 uncertainty-adjusted hold value；
- `SELL`：首次达到 EV-exit policy，创建唯一全仓 FOK intent；
- `LOCK PROFIT`：单独显示的风险降低选项，不是主动作，不改变主 ledger；
- fixed take-profit 仅作离线诊断 benchmark。

## 9. Paper lifecycle

### 9.1 Entry

- 每个 internal `match_id` 最多一条 entry intent；
- 首个合格 `BUY` 冻结 observation、rules、quote、book、model 与 policy version；
- 按 market 当前 sports delay 等待后，用届时 order book 执行 FOK；
- 全额满足价格/深度/费用门才 `FILLED`，否则 `NO_FILL → MISSED`；
- 不 partial fill、不追价、不 retry，也不以后来的有利价格替换首次信号。

### 9.2 Position 与 exit

- fill 经 PostgreSQL 提交后，同一 `DecisionSummary` 原地变为 position；
- 主轨道第一次 `SELL` 创建唯一全仓 FOK exit intent；
- 完整成交为 `EXITED`；no-fill 为 `EXIT_MISSED`，此后主 position 持有至结算；
- 同场不加仓、不换边、不重新入场；
- HODL 与 convergence-lock 从相同 entry 分叉为反事实，不生成额外组合仓位。

### 9.3 状态序列

用户可见业务序列为：

- `MARKET_ONLY`；
- 持仓前 `NO BET / WAIT / BUY`；
- `ENTRY_PENDING → FILLED` 或 `MISSED`；
- 持仓中 `HOLD / SELL`；
- `EXIT_PENDING → EXITED` 或 `EXIT_MISSED`；
- 最终 `SETTLED`。

`STALE / GAP` 是可叠加覆盖层，不替换 ledger 状态。它保留最后可信快照和时间、撤销新的 `BUY/SELL`。pending intent 到期若无法核验 book，只能记录 `BOOK_UNVERIFIABLE` no-fill，不能伪造成交。

## 10. 异常比赛与市场结算

Polymarket 官方规则明确：每个市场自己的 resolution rules 决定来源、截止时间和 edge cases；最终判定可经历 proposal、challenge、dispute 或 50–50。TennixAI 因此采用以下推荐政策：

- paper position 只服从该 market 的实际 final resolution/payout，不直接用 API-Tennis winner 提前结算；
- retirement/default/disqualification、walkover、取消、延期和 50–50 的具体处理来自该 market 的规则快照与最终 resolution；
- 比赛开始后退赛可让 winner/advancing player 与市场 outcome 一致，但只能作为等待/核对信息，不能替代市场 resolution；
- 赛前 walkover、未比赛取消或超期经常按 50–50，但不得将这一模板硬编码为所有市场规则；实际 50–50 时每份 outcome token 按 `$0.50` 结算；
- suspended/postponed 时停止新动作，已有 position 标记 `RESOLUTION_PENDING` 或 stale，等待比赛恢复或市场最终判定；
- market closed 但尚未 final resolved 时不显示 realized P&L；
- disputed/clarification 状态持续保留 position 与规则版本，不设本地超时猜结果；
- 规则无法解析或发生变化时禁止新 intent；已有 ledger 等待 provider final resolution；
- condition 被新市场替换时，旧 intent/position 留在旧 market，新 market 不继承历史成交。

## 11. 实时与持久化

### 11.1 双流 ownership

后端分别拥有 API-Tennis live/PBP 与 Polymarket order-book WebSocket。浏览器不直连供应商，只消费 canonical REST snapshot 和版本化 SSE。

- sports event 触发 prediction 与 decision 重算；
- book 的有效变化复用最新有效 prediction，只重算 quote/edge/action；
- 两流各自保存 provider timestamp、received timestamp、sequence/hash/version 与 freshness，不等待“时间戳完全相同”；
- 任何关键 stale、gap、out-of-order 或 rule change 都撤销新动作；
- 后台跟踪进入窗口且精确组合的模型覆盖比赛，以及所有未结 position；浏览器开关不控制 paper lifecycle。

### 11.2 写入分流

- ingress 只校验 envelope、打接收时间并进入有界 per-match queue；
- API-Tennis canonical reduction 延续 PostgreSQL DB-first；
- 高频 market book 用单写者内存 reducer，Redis 保存热 snapshot/pub-sub；不逐 delta 同步写 SQL；
- 改变固定 `$10` quote、动作或模型对照的 observation，以及有界周期采样，异步批量写 PostgreSQL；
- intent、fill/no-fill、position、exit 和 settlement 使用同步 PostgreSQL transaction + 唯一幂等键，commit 后才发布；
- raw provider event 14 天清理；canonical identity、rules evidence、decision observations 与 paper ledger 长期保留；
- P3 不新增 Kafka/Redis Streams。只有真实 backlog、恢复或多消费者证据达到门槛时才在 P4 评估。

### 11.3 本地延迟门

Replay 条件下记录分段 p50/p95/p99：ingress→canonical、canonical→prediction、prediction/book→decision、ledger commit→SSE。目标是 market book 有效变化到可见 decision p95 小于 500ms，sports canonical update 到可见 decision p95 小于 1s；外部供应商网络延迟和官方 sports order delay 单独报告，不混入本地处理指标。

## 12. REST、SSE 与 Chat contracts

### 12.1 REST/SSE

推荐的业务端点：

```text
GET /api/v1/markets/opportunities
GET /api/v1/markets
GET /api/v1/paper/positions
GET /api/v1/markets/pulse
GET /api/v1/markets/stream
GET /api/v1/matches/{match_id}/decision
GET /api/v1/matches/{match_id}/decision/stream
```

列表响应使用内部 `match_id/market_id/player_id`；分页、tier/gender/phase filters 是 canonical 枚举。`markets/stream` 发布 `market_delta`、`decision_delta`、`paper_delta`、`resolution_delta` 和 heartbeat。既有 Match sports stream 保持原契约；新增 Decision stream 单独发布 `ready`、`decision_delta` 与 heartbeat，并使用自己的 version cursor。前端同时运行 `useMatchStream` 与 `useDecisionStream`，任一流出现缺口只重新获取自己的 snapshot，避免 P3 状态污染 P2 sports version。

浏览器检测版本缺口时重新 GET snapshot，不把 SSE patch 猜成完整状态。Next.js Route Handler 继续做薄代理，不保存业务状态。

### 12.2 Chat

新增两个业务语义工具即可：

```text
list_market_opportunities
get_match_decision
```

Home Chat 可回答当前机会与市场状态；Match Chat 自动注入 `match_id`，解释当前 prediction、quote、gates、action、position 和 lifecycle。工具只返回 compact canonical fact packet。LLM 不得创建 intent、改变 ledger、重算概率或用自然语言覆盖 structured action。

## 13. 页面与交互

现有 v0 深色网球数据终端是视觉真源。P3 只扩展组件与页面，不改 logo、全站字体、token、圆角、header 或 P1/P2 视觉语言。

### 13.1 Home「市场脉搏」

- 最多三行；有开放 position 时固定保留一行，并优先 `SELL`、`LOCK PROFIT`、stale/gap；
- 其余按 live `BUY` → upcoming `BUY` → strongest `WAIT`；
- 每行只显示比赛、模型概率、`$10` 可执行市场概率、当前状态与 freshness；
- 点击整行进入内部 Match Page，“查看全部”进入 `/markets`；
- 不显示下单按钮、轨迹或详细 ledger；无机会时诚实显示空态。

### 13.2 `/markets`

页面级 tabs 固定为：

- **机会：** 模型覆盖的 `BUY/WAIT`，live 在前；卡片显示比赛/赛事、阶段、模型概率、`$10` 可执行均价、保守净 edge、动作、WAIT 最高价和 freshness；
- **全部市场：** 所有可识别 moneyline，按 ATP/WTA → Challenger → ITF → other，再按 live/time；模型覆盖的 `NO BET` 显示原因，低级别只显示两侧可执行价格、spread/depth 与 freshness；
- **Paper 账本：** open position 在前，再列 pending、recent exit/missed/settled；显示方向、成本/份额、当前可退出价值、主状态、净 P&L、freshness，点击进入单场 lifecycle。

同一行/卡片整体可点击，不放模拟 BUY/SELL 控件。桌面使用高密度列表；移动端压成单列卡片但保留关键数字和至少 44px 触控目标。

### 13.3 Match desktop 顺序

采用已经批准的 decision-first 方案：

1. 既有 Hero；
2. 跨两栏全宽 `DecisionSummary`；
3. 主栏依次为比赛概览、详细比分/进程、概率—市场轨迹、判断依据与 hard gates、技术统计、近期控制/PBP、paper lifecycle；
4. paper lifecycle 在从未出现 intent 时隐藏，出现后永久保留审计时间线；
5. 右侧粘性栏依次为 Match Assistant 与关键事实；
6. 移除旧 `MarketCard` 和主栏重复的 AI Insights/问题建议卡，提示问题统一由 Assistant 承担。

概率轨迹用两条可辨识线展示 model 与 executable market probability，模型不确定性用 band；stale/gap 用断线和阴影，不插值。图下必须有可访问的数据摘要/表，颜色不是唯一编码。

`Decision Evidence` 只展示结构化原因、模型/数据版本、hard gates 和降级；不显示 LLM 自造数值归因。

### 13.4 Match mobile 顺序

移动端不复制桌面两栏 DOM 顺序，固定为：Hero → `DecisionSummary` → 详细比分 → 关键事实/比赛概览 → 概率—市场轨迹 → 判断依据/hard gates → 技术统计 → 近期控制/PBP → paper lifecycle（若存在）→ Match Assistant。

Hero 与 `DecisionSummary` 保留“问这场比赛”入口，点击滚动并聚焦底部 Assistant；不增加永久占屏的浮动交易按钮。数据更新不得导致卡片高度剧烈跳动或把用户滚动位置拉回顶部。

### 13.5 Loading、empty、stale 与 error

- route loading 使用与最终列表/卡片同形的 skeleton，避免布局跳动；
- “暂无机会”“筛选后无市场”“暂无 paper 记录”“供应商暂无市场”使用不同空态文案；
- 单一上游失败保留另一侧和最后可信状态，以局部 banner/row status 表达；
- stale/gap 不清空数字，明确显示最后可信时间并撤销动作；
- 完整加载失败才使用 page-level error + retry；
- pending intent 禁止显示成功色或成交文案；
- 状态不能只靠红/绿颜色，必须有文字、icon 与可访问标签；
- focus、heading hierarchy、reduced motion、键盘 tabs 和 390px 无横向溢出属于原型验收门。

## 14. v0 状态矩阵

v0 必须提供确定性 preview switcher，覆盖全部业务状态；视觉回归只截取代表状态，避免把瞬时近似状态全部复制成独立页面。

| 页面 | 必须可切换状态 | 视觉基线（桌面 + 移动） |
|---|---|---|
| Home | populated pulse、open position/stale、empty | populated、empty |
| `/markets` 机会 | BUY + WAIT、empty、partial stale | populated、empty |
| `/markets` 全部 | 主巡模型覆盖 + 低级别 market-only、叠加筛选、filter empty | mixed catalog、filtered empty |
| `/markets` Paper | pending/open、exited/missed/settled、empty | open + recent、empty |
| Match | MARKET_ONLY、NO BET、WAIT、BUY、ENTRY_PENDING、MISSED、FILLED/HOLD、SELL、EXIT_PENDING、EXITED、EXIT_MISSED、SETTLED、STALE/GAP overlay | MARKET_ONLY、WAIT、ENTRY_PENDING、HOLD、EXIT_PENDING、SETTLED、STALE/GAP |

共 26 张代表性基线：Home 4、Markets 8、Match 14，视口沿用 `1440×1000` 与 `390×844`。每张由人逐张核对后才入 Git；生产数据接入任务不得自行重设计或批量接受未知 pixel diff。

## 15. 安全、隐私与运行边界

- 根目录 `.env` 是唯一人工配置入口；不创建子目录 env；
- public Polymarket read-only endpoints 不需要交易凭据；仓库和本地配置都不引入 private key/wallet seed；
- API key、provider IDs、raw payload、完整 order book 和训练数据路径不得进入公共 DTO、截图、日志或文档；
- paper ledger 是单机产品账本，不绑定用户钱包或真实仓位；
- 所有金额明确标注 paper、USD/USDC 语义和 fee inclusion；
- UI 保留研究/非财务建议说明，但不以免责声明替代数据质量和执行门。

## 16. 验收门

### 16.1 确定性门

- domain invariants、strict mapping、rule hash、order-book reducer、executable quote、scoring engine、shrinkage、calibration、decision gates 与完整 paper state machine 单测；
- migration upgrade→downgrade→upgrade、唯一幂等键、事务回滚、重启恢复和 14 天 raw cleanup integration；
- 双流 Replay 覆盖 out-of-order、gap、stale、PBP correction、book hash reset、rule change、entry/exit delay、FOK fill/no-fill、retirement/walkover/50–50/dispute/final resolution；
- frontend unit、typecheck、build；Home/Markets/Match 功能 E2E 与 26 张双视口视觉基线；
- P1/P2 全量回归零意外基线变化。

### 16.2 真实只读门

- API-Tennis REST/WebSocket 与 Polymarket Gamma/CLOB/WebSocket 分别 smoke；
- 主巡 moneyline strict mapping coverage 与零多候选报告；
- 至少一场真实赛前与一场真实赛中从 provider→canonical→prediction/NO BET→SSE→浏览器完整通过；若当期无适合赛事则诚实 skip 并保留 Replay gate；
- 真实 market rules、fee、delay 与 resolution metadata 被读取而非硬编码；
- 浏览器无 provider IDs、key、raw payload、console error 或伪造 BUY/fill；
- 本地 p50/p95/p99 延迟与 queue/backlog 指标达到 §11.3，或以真实证据阻止发布而非删门。

### 16.3 模型与策略门

- 数据许可/覆盖 audit、walk-forward benchmark、model card、calibration report 与 artifact hashes 齐全；
- market-independent 特征扫描无当前/未来 market 字段；
- threshold 只来自 validation/shadow；untouched test 不参与选择；
- 没有可信 net-EV 下界时 production 只输出 `NO BET`；这属于通过，不属于功能失败；
- 任何真实 `BUY/SELL` 标签都能回溯到版本化 prediction、quote、policy、book 与 ledger transition。

## 17. P4 延期项

P4 可依据真实 paper evidence 评估 FAK/partial、重试、拆单、重复入场、仓位大小、止盈止损、模型在线更新、更多市场类型和更复杂组合分析。自动下单仍需独立法律、风控、安全和执行设计，不能因 P3 paper ledger 存在而自动获得授权。

## 18. 主要官方来源

- [Polymarket Prices & Orderbook](https://docs.polymarket.com/concepts/prices-orderbook)
- [Polymarket WebSocket market channel](https://docs.polymarket.com/api-reference/wss/market)
- [Polymarket Order Lifecycle](https://docs.polymarket.com/concepts/order-lifecycle)
- [Polymarket Resolution](https://docs.polymarket.com/concepts/resolution)
- [Polymarket Market API](https://docs.polymarket.com/api-reference/markets/get-market-by-id)
- [Polymarket CLOB V2 market info](https://docs.polymarket.com/api-reference/markets/get-clob-market-info)
- [Polymarket CLOB V2 migration](https://docs.polymarket.com/v2-migration)
- [API-Tennis REST documentation](https://api-tennis.com/documentation)
- [API-Tennis WebSocket documentation](https://api-tennis.com/documentation_websocket)
