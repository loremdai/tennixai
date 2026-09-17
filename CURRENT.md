# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-17 11:44 CST

**当前任务：** T72 — Freeze the Local Real Runtime Design（P4.0）

**任务状态：** `in_progress`

**执行者 / ADE：** Codex / Codex Desktop

**分支：** `main`

**起始提交：** `c537f4f`（P3 关闭与 P4 计划状态对齐）

**当前动作：** 已获用户确认，正在把 P4.0「完整本地真实运行」写成可审阅设计：单一 `init/up/status/down` 入口、隔离 `tennix_live_local` 数据库、后台独占真实 API-Tennis/Polymarket WebSocket、赛程/排名低频同步、显式 stale/gap 安全门、显式真实核验与永远 paper-only。此任务只写规格和总控，不开始实现；规格经用户审阅批准后才创建实施计划。

## P3 关闭证据摘要（详见 ROADMAP T57–T71 行）

- 设计/原型冻结：T55 `d7cc25e`、T56 `f29a789`（26 场景 × desktop/mobile 52 张基线，逐张审阅）。
- 数据与实时：T57–T60（只读 Polymarket、精确 mapping、replay；真实 REST/WS 验证）。
- 预测与决策：T61–T65（fail-closed benchmark `not_promoted`、quote/policy/engine、one-shot paper、双流编排与延迟门）。
- 产品面：T66–T69（只读 REST/SSE/Chat、typed transport、Home Pulse/`/markets`、Match workbench）。
- 完成门：T70 `01e6ba0`（dual-stream replay/recovery/latency/全回归/视觉门）、T71 `3fde00a`（真实只读 shadow + 证据表）。
- 回归基线：backend 855 确定性 + 50 infrastructure；frontend 392 单测、typecheck/build 干净、Playwright 110 passed/38 skipped（live 门按 env 跳过）。
- 诚实缺口转入 P4：真实历史数据与模型晋升证据、artifact 键对齐、`match_info` 真实来源、退出阈值/仓位优化、性能打磨；自动下单永久 `deferred` 直至单独批准。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-17 | 待提交 | Codex 领取 T72：P4.0 Local Real Runtime 设计冻结；仅规格与总控 |
| 2026-09-17 | `3fde00a` | T71 完成：真实只读 shadow gate（backend live 4 passed + 浏览器 4 passed）与证据表；P3 关闭 |
| 2026-09-17 | `90dedf3` | T70 关闭 + Claude 领取 T71 |
| 2026-09-17 | `01e6ba0` | T70 完成：dual-stream replay/recovery/latency integration 门、exit-missed 缺陷修复、全量回归与视觉门 |

## 下一步

1. 完成 T72 设计规格、自检并提交；请用户审阅后才可编写实施计划。
2. 不得借 T72 修改运行代码、`.env`、数据库或视觉原型；实现任务将在规格批准后另行领取。
3. 任何 P4 工作不得回溯放宽 P3 边界：只读 provider、one-shot FOK、PostgreSQL 权威、独立 cursor、未晋升即 NO BET。
