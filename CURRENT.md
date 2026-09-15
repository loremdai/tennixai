# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-15 14:04 CST

**当前任务：** T55 — Freeze P3 Market & Decision Support Design and Prototype Brief

**任务状态：** `in_progress`

**执行者 / ADE：** Codex / Codex Desktop

**分支：** `main`

**任务起始提交：** `7409806`

**领取提交：** `b6539e4`

**设计提交：** —

**产品提交：** —（T55 只授权设计，不授权实现）

**关闭提交：** —

**当前动作：** P3 SOTA 研究方向、首版模型覆盖标记和 market-to-match 运行时组合方案已获用户批准。下一步继续逐项冻结 decision/abstention、paper opportunity、实时数据流和页面信息架构；全部设计获批前不写实现代码。

**当前状态：** P2（含 T54）保持已关闭；P3.0 仅进入 design freeze。研究报告位于 `docs/research/2026-09-15-tennis-win-probability-sota.md`；其模型选择方法和 market-to-match 方向已批准，但仍不是完整 P3 规格。具体 champion、校准器和 decision 阈值必须在数据覆盖审计与统一 benchmark 后决定。P4 已确定为 P1–P3 框架完成后的统一打磨阶段；当前没有 P3 provider、schema、prediction、decision、paper ledger、页面或交易能力，自动下单仍属独立延期阶段。

## T55 研究节点（2026-09-15）

- 调研覆盖赛前/赛中胜率、结构化 Markov、动态 rating、Bayesian live update、hybrid ML、概率校准、risk–coverage、市场效率与数据许可。
- 关键结论：公开研究不存在可直接照搬的统一 SOTA；P3 应冻结可复现 benchmark 和模型晋升门，而非凭单篇论文选择算法。
- 市场门修正为可执行价格：Polymarket 页面展示价通常不是实际买入价；paper decision 必须使用 ask/订单簿深度、市场实际费率、滑点和不确定性边际。
- 推荐边界：LLM 只解释结构化输出；当前市场价不进入独立网球模型；证据、数据、映射或流动性不足时输出明确 `NO BET`。
- 尚未批准或实施：候选模型 champion、绝对阈值、训练数据许可方案、P3 数据/服务契约、页面改版和任何交易能力。

## T55 已批准边界与 market-to-match spike（2026-09-15）

- 模型覆盖：只为大满贯和 ATP/WTA 主巡赛单打显示正向 `模型覆盖` 标记，并在这些比赛上提供胜率、edge 与 `BUY / NO BET`；Challenger/ITF 仍展示比赛和 Polymarket 市场，但不显示“未验证”等负向标记，也不提供模型建议。
- 数据关系：Polymarket 市场与 API-Tennis 比赛各自保留 provider ID；不建立需要人工维护的永久绑定，不用 LLM 或模糊置信分做最终连接。
- 组合规则：先把 Polymarket moneyline 的两个完整 outcome 名称解析为内部 Player ID，再与 API-Tennis 的无序 Player ID 对做运行时精确连接；只有唯一且上下文无冲突的结果才能组成 `DecisionContext`。失败时市场照常展示、不显示模型标记，后续同步自动重试。
- 真实只读 spike：2026-09-15 至 09-16 共 125 个有效 Polymarket 网球 moneyline、477 条 API-Tennis 赛程/比赛记录；79 个唯一连接（63.2%）、0 个多候选，成功项开赛时间差中位数 0 分钟、最大 45 分钟。成功项含 WTA Singles 18、男子 Challenger 42、女子 Challenger 19；该窗口无 ATP 主巡赛样本。
- 失败分布：25 个市场至少一名球员未进入当前目录，21 个已解析球员对没有 API 当期记录，样本主要集中在低级别赛事；这不阻塞低级别市场独立展示。ATP 主巡赛及更多大满贯/WTA 样本仍须在实施阶段 shadow 验证，不能用本次窗口宣称全面覆盖。

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

继续 T55 的单问题设计讨论；下一项先冻结“一个合格 paper opportunity”的定义和同场去重规则，再讨论实时流与页面。全部设计经用户批准后写入 P3 设计规格；规格获批前不得编写实施计划、修改 v0 原型或实现 P3 功能。
