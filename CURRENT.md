# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-16 09:06 CST

**当前任务：** T55 — Freeze P3 Market & Decision Support Design and Prototype Brief

**任务状态：** `in_progress`

**执行者 / ADE：** Codex / Codex Desktop

**分支：** `main`

**任务起始提交：** `7409806`

**领取提交：** `b6539e4`

**设计提交：** —

**产品提交：** —（T55 只授权设计，不授权实现）

**关闭提交：** —

**当前动作：** P3 SOTA 研究方向、覆盖与组合边界、独立估值、持仓前后动作语义、paper 生命周期、实时架构、三层页面结构，以及 `/markets` 三视图均已获用户批准。下一步冻结 Home 的市场/持仓摘要，再细化 Match 工作台和 v0 原型状态。

**当前状态：** P2（含 T54）保持已关闭；P3.0 仅进入 design freeze。研究报告位于 `docs/research/2026-09-15-tennis-win-probability-sota.md`；其模型选择方法和 market-to-match 方向已批准，但仍不是完整 P3 规格。具体 champion、校准器和 decision 阈值必须在数据覆盖审计与统一 benchmark 后决定。P4 已确定为 P1–P3 框架完成后的统一打磨阶段；当前没有 P3 provider、schema、prediction、decision、paper ledger、页面或交易能力，自动下单仍属独立延期阶段。

## T55 研究节点（2026-09-15）

- 调研覆盖赛前/赛中胜率、结构化 Markov、动态 rating、Bayesian live update、hybrid ML、概率校准、risk–coverage、市场效率与数据许可。
- 关键结论：公开研究不存在可直接照搬的统一 SOTA；P3 应冻结可复现 benchmark 和模型晋升门，而非凭单篇论文选择算法。
- 市场门修正为可执行价格：Polymarket 页面展示价通常不是实际买入价；paper decision 必须使用 ask/订单簿深度、市场实际费率、滑点和不确定性边际。
- 推荐边界：LLM 只解释结构化输出；当前市场价不进入独立网球模型；证据、数据、映射或流动性不足时输出明确 `NO BET`。
- 退出研究结论：不存在脱离目标函数、风险偏好、交易成本和 alpha 持续性的通用最优卖点；“市场价追上模型点估计就自动卖”不能直接冻结为唯一规则。风险中性时应比较净可执行卖出所得与模型继续持有价值；锁定同等期望利润属于降低方差的选择，必须单独标识。
- Polymarket 执行事实：卖出须使用实际订单簿 bid/depth，且要计入逐市场费率与 sports order delay；2026-09-15 只读样本显示当期 tennis moneyline 常见 `secondsDelay=1`，不同市场版本的 `feeSchedule.rate` 出现 `0.03` 与 `0.05`，进一步证明不能硬编码或按信号时盘口假装成交。
- 热路径核验：交易所官方经验要求 WebSocket 回调避免 I/O 与慢消费；Redis Pub/Sub 是 at-most-once，当前本地 Redis 又是 `appendonly=no`，不能承担不可丢账本；PostgreSQL 当前 `synchronous_commit=on`、`fsync=on`。本机临时探针中 PostgreSQL 300 次同步小事务 median/p95 为 0.945/1.116ms，Redis 500 次 set+publish 为 0.571/0.696ms；现有完整 reduction 集成用例单次 call 0.08s。证据支持按事件类别分流，而不是全同步或全异步。
- 已批准退出语义：`SELL` 是净可执行卖出价值高于稳健持有价值时的期望值动作；`LOCK PROFIT` 是市场回到模型合理区间时的可选风险降低动作，两者不得混用。具体数值阈值和候选规则仍须由 walk-forward/shadow 数据选择。
- 尚未批准或实施：候选模型 champion、绝对阈值、训练数据许可方案、P3 数据/服务契约、页面改版和任何交易能力。

## T55 已批准边界与 market-to-match spike（2026-09-15）

- 模型覆盖：只为大满贯和 ATP/WTA 主巡赛单打显示正向 `模型覆盖` 标记，并在这些比赛上提供胜率、edge、模型观点与 `BUY / WAIT / NO BET`；Challenger/ITF 仍展示比赛和 Polymarket 市场，但不显示“未验证”等负向标记，也不提供模型建议。
- 数据关系：Polymarket 市场与 API-Tennis 比赛各自保留 provider ID；不建立需要人工维护的永久绑定，不用 LLM 或模糊置信分做最终连接。
- 组合规则：先把 Polymarket moneyline 的两个完整 outcome 名称解析为内部 Player ID，再与 API-Tennis 的无序 Player ID 对做运行时精确连接；只有唯一且上下文无冲突的结果才能组成 `DecisionContext`。失败时市场照常展示、不显示模型标记，后续同步自动重试。
- 真实只读 spike：2026-09-15 至 09-16 共 125 个有效 Polymarket 网球 moneyline、477 条 API-Tennis 赛程/比赛记录；79 个唯一连接（63.2%）、0 个多候选，成功项开赛时间差中位数 0 分钟、最大 45 分钟。成功项含 WTA Singles 18、男子 Challenger 42、女子 Challenger 19；该窗口无 ATP 主巡赛样本。
- 失败分布：25 个市场至少一名球员未进入当前目录，21 个已解析球员对没有 API 当期记录，样本主要集中在低级别赛事；这不阻塞低级别市场独立展示。ATP 主巡赛及更多大满贯/WTA 样本仍须在实施阶段 shadow 验证，不能用本次窗口宣称全面覆盖。

## T55 已批准 paper opportunity（2026-09-15）

- `DecisionObservation` 与 `PaperPosition` 必须分离：系统保存同一场比赛中每个有效决策时点的模型概率、市场可执行价、edge、数据版本与结论，用于赛后分析；这些观察记录不等于多笔下注。
- 每个内部 `match_id` 最多建立一笔固定 `$10` 的模拟持仓。若赛前首次出现合格 `BUY`，即在该时点开仓；若赛前从未出现，则允许在赛中首次出现合格 `BUY` 时开仓。
- 一旦开仓，同场不加仓、不反向换边、不重新入场；最多执行一次退出。期望值动作 `SELL` 与可选风险降低动作 `LOCK PROFIT` 使用不同语义和评估轨道，不把“市场追上模型”自动等同为更高期望值。这样一场比赛仍只贡献一个明确且可审计的 position lifecycle，不会把高度相关的连续信号虚增成多次机会。
- 对提前退出的持仓，同时保存实际退出结果和“若继续持有到结算”的反事实结果，以检验退出时机是否真正改善收益；反事实不计作第二笔交易。
- 若整场没有出现合格 `BUY`，结果为 `NO BET`，不生成模拟持仓；所有合格与不合格观察仍可进入评估轨迹。
- 动态加仓、反向、重新入场、任意止盈止损和多次买卖统一留到 P4；P3 只建立最小的一次退出能力，并同时保存 HODL、EV-exit 与 convergence-lock 三条可比较轨道。固定止盈只作诊断 benchmark，具体阈值仍须用 observation 数据评估。

## T55 已批准独立估值原则（2026-09-15）

- P3 的目标不是利用比分源与市场之间的传输时差，而是在市场已吸收公开比赛状态后，由独立网球模型判断其是否高估或低估某位球员；数据新鲜度与对齐只属于防错门，不能计作模型 edge。
- 独立模型不读取当前 Polymarket 价格；市场价格只在 Decision Engine 中作为比较基准。双方意见一致通常意味着当前没有交易价值，不能为了产生建议而强行输出 `BUY`。
- 决策使用模型概率的保守估计与固定 `$10` 的真实可执行成本比较。只有扣除模型不确定性、订单簿价格、费用和滑点后仍超过待验证门槛，才构成可交易分歧。
- “看好球员”和“值得按当前价格买入”是两个判断：即使模型认为某球员更可能获胜，市场报价更高时也应等待或弃权；赛前与赛中持续重算价值—价格关系，入场时机来自错价窗口，而非抢比分延迟。

## T55 已批准持仓前动作语义（2026-09-15）

- 页面分别展示“模型观点”和“当前动作”，避免把胜负倾向、相对估值和可交易性混成一个标签。
- `BUY A/B`：模型适用域、数据质量、映射和流动性硬门均通过，固定 `$10` 按实际 ask/depth/费用/滑点计算后的保守净 edge 超过待验证阈值；只有该状态可创建 paper position。
- `WAIT`：模型已有明确的低估方向，但当前可执行价尚未通过保守净 edge 门；页面显示由当前保守概率、实际成本和安全边际反算的动态最高买入价。`WAIT` 不创建 paper position。
- `NO BET`：模型与市场处于合理一致区间，或任一数据、置信度、映射、流动性等硬门失败；必须展示具体原因。它表示“当前没有可论证的正 edge 入场”，不表示比赛、预测或最终盈利可能性没有意义。
- 动态最高买入价不是固定折扣：Decision Engine 对固定 `$10` 的候选成交逐档计价，求出仍满足保守净 edge 门的最高可接受平均成交价；费用、深度、模型或比赛状态变化时该价格随之变化。

## T55 已批准退出语义（2026-09-15）

- `HODL_BASELINE` 始终持有至结算，作为原始预测与入场质量的基线。
- `EV_EXIT` 对应产品动作 `SELL`：只有在市场实际 delay 后，按届时订单簿深度、部分/未成交和费用计算出的净卖出价值，高于模型不确定性调整后的继续持有价值时才建议卖出。
- `CONVERGENCE_LOCK` 对应产品动作 `LOCK PROFIT`：当市场回到模型合理区间时允许用户降低方差、锁定利润，但不得宣称该动作提高期望值。
- `FIXED_TAKE_PROFIT` 只作为诊断 benchmark，不进入默认产品建议。
- 三条策略轨道不分别生成多笔组合交易；真实 paper position 最多采用一次退出，同时保存未采用轨道和持有到结算的反事实结果。
- 模型概率必须先通过 proper scoring 与校准门；绝对阈值和具体规则不得凭直觉硬编码，只能依据独立 walk-forward/shadow 证据晋升。

## T55 已批准实时数据流（2026-09-15）

- 实时性是首要运行目标。后端分别维护 API-Tennis canonical match state 与 Polymarket canonical market/order-book state，浏览器不直连供应商，只接收后端统一的版本化 `DecisionSnapshot` SSE。
- API-Tennis 比赛/PBP 事件触发模型概率及 decision 更新；Polymarket 订单簿有效变化复用最新有效模型概率，只重算固定 `$10` 的可执行价、edge 与动作，避免无意义地重复运行模型。
- 两条流不等待时间戳完全相同才计算；各自保留 provider timestamp、received timestamp、sequence/version 和 freshness，使用最新且通过有效性门的状态。任一关键输入 stale、断流或出现版本缺口时保留最后画面但撤销新的 `BUY / SELL`，并显示降级原因。
- 进入赛前追踪窗口且完成精确组合的模型覆盖比赛由后端后台跟踪；已有 paper position 无论浏览器是否打开都持续跟踪至退出或结算。Challenger/ITF 不运行模型与 paper observation，市场只在用户查看时按需加载。
- REST 只负责首次 snapshot、WebSocket 重连重建和受限校准，不回到常态固定轮询。后端未运行或中间失联时记录 `tracking_gap`，恢复后重新校准，不补造错过的信号、订单簿或成交。

## T55 已批准实时持久化分流（2026-09-16）

- API-Tennis 与 Polymarket WebSocket ingress 只做轻量 envelope 校验、记录接收时间并进入有界 per-match queue；不得在读取循环中等待模型、SQL 或 SSE 客户端。
- API-Tennis point/比赛事实频率较低且现有 transaction/recovery 已验证，P3 首版保留 canonical reduction 的 PostgreSQL DB-first 顺序，并增加分段 p50/p95/p99 与 backlog 指标；只有实际超门才改造。
- Polymarket 高频 order book 由单写者内存 reducer 按 timestamp/hash/version 更新，Redis 只承载热快照和实时通知；不逐 delta 同步写 PostgreSQL。改变 `$10` 可执行价、动作或模型对照的 observation 及周期采样异步批量落库。
- `order_intent`、sports delay 后的 `fill/no_fill`、`exit` 与 `settlement` 使用 PostgreSQL 同步事务和唯一幂等键；事务提交后才能向 Redis/SSE 确认状态，重启后以 PostgreSQL ledger 恢复。
- 普通 observation 队列丢失或进程离线形成显式 `tracking_gap`，不得事后补造；不可丢的 paper 状态不得进入弱保证队列。
- 当前本地私人测试规模不新增 Kafka 或 Redis Streams；只有实测 observation backlog、跨进程 replay 或多消费者恢复需求达到升级门后才重新评估，且 broker 不能替代 PostgreSQL paper ledger。

## T55 已批准页面层级（2026-09-16）

- 采用 Home → `/markets` → Match Page 三层结构；现有导航中的“市场 BETA”从 Home 锚点升级为独立 `/markets` 路由。
- Home 保持全局比赛发现和查询主职责，只显示少量高价值机会与未结 paper position 摘要；不铺完整市场列表、价格轨迹或详细 ledger。
- `/markets` 负责跨比赛 Market Discovery 与 Paper Tracking，首版仅包含当前机会、即将开始、开放 paper positions、近期已结算结果四类内容。
- Match Page 是单场决策工作台，承载 calibrated probability、实际可执行市场价、edge/confidence、当前动作、概率轨迹、结构化解释和本场 paper lifecycle。
- 所有机会、市场和持仓卡片通过内部 `match_id` 进入 Match Page；`/markets` 不负责单场深度分析，也不是自动下单终端。

## T55 已批准 `/markets` 三视图（2026-09-16）

- `机会` 为默认视图，只展示模型覆盖的大满贯及 ATP/WTA 主巡赛单打中的 `BUY / WAIT`；Live 在前、Upcoming 在后，`NO BET` 不进入机会流。
- `全部市场` 展示所有可用的 Polymarket 网球单场胜者市场，按 ATP/WTA → Challenger → ITF → other 排序，并允许按赛事级别、性别和赛前/赛中筛选。模型覆盖比赛的 `NO BET` 显示原因；Challenger/ITF 只显示市场，不出现“未覆盖”等负向标签。
- `Paper 账本` 先列开放持仓，再列近期退出和结算；页面只提供组合概览，点击后通过内部 `match_id` 进入 Match Page 查看完整 lifecycle。
- 三个视图是同一路由内的页面级切换，不把 current/upcoming/open/settled 拆成四个并列首页区块，也不提供自动下单。

## 上一任务 T54 完成证据（2026-09-13）

- 确定性后端：`543 passed / 51 deselected`；infrastructure `22 passed / 572 deselected`。
- 前端：`pnpm test` 228 passed；`pnpm typecheck` 干净；`pnpm build` 编译成功。
- 全量 Playwright（fake）：`62 passed / 34 skipped / 0 failed`（exit 0）；新增 `home-history-answer.png` 桌面/移动两张基线逐张审阅通过，既有基线零变化（git 仅新增）。
- 确定性 home-history e2e：功能 4 + 视觉 2（双视口），连续复跑稳定。
- 真实 API-Tennis：`api_tennis_live` 2 passed。
- 真实 LLM（确定性 provider）：`llm_live` 19 passed，含 5 项 T54 内容断言（last/recent/season scope、多球员双 data event、与同次 service probe 逐 ID 相等）。
- 真实 API+LLM 同运行后端：`player_directory_e2e_live` 4 passed（probe-vs-Chat 不变量：内部身份、scope、finished 倒序、赛季记录；一次 supplier 同步抖动的诚实 skip 复跑全过）。
- 真实浏览器（api_tennis + 真实 LLM）：`player-directory-live.spec.ts` 20 passed，5 个历史场景内容级断言（section 数/双语标题/scope 徽章/内部链接/空态文案/SSE done/无 error 帧/无控制台错误/无 payload 泄漏）。
- 边界：`git diff --check` 干净；diff 无供应商字段/凭据；产品代码无 P3 术语；工作区仅 5 项受保护未跟踪项。
- 顺带修复 T50 遗留契约错位：Chat `player_resolution` SSE 为嵌套域形状，Home 候选链接曾以 undefined id 渲染（React key 警告 + `/players/undefined`）；现按内部 ID 渲染并有单测与 live 复验。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-15 | `b6539e4` | T55 领取：P3.0 进入 design freeze，仅授权设计讨论与规格，不授权实现 |
| 2026-09-13 | `86ea404` | T54 关闭：P2.6/P2 重新 done，P3 恢复 ready for design（未开始） |
| 2026-09-13 | `8d1233f` | Task 6 真实内容门 + 修复 T50 候选链接契约错位 |
| 2026-09-13 | `4b23f1b` | Task 5 Home 历史分组渲染与两张专用视觉基线 |
| 2026-09-13 | `edb2b89` / `8818304` | Task 4 dataItems 聚合 / Task 3 typed player_history |

## 下一步

继续 T55 的单问题设计讨论；下一项冻结 Home 的高价值机会与开放持仓摘要，随后细化 Match 工作台和 v0 原型状态。全部设计经用户批准后写入 P3 设计规格；规格获批前不得编写实施计划、修改 v0 原型或实现 P3 功能。
