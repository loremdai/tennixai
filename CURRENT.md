# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-16 23:40 CST

**当前任务：** T66 — Expose Read-Only P3 REST, Independent SSE, and Chat Tools

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `8cc3c26`

**领取提交：** 本次提交（T65 关闭 + T66 领取记录）

**当前动作：** T65 已以 `8cc3c26` 交付：DecisionWorker 双流编排（sports→prediction→decision、book→复用 prediction、commit 先于 publish、有界队列 coalescing、cursor 恢复）、TrackingDemand（覆盖窗口+持仓，零 viewer 依赖）、P3Metrics（低基数六段 histogram + 计数器）与本地延迟门（10k book + 1k sports 变更，book→decision p95 < 500ms、sports→decision p95 < 1s、两轮输出字节一致）。P3.3 关闭。现按 [P3 实施计划 T66](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t66-expose-read-only-p3-rest-independent-sse-and-chat-tools) 以 TDD 实施七个只读业务端点、markets/decision 双独立 SSE 与两个只读 Chat 工具。

## 当前已验证状态

- T65 验收（全部实际运行）：焦点 27 passed + 重启恢复 integration 1 passed；P2 realtime 回归 19 passed（match stream 契约不变）；确定性 backend 822 passed/73 deselected；infrastructure 42 passed；paper-mode 装配 smoke 通过；新文件 ruff 干净。
- 编排不变量已冻结：book 更新永不触发模型调用；无 prediction 时 book 更新不产生决策；rule change 抑制动作且 paper 零调用；decision/ledger commit 均先于 publish；队列 overflow 计数且 coalesce 到最新；decision version cursor 仅从 PostgreSQL 恢复。
- T57–T64 保持关闭；T56 视觉真源保持；P2 保持 `done`；真实下单明确延期。诚实缺口不变：T61 真实历史数据未接入、artifact 键对齐与 `match_info` 真实来源（T65 装配暂用 positions+links 保守跟踪）留待 T70/T71 集成验证。
- 模型未晋升时生产必须 `NO BET`；不得伪造 `BUY`。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-16 | `8cc3c26` | T65 完成：双流决策编排、durable tracking demand、P3 指标与本地延迟门；P3.3 关闭 |
| 2026-09-16 | `b0a3f42` | T64 关闭 + Claude 领取 T65 |
| 2026-09-16 | `d5ae409` | T64 完成：one-shot FOK paper lifecycle、provider-final settlement、并发/崩溃恢复 |
| 2026-09-16 | `6012fcc` | T63 完成：可执行 quote、versioned policy、决策引擎全 hard-gate 表 |
| 2026-09-16 | `5031856` | T62 完成：DP 计分引擎、empirical-Bayes 收缩、fail-closed PredictionService |

## 下一步

1. 完成 T66 的 TDD 实施与验收（REST 契约、双独立 SSE 契约、Chat 工具、P2 `/matches/{id}/stream` 字节级回归），更新三份总控，提交并推送 `origin/main`。
2. T66 边界：公共 DTO/URL/错误零 provider ID、零 wallet 字段；`markets/stream` 发布 `market_delta/decision_delta/paper_delta/resolution_delta/heartbeat`；`decision/stream` 用自己的 version cursor，gap 只重取自身；两个 Chat 工具只返回 compact canonical fact packet，LLM 不得创建 intent/改 policy/覆盖 structured action。
3. T66 关闭后按同一流程领取 T67（typed frontend transport），顺序执行至 T71。
