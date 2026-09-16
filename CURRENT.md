# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-17 02:45 CST

**当前任务：** T69 — Connect the Match Decision Workbench and Ledger-Driven State Sequence

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `39756f7`

**领取提交：** 本次提交（T68 关闭 + T69 领取记录）

**当前动作：** T68 已以 `39756f7` 交付（后端补强 `603262a`/`c6ef131`）：生产 Home Market Pulse（≤3 行、紧急持仓预留 1 行 + live BUY → upcoming BUY → 最强 WAIT、整行内部导航、无轨迹/账本细节、`p3_disabled` 时渲染 null 并保留占位卡）与生产 `/markets` 三视图（机会/全部/Paper，canonical 枚举筛选 + URL 同步、整行导航、降级矩阵全套：loading 骨架、诚实空态、typed 列表错误 + 重试、刷新失败保留最后可信行、行级 stale/gap overlay、market-only 无负面标签、book 缺失 em-dash、closed 徽章、p3_disabled 诚实面板）。P3 可用性由服务端探测决定（`?p3=1` 为 e2e/dev 强制位），P3 关闭时生产 Home 零 P3 浏览器请求、DOM 与 P1/P2 基线字节一致。冻结 `?preview=p3` 原型保持视觉真源。现按 [P3 实施计划 T69](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t69-connect-the-match-decision-workbench-and-ledger-driven-state-sequence) 以 TDD 实施 Match Decision Workbench（全宽 DecisionSummary、双边对照、轨迹/依据/lifecycle、desktop/mobile 固定顺序、移除旧 MarketCard）与 `useDecisionStream` 生产接线。

## 当前已验证状态

- T68 验收（全部实际运行）：前端单测 351 passed（29 文件；新增 p3-view-models 11 + workspace 11 + live pulse 7 + home 生产 2 + decoders 扩展 7）；`pnpm typecheck`/`pnpm build` 干净；完整 Playwright 84 passed/34 skipped（live-gated）：52 张 P3 基线 + P1/P2 + prototype 视觉原样通过、home-history 零 console 错误契约恢复、新增 p3-markets 16 项生产流（直达/tab/筛选/导航/刷新/键盘/390×844 零横向溢出/44px 目标/disabled 面板）。
- T68 后端补强验收：enriched DTO（player_ids/names、per-outcome top levels、spread/depth、model_probability、average_entry_price、entry_pending ledger 行、pulse phase/tournament/edge/stale）对真实 PostgreSQL integration 3 passed；确定性 backend 854 passed/77 deselected；infrastructure 46 passed；pulse 选择契约（SELL > lock-profit > stale/gap > exit_pending > open > entry_pending，再按 decision 新近度）由 integration 证明。
- T67 不变量保持：双独立 stream cursor、gap 只重取自身、malformed 显式事件、重连携带自身 Last-Event-ID。
- T57–T67 保持关闭；T56 视觉真源保持（52 张基线全部原样通过，不得批量接受 diff）；P2 保持 `done`；真实下单明确延期。诚实缺口不变：T61 真实历史数据未接入、artifact 键对齐与 `match_info` 真实来源留待 T70/T71。
- 模型未晋升时生产必须 `NO BET`；不得伪造 `BUY`。前端只渲染服务端提供的 action/reason/lifecycle，绝不在 React 中计算 probability/edge/成交/结算。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-17 | `39756f7` | T68 完成：生产 Home Pulse + `/markets` 三视图与降级矩阵；52 张 P3 基线与 P1/P2 视觉原样通过；Playwright 84 passed |
| 2026-09-17 | `c6ef131`/`603262a` | T68 后端补强：enriched P3 read models（名称/档位/spread/depth/均价/entry_pending/pulse 选择契约），integration 对真实 PostgreSQL 证明 |
| 2026-09-17 | `d7f0380` | T67 关闭 + Claude 领取 T68 |
| 2026-09-17 | `808b87e` | T67 完成：typed P3 transport、runtime 解码、七个薄代理、双独立 stream hooks；前端 313 passed |
| 2026-09-17 | `3ef0cd3` | T66 追加：paper publish 装配修复（marker→`paper_delta`）与 paper-mode 装配 smoke |

## 下一步

1. 完成 T69 的 TDD 实施与验收：`components/match/{decision-summary,probability-market-chart,decision-evidence,paper-lifecycle}.tsx` 生产接线 + `match-page.tsx`/`match-main.tsx`/`match-sidebar.tsx` 修改；12 个决策状态 + STALE/GAP 正交 overlay 全状态测试（entry 控制在 intent 后消失、单一当前动作来源、零"真实下注"文案）；算术与图表测试（双边独立可执行 ask、不强制 100% 互补、$10 均价/费/edge/P&L 与后端一致、缺失样本留缺口不插值、图表带文字摘要与可访问系列名）；顺序/去重测试（mobile DOM 顺序直接断言、desktop 全宽接缝、单一 DecisionSummary、移除旧 MarketCard、移除重复 AI insight/prompt 卡、保留 score/Stats/PBP/Assistant）；`useDecisionStream` 生产接线（只渲染服务端 action/reasons）；mobile Ask 只滚动聚焦 Assistant 非交易 CTA。
2. T69 验收命令：`pnpm test -- components/match/decision-summary.test.tsx components/match/probability-market-chart.test.tsx components/match/paper-lifecycle.test.tsx components/match-page.test.tsx`；Playwright `e2e/p3-match.spec.ts`（每个 terminal/pending 家族直接刷新、sports 与 decision 流独立 gap、键盘焦点、响应式溢出、零 console/SSE 错误）；`pnpm typecheck` + `pnpm build` + 全量前端 + 视觉基线（14 张 match 基线原样通过）。
3. T69 关闭后按同一流程领取 T70（replay/recovery/全量回归/26 场景视觉逐张审阅），随后 T71 关闭 P3。
