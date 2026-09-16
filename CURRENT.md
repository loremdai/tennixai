# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-16 22:05 CST

**当前任务：** T63 — Implement Executable Quotes and the Versioned Decision Engine

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `5031856`

**领取提交：** 本次提交（T62 关闭 + T63 领取记录）

**当前动作：** T62 已以 `5031856` 交付：确定性 DP 计分引擎（含 deuce/抢七闭式尾）、empirical-Bayes 发球收缩与 fail-closed PredictionService（typed abstention、artifact SHA-256/promotion 校验、零 `app.markets` import）。现按 [P3 实施计划 T63](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t63-implement-executable-quotes-and-the-versioned-decision-engine) 以 TDD 实施 `$10` 逐档可执行 quote、versioned policy artifact 装载与 `MARKET_ONLY/NO BET/WAIT/BUY/HOLD/SELL` 决策引擎。

## 当前已验证状态

- T62 验收（全部实际运行）：焦点 `test_scoring_probability + test_live_prediction + test_prediction_service` 39 passed；加 P2 `test_live_reducer/test_momentum_engine` 回归 70 passed；确定性 backend 735 passed/70 deselected；新文件 ruff 干净。引擎数学精确值经手算核对（对称先验 love-all = 0.5；BO3 一盘领先 = 0.75；BO5 = 0.6875）。
- 修复的真实缺陷：`_game` 终止态曾按 server 而非 p1 视角返回（TDD 断言捕获）；`PredictionService` 分支曾把无 score 的 LIVE 误走赛前路径。
- 弃权语义已冻结：`OUT_OF_DOMAIN`（Challenger/ITF/双打）、`MODEL_UNPROMOTED`/`PROMOTION_NOT_GRANTED`/`ARTIFACT_INVALID`（fail-closed）、`FORMAT_UNKNOWN`（绝不猜测赛制）、`DATA_INCOMPLETE`、`MATCH_NOT_PLAYABLE`；无 server 降级为 score-only `DEGRADED`。
- T57–T61 保持关闭；T56 视觉真源保持；P2 保持 `done`；真实下单明确延期。已知诚实缺口：T61 真实历史数据未接入（合成 fixture 证明管线可复现，真实审计留待 T71 本地路径输入）；artifact elo 键与 canonical player_id 的对齐同样留待 T71 真实数据接入时验证。
- 模型未晋升时生产必须 `NO BET`；不得伪造 `BUY`。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-16 | `5031856` | T62 完成：DP 计分引擎、empirical-Bayes 收缩、fail-closed PredictionService；39+70 passed |
| 2026-09-16 | `57190c1` | T61 关闭 + Claude 领取 T62 |
| 2026-09-16 | `9ef4937` | T61 完成：审计 walk-forward benchmark、fail-closed CLI、合成 fixture；诚实 `not_promoted` |
| 2026-09-16 | `6aac68f` | T60 完成：market WS feed/reducer/热状态/worker/replay；P3.2 关闭 |
| 2026-09-16 | `0d6728c` | T59 完成：只读 Polymarket adapter + 精确 mapping + 真实公开 REST smoke |

## 下一步

1. 完成 T63 的 TDD 实施与验收（quote 逐档/费用/深度/滑点测试、policy artifact fail-closed 测试、决策表全 hard gate 测试 + domain 回归），更新三份总控，提交并推送 `origin/main`。
2. T63 边界：entry 用对应 outcome 的 asks、exit 用持仓 outcome 的 bids；displayed midpoint/last trade/best level 不能替代整笔 quote；fee/tick/min-size/delay 一律来自 market metadata 不硬编码；WAIT 的动态最高可接受均价必须用同一 fee/depth-aware 保守净 edge 不等式求解，不得固定折扣；policy 证据不足（hash 不符/test 选阈值/缺 validation+shadow/net-EV 下界非正）必须禁用 BUY/SELL。
3. T63 关闭后按同一流程领取 T64（one-shot FOK paper lifecycle 与 provider-final settlement），顺序执行至 T71。
