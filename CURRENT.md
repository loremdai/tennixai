# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-17 12:25 CST

**当前任务：** 未领取 — T73: Add Live-Local Configuration and Isolation Guards（P4.1）

**任务状态：** `ready`

**执行者 / ADE：** 待领取

**分支：** `main`

**起始提交：** `32ea89c`（T72 实施计划已提交）

**当前动作：** T72 已关闭：用户批准 [P4.0 本地真实运行设计](./docs/superpowers/specs/2026-09-17-tennixai-p4-local-real-runtime-design.md)，实施计划已提交为 `32ea89c`：[P4.0 本地真实运行实施计划](./docs/superpowers/plans/2026-09-17-tennixai-p4-local-real-runtime-implementation.md)。计划把实现拆为 T73–T80；尚未修改运行代码。下一位执行者必须先领取 T73，再开始实现。

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
| 2026-09-17 | `32ea89c` | T72 关闭：用户批准设计，T73–T80 实施计划已提交；尚未开始运行时代码 |
| 2026-09-17 | `e2173fd` | T72 规格已推送：P4.0 本地真实运行设计；等待用户审阅，未开始实现 |
| 2026-09-17 | `6deac21` | Codex 领取 T72：P4.0 Local Real Runtime 设计冻结；仅规格与总控 |
| 2026-09-17 | `3fde00a` | T71 完成：真实只读 shadow gate（backend live 4 passed + 浏览器 4 passed）与证据表；P3 关闭 |
| 2026-09-17 | `90dedf3` | T70 关闭 + Claude 领取 T71 |

## 下一步

1. 下一位执行者先按 `AGENTS.md` 完整检查仓库，再在本文件领取并推送 T73；领取前不得修改代码或配置。
2. T73 只能执行 [实施计划](./docs/superpowers/plans/2026-09-17-tennixai-p4-local-real-runtime-implementation.md) 的 Task 1；完成后记录实际测试证据、提交、推送，并将 T74 从 `planned` 转为 `ready`。
3. 后续严格一次一个任务推进 T74–T80；任何 P4 工作不得回溯放宽 P3 边界：只读 provider、one-shot FOK、PostgreSQL 权威、独立 cursor、未晋升即 NO BET。
