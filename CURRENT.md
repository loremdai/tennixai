# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-16 22:30 CST

**当前任务：** T64 — Implement the One-Shot FOK Paper Lifecycle and Provider-Final Settlement

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `6012fcc`

**领取提交：** 本次提交（T63 关闭 + T64 领取记录）

**当前动作：** T63 已以 `6012fcc` 交付：`$10` 逐档可执行 quote（动态 fee 曲线、两侧独立 book、stale/深度/min-size 不可执行）、fail-closed versioned policy artifact 与全 hard-gate 决策引擎（MARKET_ONLY/NO BET/WAIT/BUY/HOLD/SELL + LOCK PROFIT 独立选项；WAIT 最高价用同一 fee-aware 不等式求解）。现按 [P3 实施计划 T64](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t64-implement-the-one-shot-fok-paper-lifecycle-and-provider-final-settlement) 以 TDD 实施纯状态机、settlement 解释器与事务化 paper service。

## 当前已验证状态

- T63 验收（全部实际运行）：焦点 `test_executable_quotes + test_decision_policy + test_decision_engine` 36 passed、P3 domain 回归 52 passed、确定性 backend 771 passed/70 deselected、新文件 ruff 干净。数值全部手算核对（多档均价 0.523810、动态 fee 0.086818、fee-aware 最高价 0.5816）。
- 决策语义已冻结：hard gate 顺序 mapping → rules → model availability → policy → overlay → 分支；WAIT 需真实低估方向（≥ 半个 BUY 阈值），否则 NO_NET_EDGE；stale/gap 保留 HOLD 撤销新动作；LOCK PROFIT 仅诊断标注（entry 成本 1.25 倍线），不改主 ledger。
- T57–T62 保持关闭；T56 视觉真源保持；P2 保持 `done`；真实下单明确延期。诚实缺口不变：T61 真实历史数据未接入；artifact elo 键与 canonical player_id 对齐留待 T71。
- 模型未晋升时生产必须 `NO BET`；不得伪造 `BUY`。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-16 | `6012fcc` | T63 完成：可执行 quote、versioned policy、决策引擎全 hard-gate 表；36+52 passed |
| 2026-09-16 | `b0ecac6` | T62 关闭 + Claude 领取 T63 |
| 2026-09-16 | `5031856` | T62 完成：DP 计分引擎、empirical-Bayes 收缩、fail-closed PredictionService |
| 2026-09-16 | `9ef4937` | T61 完成：审计 walk-forward benchmark、fail-closed CLI；诚实 `not_promoted` |
| 2026-09-16 | `6aac68f` | T60 完成：market WS feed/reducer/热状态/worker/replay；P3.2 关闭 |

## 下一步

1. 完成 T64 的 TDD 实施与验收（完整 transition 表、fake-clock FOK 执行、settlement 语义、并发与重启恢复 integration），更新三份总控，提交并推送 `origin/main`。
2. T64 边界：首个合格 BUY 与首个 EV SELL 是每场唯一 entry/exit；FOK 全成或不成、零 partial/retry/追价/加仓/换边/重新入场；`BOOK_UNVERIFIABLE` 只能记 no-fill 不得伪造成交；settlement 只服从 provider final resolution（含显式 50–50 = $0.50/share、disputed/pending 不本地猜测、retirement/walkover 按市场规则）；HODL/convergence-lock 从同一 entry 分叉为反事实不产生额外仓位；PostgreSQL commit 先于任何对外可见转移。
3. T64 关闭后按同一流程领取 T65（双流后台协调与管线指标），顺序执行至 T71。
