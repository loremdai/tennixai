# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-18 05:40 CST

**当前任务：** T80: Add Explicit Real Verification, Browser Acceptance, and the Human Runbook（P4.1）

**任务状态：** `in_progress`

**执行者 / ADE：** Claude Code（Fable 5）

**分支：** `main`

**起始提交：** `da6dcdd`（T79 最终提交；main 领先 origin 三个待推送提交，随本领取记录一并推送）

**当前动作：** T79 已完成并经 opus 评审两轮 + 两次加固（首轮 Important——二次 `up` 可孤儿化既有 runtime 子进程、产生第二上游所有者——已由 `81ace2e` 修复并复审 Approved；`fb49cdc` 闭合 SIGTERM 竞态/死亡子进程快速失败/status 健康年龄；`da6dcdd` 以 `waitpid WNOHANG` 收割僵尸使存活探测真实）：安全 launcher 全生命周期（状态仅在系统临时目录 0700/0600、token+命令双重验证才 signal、只停本次新建容器、绝不 `compose down`/删 volume/按端口杀进程、up 绝不自动 init/绝不调用 LLM）、runtime 进程入口 `daemon_main` + `build_local_runtime_daemon` 真实图装配（评审逐 kwarg 核对）、真实 Alembic 适配器与幂等 `tennix_live_local` 建库、`scripts/tennix-live` 可执行包装。launcher 58 + daemon_main 3 passed、全量确定性 1163 passed/5 skipped/30 deselected。本提交关闭 T79 并领取 T80 为唯一 `in_progress`。T80 前置已核对：根 `.env` 已有 `TENNIX_PROVIDER_MODE=api_tennis` 与真实 API-Tennis/LLM 凭据；缺 `TENNIX_P3_MODE=paper` 与 `TENNIX_LOCAL_RUNTIME_*` 块，将按 runbook 流程补入根 `.env`（Git 忽略、仅本地，不打印值）。随后按实施计划 Task 8 以 TDD 实现 `verify.py`（受限只读真实 smoke：至多各一次 ranking/fixture/discovery/book 调用、仅存在合格 live 比赛/活跃 book 时才试 WebSocket、45s 有界等待、`--with-llm` 是唯一 LLM 路径、安静窗口诚实 SKIP 绝不冒充 PASS）、`local_runtime_live` marker、opt-in 浏览器验收 `frontend/e2e/local-real-runtime.spec.ts`（`TENNIX_E2E_LOCAL_RUNTIME=1`）、人类 runbook，并执行全量回归与手工 `init → up → status → 浏览器刷新 → down → up → status` 真实门，如实记录 PASS/FAIL/SKIP 与重启后 ID/数据/ledger 保留证据。

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
| 2026-09-18 | （本提交） | T79 关闭 + Claude Code 领取 T80：显式真实核验、浏览器验收与 runbook；起始 `da6dcdd` |
| 2026-09-18 | `da6dcdd` | T79 修复 3：`waitpid WNOHANG` 收割僵尸，存活探测/快速失败真实生效（launcher 58 passed；确定性 1163 passed） |
| 2026-09-18 | `fb49cdc` | T79 加固：SIGTERM 竞态闭合、runtime 死亡快速失败、frontend 存活窗、status 健康年龄（opus 复审 Approved） |
| 2026-09-18 | `81ace2e` | T79 修复 1：`up` 拒绝在既有存活 owned/unowned 子进程时重复 spawn（防第二上游所有者）；init 失败持久化清 marker；状态文件 0600；SIGKILL 前 ownership 复核（opus 复审 Approved） |
| 2026-09-17 | `18efdc3` | T79 主体完成：安全 launcher、child 包装、CLI、runtime 进程入口与真实图装配、Alembic 适配器、幂等建库（gate 90 passed） |

## 下一步

1. T80 只执行 [实施计划](./docs/superpowers/plans/2026-09-17-tennixai-p4-local-real-runtime-implementation.md) 的 Task 8：先写失败的 verifier 结果测试（诚实 SKIP 语义、零 LLM 无 flag），再实现 `verify.py`/marker/浏览器验收/runbook；补全根 `.env` 的 `TENNIX_P3_MODE=paper` 与 `TENNIX_LOCAL_RUNTIME_*` 块；跑确定性验证 + 前端质量门 + 两个 opt-in 真实门；执行手工 `init → up → status → 浏览器刷新 → down → up → status` 并如实记录每一步结果、精确测试计数、真实源 PASS/FAIL/SKIP、重启后 ID/数据/ledger 保留的人工核对。
2. T80 完成后逐条核验 P4.1 / Local Real Runtime Completion Gate 与计划 Completion Gate for T73–T80，对齐 PROJECT/ROADMAP/CURRENT/runbook/Git HEAD 与 origin/main，最终整枝评审后关闭 P4.1。
3. 任何 P4 工作不得回溯放宽 P3 边界：只读 provider、one-shot FOK、PostgreSQL 权威、独立 cursor、未晋升即 NO BET；外部安静窗口必须诚实 SKIP，不得写成通过。T74–T79 遗留 Minor 已记录，留最终整枝评审分诊。
