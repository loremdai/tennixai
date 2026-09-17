# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-18 03:07 CST

**当前任务：** T79: Add a Safe Repository-Root Launcher（P4.1）

**任务状态：** `in_progress`

**执行者 / ADE：** Claude Code（Fable 5）

**分支：** `main`

**起始提交：** `4fdc4f6`（T78 最终修复提交；main 领先 origin 三个待推送提交，随本领取记录一并推送）

**当前动作：** T78 已完成并经 opus 评审两轮（首轮 Needs fixes：run 循环可被 persist 失败杀死、resolution 目标无优先级/轮转；`6cf844e` 修复后复审 Approved；`4fdc4f6` 补 daemon_tick 恢复回 OK）：`RuntimeHealthRegistry`（安静比分不判 stale、gap 仅对账成功后解除、degraded 保留数据、消毒 reason code、聚合计数入 `RuntimeHealthDto`）、`DecisionWorker` freshness overlay 复用 T63 硬门、`LocalRuntimeDaemon`（精确 60/600/86400/120 调度、严格映射发现零 LLM、paper 只以可验证 hot book 执行否则 BOOK_UNVERIFIABLE/NO_FILL、幂等 book 消费、单顺序 demand 调用者+源隔离、优雅停机 flush）、catalog COALESCE 防 partial 覆盖；恢复 integration 证明仅凭 PostgreSQL 重建、恢复前显式 gap、零重复 intent/fill。daemon+health 52 + workers 24 + 回归 68 passed、全量确定性 1104 passed/5 skipped/30 deselected、infrastructure 62 passed（控制者复跑）。本提交关闭 T78 并领取 T79 为唯一 `in_progress`；随后按实施计划 Task 7 以 TDD 实现安全 launcher：`app/runtime/child.py`（token 化子进程包装、独立进程组）、`app/runtime/launcher.py`（Compose/端口/进程 ownership：未 init 拒绝 up、外部端口只报不杀、down 只停可证明拥有的容器/进程、绝不 `docker compose down`/删 volume）、`app/runtime/cli.py`（六命令与清晰非零退出码）、`scripts/tennix-live` 可执行包装；全部测试使用 fake command runner/process inspector，不触真实 Docker、不绑端口、不读 `.env` 值、不杀进程。

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
| 2026-09-18 | （本提交） | T78 关闭 + Claude Code 领取 T79：安全的根目录 launcher；起始 `4fdc4f6` |
| 2026-09-18 | `4fdc4f6` | T78 修复 2：daemon_tick 恢复后回 OK（先红后绿；确定性 1104 passed） |
| 2026-09-18 | `6cf844e` | T78 修复 1：run 循环 persist 失败不再致命；resolution 目标优先级+确定性轮转+skipped 计数（opus 复审 Approved） |
| 2026-09-17 | `bab5380` | T78 主体完成：health registry、freshness overlay、LocalRuntimeDaemon、恢复 integration（确定性 1095→1103；infra 62 passed） |
| 2026-09-17 | `2494df4` | T77 关闭 + Claude Code 领取 T78 |

## 下一步

1. T79 只执行 [实施计划](./docs/superpowers/plans/2026-09-17-tennixai-p4-local-real-runtime-implementation.md) 的 Task 7：先写失败的 launcher 安全测试（fake runner/inspector），再实现 `child.py`/`launcher.py`/`cli.py`/`scripts/tennix-live` 与 compose 兼容性；证明测试零真实 Docker/零端口绑定/零 `.env` 值读取/零进程杀；完成后记录实际测试证据、提交、推送，并将 T80 从 `planned` 转为 `ready` 后领取。
2. T80 是最后任务：显式真实核验（`local_runtime_live` marker + `TENNIX_RUN_LOCAL_RUNTIME_VERIFY=1`）、浏览器验收（`TENNIX_E2E_LOCAL_RUNTIME=1`）、人类 runbook、全量回归与手工 `init → up → status → 浏览器刷新 → down → up → status` 门；外部安静窗口必须诚实 PASS/FAIL/SKIP。
3. 任何 P4 工作不得回溯放宽 P3 边界：只读 provider、one-shot FOK、PostgreSQL 权威、独立 cursor、未晋升即 NO BET。T74–T78 遗留 Minor（RuntimeDemand 与 TrackingDemandSource 重复、daemon 依赖 Any 类型、source-global gap、无界缓存、recently-closed 类实际不可达等）已记录在案，留最终整枝评审分诊。
