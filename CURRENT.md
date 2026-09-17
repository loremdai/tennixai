# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-17 17:05 CST

**当前任务：** T77: Compose P2 and P3 Demand Under One Runtime Owner（P4.1）

**任务状态：** `in_progress`

**执行者 / ADE：** Claude Code（Fable 5）

**分支：** `main`

**起始提交：** `8860136`（T76 完成提交；main 与 origin/main 一致）

**当前动作：** T76 已完成并通过独立评审（spec ✅ / Approved）：`LocalRuntimeAssembly` 与 `create_app()` 的 `local_runtime_role=api` 分支交付只读 FastAPI 角色——fail-fast 配置校验、`realtime.worker=None`、lifespan 零上游 worker/零后台任务、P3 feed/worker 构建被门控；`TennisService` catalog 注入仅限列表读取，快照/历史/H2H fallback 不变；`/api/v1/runtime/health` 只含 canonical 聚合或 typed `runtime_not_started`。焦点 8 passed、API/P2/P3 门 35 passed、全量确定性 1017 passed/5 skipped/30 deselected、infrastructure 59 passed。本提交关闭 T76 并领取 T77 为唯一 `in_progress`；随后按实施计划 Task 5 以 TDD 实现 `RuntimeDemand`（viewer lease ∪ P3 durable tracking，去重、零 viewer 时 paper 跟踪仍保活）、`RealtimeWorker` 向后兼容扩展点（可选 `demand_source`/`on_snapshot`/`on_connection`，默认 lease-only 行为不变、回调错误隔离不污染 P2 发布）、`MarketWorker.active_market_ids()` 与 REST baseline 后的 `on_state` 下游通知，并把真实 `match_info`（来自 canonical catalog）接入 `TrackingDemand`（live-local runtime 不再 `match_info=None`）。

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
| 2026-09-17 | （本提交） | T76 关闭 + Claude Code 领取 T77：统一 P2/P3 tracking demand；起始 `8860136` |
| 2026-09-17 | `8860136` | T76 完成：FastAPI 只读角色与 runtime ownership 分离（焦点 8 + 门 35 passed；确定性 1017 passed；infra 59 passed） |
| 2026-09-17 | `e8f6bb0` | T75 关闭 + Claude Code 领取 T76 |
| 2026-09-17 | `134c9f9` | T75 完成：幂等 `init` 数据准备（焦点 21 passed；确定性 1009 passed/5 skipped/30 deselected） |
| 2026-09-17 | `222baf4` | T74 关闭 + Claude Code 领取 T75 |

## 下一步

1. T77 只执行 [实施计划](./docs/superpowers/plans/2026-09-17-tennixai-p4-local-real-runtime-implementation.md) 的 Task 5：先写失败的 composed-demand/worker-hook 测试，再加向后兼容扩展点与真实 `match_info` 接线；跑 P2/P3 worker 回归门；完成后记录实际测试证据、提交、推送，并将 T78 从 `planned` 转为 `ready` 后领取。
2. 后续严格一次一个任务推进 T78–T80；任何 P4 工作不得回溯放宽 P3 边界：只读 provider、one-shot FOK、PostgreSQL 权威、独立 cursor、未晋升即 NO BET。
3. 评审遗留 Minor 处置：T78 扩展 `RuntimeHealth` 时必须同步扩展 `RuntimeHealthDto`（当前 `model_validate` 静默丢 extras）并只写消毒后的稳定 `reason_code`；catalog upsert 单写者假设与 partial-fixture 字段覆盖防护在 T77/T78 处置；其余（skipped 语义、Literal state、builder smoke 测试等）留最终整枝评审复核。
