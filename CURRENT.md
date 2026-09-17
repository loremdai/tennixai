# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-17 14:50 CST

**当前任务：** T74: Persist a Canonical Catalog and Runtime State（P4.1）

**任务状态：** `in_progress`

**执行者 / ADE：** Claude Code（Fable 5）

**分支：** `main`

**起始提交：** `4c0c955`（T73 完成提交；main 与 origin/main 一致）

**当前动作：** T73 已完成并通过独立评审（spec ✅ / quality Approved）：`app/runtime` 配置守卫（`require_live_local` 只接受 loopback 上的 `tennix_live_local`、Redis DB 11、`api_tennis`+`paper`+真实凭据；错误只含稳定 reason code；`child_environment` 五个子进程覆盖键、零 `NEXT_PUBLIC_*`、不改父环境），焦点 64 passed、全量确定性 backend 962 passed/5 skipped/30 deselected。本提交关闭 T73 并领取 T74 为唯一 `in_progress`；随后按实施计划 Task 2 以 TDD 实现 migration `0005`（仅 `runtime_state`，downgrade 只删新表）、`MatchCatalogRepository` 与 `RuntimeStateRepository`（仅 `local_runtime_init`/`local_runtime_health` 两键、不存 provider ID/raw JSON），并跑 PostgreSQL integration 与持久化回归。

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
| 2026-09-17 | （本提交） | T73 关闭 + Claude Code 领取 T74：canonical catalog 与 runtime state 持久化；起始 `4c0c955` |
| 2026-09-17 | `4c0c955` | T73 完成：本地真实运行配置与隔离守卫（焦点 64 passed；确定性 backend 962 passed/5 skipped/30 deselected） |
| 2026-09-17 | `38df793` | Claude Code 领取 T73：P4.1 本地真实运行配置与隔离守卫；起始 `eb793e7` |
| 2026-09-17 | `32ea89c` | T72 关闭：用户批准设计，T73–T80 实施计划已提交；尚未开始运行时代码 |
| 2026-09-17 | `e2173fd` | T72 规格已推送：P4.0 本地真实运行设计；等待用户审阅，未开始实现 |

## 下一步

1. T74 只执行 [实施计划](./docs/superpowers/plans/2026-09-17-tennixai-p4-local-real-runtime-implementation.md) 的 Task 2：先写失败的 repository 契约测试，再加 migration `0005` 与两个 repository，跑 PostgreSQL integration 与既有持久化回归；完成后记录实际测试证据、提交、推送，并将 T75 从 `planned` 转为 `ready` 后领取。
2. 后续严格一次一个任务推进 T75–T80；任何 P4 工作不得回溯放宽 P3 边界：只读 provider、one-shot FOK、PostgreSQL 权威、独立 cursor、未晋升即 NO BET。
