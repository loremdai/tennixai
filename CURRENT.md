# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-17 04:20 CST

**当前任务：** T70 — Prove Dual-Stream Replay, Recovery, Full Regression, and Visual Fidelity

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `64bb505`

**领取提交：** 本次提交（T69 关闭 + T70 领取记录）

**当前动作：** T69 已以 `64bb505` 交付（后端补强 `32ab3bd`/`99c980e`/`e96e1a7`/`1f36773`）：生产 Match Page 以服务端决策快照为单一当前动作来源——全宽 DecisionSummary（12 个 canonical 状态 + 正交 STALE/GAP overlay、intent 出现后 entry 控件消失、零"真实下注"文案）、双边独立可执行 ask 与 $10 算术逐字展示（不强制互补）、ledger 派生永久 Paper lifecycle 时间线（intent-only 场合成 entry_pending/missed 明细不伪造 fill）、evidence/gates 与模型—市场轨迹图（缺失样本留缺口、无订单簿不伪造价格、sr-only 数据表）；`useDecisionStream` 生产接线 gap/malformed 只降级 decision 流并只重取 decision。冻结 `?preview=p3` 原型保持视觉真源（52 张基线原样通过）；生产移除旧侧栏市场占位（P3 规格"旧侧栏市场占位不再保留"）后，4 张 P1 match 基线经逐张 diff 审阅（仅卡片区域与其布局位移，无其他像素变化）后重生成。现按 [P3 实施计划 T70](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t70-prove-dual-stream-replay-recovery-full-regression-and-visual-fidelity) 执行：`p3_dual_stream.jsonl` replay、PostgreSQL/Redis restart recovery、本地延迟门、全量回归与 26 场景 × desktop/mobile 逐张审阅。

## 当前已验证状态

- T69 验收（全部实际运行）：前端单测 392 passed（32 文件；新增 decision-summary 12 + chart 7 + paper-lifecycle 6 + match-page workbench 块）；`pnpm typecheck`/`pnpm build` 干净；完整 Playwright 110 passed/34 skipped：新增 e2e/p3-match.spec.ts 26 项（六状态家族直接刷新、buy 研究摘要且零交易 CTA、entry_pending/settled 账本时间线、decision gap 只降级 decision 流、键盘焦点、零 console/page 错误、390×844 零横向溢出 + Ask≥36px），52 张 P3 基线与 prototype/home/p2 基线原样通过，4 张 P1 match 基线逐张审阅后重生成。
- T69 后端验收：workbench 快照扩展（versions/gates/outcome_levels/position 明细+events、intent-only 合成时间线、target_player_id）对真实 PostgreSQL integration 3 passed；确定性 backend 854 passed/77 deselected；infrastructure 保持通过。
- T67/T68 不变量保持：双独立 stream cursor、gap 只重取自身、malformed 显式事件、重连携带自身 Last-Event-ID；Home Pulse 服务端探测与 `/markets` 降级矩阵不变。
- T57–T68 保持关闭；T56 视觉真源保持（52 张基线零改动）；P2 保持 `done`；真实下单明确延期。诚实缺口不变：T61 真实历史数据未接入、artifact 键对齐与 `match_info` 真实来源留待 T70/T71。
- 模型未晋升时生产必须 `NO BET`；不得伪造 `BUY`。前端只渲染服务端提供的 action/reason/lifecycle，绝不在 React 中计算 probability/edge/成交/结算。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-17 | `64bb505` | T69 完成：生产 Match Decision Workbench（全宽摘要/双边对照/轨迹/依据/lifecycle、gap 独立性、键盘与移动端门）；4 张 P1 match 基线逐张审阅后重生成；Playwright 110 passed |
| 2026-09-17 | `1f36773`/`e96e1a7`/`99c980e`/`32ab3bd` | T69 后端补强：workbench 快照 versions/gates/outcome_levels/position 明细、intent-only 时间线、target_player_id；integration 对真实 PostgreSQL 证明 |
| 2026-09-17 | `5ac7b1e` | T68 关闭 + Claude 领取 T69 |
| 2026-09-17 | `39756f7` | T68 完成：生产 Home Pulse + `/markets` 三视图与降级矩阵 |
| 2026-09-17 | `808b87e` | T67 完成：typed P3 transport、runtime 解码、七个薄代理、双独立 stream hooks |

## 下一步

1. T70 实施与验收（按计划顺序）：`p3_dual_stream.jsonl` 确定性 replay（sports 与 market 双 cursor、gap 注入后只恢复自身、不补造事件/成交）；PostgreSQL 与 Redis restart 后 paper 权威恢复（Redis/浏览器丢失不能创建或抹除持仓）；本地延迟门复测（book→decision p95<500ms、sports→decision p95<1s）；全量回归（backend 确定性+infrastructure、前端单测/typecheck/build、完整 Playwright）；26 场景 × desktop/mobile 视觉基线逐张审阅（不得批量接受 diff，P1/P2 基线保持不变，除非规格要求的生产变化经逐张证明）。
2. T70 关闭后领取 T71：真实只读 shadow gate（重跑 audit/benchmark 于真实本地数据、REST/WS smoke、shadow backend、真实浏览器、证据表），诚实 skip 带日期与 discovery counts，随后关闭 P3 并写回三份总控。
