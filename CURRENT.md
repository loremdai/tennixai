# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-18 15:56 CST

**当前任务：** T81 — Stabilize the Parallel Playwright Visual Gate（`ready`，等待领取）

**任务状态：** `ready` — 计划已冻结；尚无执行者，不能与其他主任务并行领取

**执行者 / ADE：** 待领取（上一执行者：Claude Code（Fable 5））

**分支：** `main`

**起始提交：** `2270049`（T80 最终实现 `002da61`；T81 计划提交见本次交接）

**当前动作：** 执行者先按 `AGENTS.md` 领取 T81 并推送领取记录，再严格执行 [T81 计划](./docs/superpowers/plans/2026-09-18-tennixai-t81-playwright-visual-gate-stabilization.md)。已验证基线：当前 `2270049` 的完整 Playwright 连续两次均为 `109 passed / 44 skipped / 1 failed`；唯一失败为 mobile `prototype.visual` 的 `home-answer`（265 像素）。同一测试以 `--workers=1 --repeat-each=10` 为 10/10 通过，且 P4.1 关闭后 Header/visual spec/config 没有产品代码变更。T81 只能把快照用原生 `@visual` tag 分流到第二条串行 CLI lane；不得重录 PNG、改 UI、调阈值、加 mask/skip/retry 或运行真实配额门。P4.1 的真实 runtime 闭环仍为历史已关闭事实；本机栈保持 `down`，外部容器与 `tennix_live_local` 数据保留。

## P4.1 关闭证据摘要（详见 ROADMAP T73–T80 行与 Completion Gate 核验摘要）

- 配置与隔离：T73 `4c0c955`（`tennix_live_local`/Redis DB 11/loopback 守卫、稳定 reason code、子进程 env 注入）；T74 `ccfdb66`（migration 0005 可逆、canonical catalog/runtime state repositories）。
- 数据准备：T75 `134c9f9`（幂等 init 固定顺序、marker 最后写、二次 init 零翻译调用）；真实 init 2026-09-18 exit 0（3944 球员/292 比赛/中文覆盖有名成员 100%）。
- 进程边界：T76 `8860136`（FastAPI 只读角色零上游）；T77 `9758288`（demand 合并、单订阅证明）；T78 `bab5380`+修复（daemon 唯一所有者、精确调度、freshness/gap 硬门、恢复 integration）。
- 生命周期：T79 `18efdc3`+3 修复+2 实机修复（token/ownership 安全、fail-fast、僵尸收割、PYTHONPATH、pnpm 前置检查）。
- 真实核验：T80 `1ba5e5c` 等（verify 7/7 真实 passed、浏览器验收 6/6、手工全流程两轮 up/down 诚实通过、重启持久性核对）；最终整枝评审 fable+opus 双轮 Approved。
- 回归基线：backend 确定性 1199/5/32 + infrastructure 62；frontend vitest 395 + typecheck/build；完整 Playwright 110 passed/44 skipped/0 failed。
- 追踪项转入 P4 后续：per-match freshness overlay（任何模型晋升前必须落实）、RuntimeDemand 死代码清理、真实历史数据与模型晋升证据、退出阈值/仓位优化；自动下单永久 `deferred`。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-18 | （本提交） | T81 计划与总控交接：后验定位为跨文件 worker 并发下的移动端视觉门不稳定；冻结 `@visual` + 功能/串行视觉两 lane 方案，PNG/UI/阈值均不可改 |
| 2026-09-18 | （本提交） | P4.1 关闭：T80 `done`（真实 init/verify 7/7/浏览器 6/6/手工全流程/重启持久性）+ Completion Gate 九条核验摘要入 ROADMAP；PROJECT/CURRENT 同步 |
| 2026-09-18 | `002da61` | 实机修复 2：`LOCAL_PNPM_MISSING` 前置快速失败（launcher 61 passed；确定性 1199/5/32） |
| 2026-09-18 | `402c527` | 实机修复 1：子进程 wrapper PYTHONPATH 注入，任意 cwd 可导入（真实 up 门发现） |
| 2026-09-18 | `92524cb` | 装配接线回归钉死（变异红证）；最终评审修复波收口 |

## 下一步

1. 下一个执行者先领取并推送 T81，再完成 [T81 计划](./docs/superpowers/plans/2026-09-18-tennixai-t81-playwright-visual-gate-stabilization.md)。关闭要求：视觉 PNG 零 diff，`pnpm test:e2e` 连续两次 `110 passed/44 skipped/0 failed`；不运行 live/LLM gate。
2. T81 完成后，P4 后续候选（待用户排期与批准，均未领取）：真实历史数据与模型晋升证据链、退出阈值/仓位优化（需 paper 证据）、per-match freshness overlay（模型晋升前置条件）、性能打磨、RuntimeDemand 死代码清理等延期 Minor。日常本地使用仍是 `./scripts/tennix-live up`（不调用 LLM）→ `status`/`logs` → `down`；详见 `docs/runbooks/local-real-runtime.md`。
3. 边界不变：自动下单永久 `deferred` 直至单独批准；任何后续工作不得回溯放宽 P3 边界（只读 provider、one-shot FOK、PostgreSQL 权威、独立 cursor、未晋升即 NO BET）；外部安静窗口必须诚实 SKIP。
