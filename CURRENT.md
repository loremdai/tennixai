# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-16 23:05 CST

**当前任务：** T65 — Orchestrate Dual Live Inputs, Durable Tracking, and Pipeline Metrics

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `d5ae409`

**领取提交：** 本次提交（T64 关闭 + T65 领取记录）

**当前动作：** T64 已以 `d5ae409` 交付：纯状态机（全部非法转移以稳定 reason code 拒绝）、provider-final settlement 解释器（签名不接受网球结果）、事务化 paper service（唯一 entry/exit、实际 delay 后 FOK requote、typed no-fill、commit 先于 publish）与并发/崩溃恢复 integration 证明。现按 [P3 实施计划 T65](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t65-orchestrate-dual-live-inputs-durable-tracking-and-pipeline-metrics) 以 TDD 实施 decision worker 双流编排、durable tracking demand 与低基数管线指标（p50/p95/p99）。

## 当前已验证状态

- T64 验收（全部实际运行）：焦点 31 passed（状态机 15 + settlement 12 + service 8，扣除参数化后合计）；infrastructure 41 passed（含双 worker 并发唯一性与 commit-before-publish 崩溃恢复恰一次）；确定性 backend 802 passed/72 deselected；新文件 ruff 干净。
- paper 不变量已在三层证明：domain（T57 transition 表）、repository（T58 幂等/回滚/重启）、service/integration（T64 并发/崩溃/三轨结算）。`BOOK_UNVERIFIABLE` 只产生 no-fill；settlement 只服从 provider FINAL resolution；50–50 显式 $0.50/share。
- T57–T63 保持关闭；T56 视觉真源保持；P2 保持 `done`；真实下单明确延期。诚实缺口不变：T61 真实历史数据未接入、artifact 键对齐留待 T71。
- 模型未晋升时生产必须 `NO BET`；不得伪造 `BUY`。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-16 | `d5ae409` | T64 完成：one-shot FOK paper lifecycle、provider-final settlement、并发/崩溃恢复证明 |
| 2026-09-16 | `2b69c89` | T63 关闭 + Claude 领取 T64 |
| 2026-09-16 | `6012fcc` | T63 完成：可执行 quote、versioned policy、决策引擎全 hard-gate 表 |
| 2026-09-16 | `5031856` | T62 完成：DP 计分引擎、empirical-Bayes 收缩、fail-closed PredictionService |
| 2026-09-16 | `9ef4937` | T61 完成：审计 walk-forward benchmark、fail-closed CLI；诚实 `not_promoted` |

## 下一步

1. 完成 T65 的 TDD 实施与验收（ordering/backpressure/demand/freshness 焦点测试、确定性重启 integration、10k book + 1k sports 变更本地延迟门、P2 realtime 回归），更新三份总控，提交并推送 `origin/main`。
2. T65 编排契约：canonical sports 变化 → prediction → decision；有效 book 变化 → 复用最新 prediction 只重算 quote/decision；rule change → 动作抑制；resolution → settlement；ledger 转移 commit 先于 SSE；tracking demand 来自赛前覆盖窗口与未结持仓，绝不来自 ViewerLeaseStore；指标低基数、零 player/match/token ID 标签。
3. T65 关闭后 P3.3 完成，按同一流程领取 T66（只读 P3 REST/独立 SSE/Chat tools），顺序执行至 T71。
