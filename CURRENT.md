# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-15 16:00 CST

**当前任务：** T55 — Freeze P3 Market & Decision Support Design and Prototype Brief

**任务状态：** `in_progress`

**执行者 / ADE：** Codex / Codex Desktop

**分支：** `main`

**任务起始提交：** `7409806`

**领取提交：** `b6539e4`

**设计提交：** —

**产品提交：** —（T55 只授权设计，不授权实现）

**关闭提交：** —

**当前动作：** P3 SOTA 研究方向、首版模型覆盖标记、market-to-match 运行时组合、“独立估值而非延迟套利”原则、一次入场/最多一次退出的 paper 生命周期，以及 `SELL` 与 `LOCK PROFIT` 分轨语义均已获用户批准。下一步冻结持仓前的 `BUY / WAIT / NO BET` 语义与目标买入价，再继续讨论实时数据流和页面信息架构。

**当前状态：** P2（含 T54）保持已关闭；P3.0 仅进入 design freeze。研究报告位于 `docs/research/2026-09-15-tennis-win-probability-sota.md`；其模型选择方法和 market-to-match 方向已批准，但仍不是完整 P3 规格。具体 champion、校准器和 decision 阈值必须在数据覆盖审计与统一 benchmark 后决定。P4 已确定为 P1–P3 框架完成后的统一打磨阶段；当前没有 P3 provider、schema、prediction、decision、paper ledger、页面或交易能力，自动下单仍属独立延期阶段。

## T55 研究节点（2026-09-15）

- 调研覆盖赛前/赛中胜率、结构化 Markov、动态 rating、Bayesian live update、hybrid ML、概率校准、risk–coverage、市场效率与数据许可。
- 关键结论：公开研究不存在可直接照搬的统一 SOTA；P3 应冻结可复现 benchmark 和模型晋升门，而非凭单篇论文选择算法。
- 市场门修正为可执行价格：Polymarket 页面展示价通常不是实际买入价；paper decision 必须使用 ask/订单簿深度、市场实际费率、滑点和不确定性边际。
- 推荐边界：LLM 只解释结构化输出；当前市场价不进入独立网球模型；证据、数据、映射或流动性不足时输出明确 `NO BET`。
- 退出研究结论：不存在脱离目标函数、风险偏好、交易成本和 alpha 持续性的通用最优卖点；“市场价追上模型点估计就自动卖”不能直接冻结为唯一规则。风险中性时应比较净可执行卖出所得与模型继续持有价值；锁定同等期望利润属于降低方差的选择，必须单独标识。
- Polymarket 执行事实：卖出须使用实际订单簿 bid/depth，且要计入逐市场费率与 sports order delay；2026-09-15 只读样本显示当期 tennis moneyline 常见 `secondsDelay=1`，不同市场版本的 `feeSchedule.rate` 出现 `0.03` 与 `0.05`，进一步证明不能硬编码或按信号时盘口假装成交。
- 已批准退出语义：`SELL` 是净可执行卖出价值高于稳健持有价值时的期望值动作；`LOCK PROFIT` 是市场回到模型合理区间时的可选风险降低动作，两者不得混用。具体数值阈值和候选规则仍须由 walk-forward/shadow 数据选择。
- 尚未批准或实施：候选模型 champion、绝对阈值、训练数据许可方案、P3 数据/服务契约、页面改版和任何交易能力。

## T55 已批准边界与 market-to-match spike（2026-09-15）

- 模型覆盖：只为大满贯和 ATP/WTA 主巡赛单打显示正向 `模型覆盖` 标记，并在这些比赛上提供胜率、edge 与 `BUY / NO BET`；Challenger/ITF 仍展示比赛和 Polymarket 市场，但不显示“未验证”等负向标记，也不提供模型建议。
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

## T55 已批准退出语义（2026-09-15）

- `HODL_BASELINE` 始终持有至结算，作为原始预测与入场质量的基线。
- `EV_EXIT` 对应产品动作 `SELL`：只有在市场实际 delay 后，按届时订单簿深度、部分/未成交和费用计算出的净卖出价值，高于模型不确定性调整后的继续持有价值时才建议卖出。
- `CONVERGENCE_LOCK` 对应产品动作 `LOCK PROFIT`：当市场回到模型合理区间时允许用户降低方差、锁定利润，但不得宣称该动作提高期望值。
- `FIXED_TAKE_PROFIT` 只作为诊断 benchmark，不进入默认产品建议。
- 三条策略轨道不分别生成多笔组合交易；真实 paper position 最多采用一次退出，同时保存未采用轨道和持有到结算的反事实结果。
- 模型概率必须先通过 proper scoring 与校准门；绝对阈值和具体规则不得凭直觉硬编码，只能依据独立 walk-forward/shadow 证据晋升。

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

继续 T55 的单问题设计讨论；下一项冻结持仓前的 `BUY / WAIT / NO BET` 与目标买入价语义，明确区分“模型观点”和“当前动作”。随后再讨论实时数据流与页面信息架构。全部设计经用户批准后写入 P3 设计规格；规格获批前不得编写实施计划、修改 v0 原型或实现 P3 功能。
