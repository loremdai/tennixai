# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-17 16:24 CST

**当前任务：** T76: Split FastAPI Read Role From Runtime Ownership（P4.1）

**任务状态：** `in_progress`

**执行者 / ADE：** Claude Code（Fable 5）

**分支：** `main`

**起始提交：** `134c9f9`（T75 完成提交；main 与 origin/main 一致）

**当前动作：** T75 已完成并通过独立评审（spec ✅ / Approved）：`CatalogSynchronizer`（live+fixtures 各恰一次、去重 live 优先、失败零删除）、`sync_player_aliases`（仅新见 ID、零 LLM 零全目录扫描、幂等）与 `RuntimeBootstrapper.initialize()`（固定顺序、marker 最后写、失败不擦除既有数据、二次 init 零翻译调用、record 只含聚合计数）；焦点 21 passed、全量确定性 1009 passed/5 skipped/30 deselected。本提交关闭 T75 并领取 T76 为唯一 `in_progress`；随后按实施计划 Task 4 以 TDD 实现 `local_runtime_role=api` 的 `LocalRuntimeAssembly`（FastAPI 只读角色：挂 canonical catalog/P3 查询依赖、`realtime.worker=None`、lifespan 零上游 worker）、`TennisService` 注入 catalog 优先读取（无 catalog 时保持既有 provider 路径逐字节兼容）、内部 ID-only 的 `/runtime/health` 端点（无健康记录时 typed `runtime_not_started`，不改 P1 `/health` 契约），并跑 API/P2/P3 兼容回归。

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
| 2026-09-17 | （本提交） | T75 关闭 + Claude Code 领取 T76：FastAPI 只读角色与 runtime ownership 分离；起始 `134c9f9` |
| 2026-09-17 | `134c9f9` | T75 完成：幂等 `init` 数据准备（焦点 21 passed；确定性 1009 passed/5 skipped/30 deselected） |
| 2026-09-17 | `222baf4` | T74 关闭 + Claude Code 领取 T75 |
| 2026-09-17 | `ccfdb66` | T74 完成：migration `0005` + canonical catalog/runtime state repositories（infra 59 passed；确定性 992 passed） |
| 2026-09-17 | `10ae083` | T73 关闭 + Claude Code 领取 T74 |

## 下一步

1. T76 只执行 [实施计划](./docs/superpowers/plans/2026-09-17-tennixai-p4-local-real-runtime-implementation.md) 的 Task 4：先写失败的 ownership/read-path 测试，再实现 local-role assembly、catalog-first service 读取与 `/runtime/health`；跑 API/P2/P3 兼容回归；完成后记录实际测试证据、提交、推送，并将 T77 从 `planned` 转为 `ready` 后领取。
2. 后续严格一次一个任务推进 T77–T80；任何 P4 工作不得回溯放宽 P3 边界：只读 provider、one-shot FOK、PostgreSQL 权威、独立 cursor、未晋升即 NO BET。
3. T74/T75 评审遗留 Minor（catalog upsert 单写者假设、partial fixture 字段覆盖防护、`reason_code` 消毒约定、`sync_player_aliases` skipped 语义、协议结构契合在装配时确认）由 T77/T78 处置并在最终整枝评审复核。
