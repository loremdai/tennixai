# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-18 13:20 CST

**当前任务：** 无 — P4.1 Local Real Runtime Implementation 已关闭（T73–T80 全部 `done`，Completion Gate 九条逐条实际核验）

**任务状态：** —（P4 后续优化项待用户排期，未领取）

**执行者 / ADE：** 待领取（上一执行者：Claude Code（Fable 5））

**分支：** `main`

**起始提交：** —（T80 最终提交 `002da61`；关闭提交见下）

**当前动作：** P4.1 已交付并关闭。T80 阶段 2 真实门全部诚实完成（2026-09-18）：用户更换 LLM key 后真实 `init` exit 0（revision=0005、players=3944、matches=292、中文覆盖 4182/4320=有名成员全覆盖、marker 写入）；真实门暴露并修复两个 launcher 实机缺陷（`402c527` 子进程 wrapper PYTHONPATH、`002da61` `LOCAL_PNPM_MISSING` 前置快速失败——本机 pnpm 仅存在于 fnm v22.22.0，launcher 现给出清晰前置错误而非 spawn 即死）；`verify --with-llm` **7/7 全部真实 passed**；`up`→`status`（全 ok、`paper_only`/`not_promoted`）→浏览器验收 Playwright **6/6**→手工刷新（零 console 错误、PID 不变、api.log 零上游痕迹）→`down`（优雅、数据/容器保留）→`up`→`status` 全 ok；重启持久性核对（内部 ID 一致、ledger 0→0 零重复、markets/links 活性增长）。最终回归：确定性 1199/5/32、infrastructure 62、vitest 395+typecheck+build、完整 Playwright 110/44/0。栈已 `down`，端口清空，外部容器保留，`tennix_live_local` 数据完整。日常使用：`./scripts/tennix-live up`（绝不消耗 LLM）；详见 `docs/runbooks/local-real-runtime.md`。追踪项：per-match freshness overlay 必须在任何模型晋升前落实；延期 Minor 清单见 ROADMAP T80 行与评审记录。

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
| 2026-09-18 | （本提交） | P4.1 关闭：T80 `done`（真实 init/verify 7/7/浏览器 6/6/手工全流程/重启持久性）+ Completion Gate 九条核验摘要入 ROADMAP；PROJECT/CURRENT 同步 |
| 2026-09-18 | `002da61` | 实机修复 2：`LOCAL_PNPM_MISSING` 前置快速失败（launcher 61 passed；确定性 1199/5/32） |
| 2026-09-18 | `402c527` | 实机修复 1：子进程 wrapper PYTHONPATH 注入，任意 cwd 可导入（真实 up 门发现） |
| 2026-09-18 | `92524cb` | 装配接线回归钉死（变异红证）；最终评审修复波收口 |
| 2026-09-18 | `c61947b` | 最终评审 Important 修复：共享 120s TTL 决策元数据/规则缓存 + per-market pump 隔离 + 装配接线缺陷修复 |

## 下一步

1. P4.1 已关闭，无 in_progress 任务。日常使用：`./scripts/tennix-live up`（不调用 LLM）→ `status`/`logs` → `down`；一次性维护用 `init`；显式真实核验用 `verify [--with-llm]`。详见 `docs/runbooks/local-real-runtime.md`。
2. P4 后续候选（待用户排期与批准，均未领取）：真实历史数据与模型晋升证据链、退出阈值/仓位优化（需 paper 证据）、per-match freshness overlay（模型晋升前置条件）、性能打磨、RuntimeDemand 死代码清理等延期 Minor。
3. 边界不变：自动下单永久 `deferred` 直至单独批准；任何后续工作不得回溯放宽 P3 边界（只读 provider、one-shot FOK、PostgreSQL 权威、独立 cursor、未晋升即 NO BET）；外部安静窗口必须诚实 SKIP。
