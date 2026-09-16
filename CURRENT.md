# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-16 21:35 CST

**当前任务：** T62 — Implement Live Tennis Probability, Calibration Loading, and Safe Degradation

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `9ef4937`

**领取提交：** 本次提交（T61 关闭 + T62 领取记录）

**当前动作：** T61 已以 `9ef4937` 交付：审计 walk-forward benchmark 管线、三候选（surface Elo/dynamic rating/HGBM）、三校准器、fail-closed CLI 与 200 行合成 fixture。fixture benchmark 诚实结论：champion=surface_elo、test log_loss 0.681 CI95 [0.614,0.752]、`not_promoted`（保守下界不过门）。现按 [P3 实施计划 T62](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t62-implement-live-tennis-probability-calibration-loading-and-safe-degradation) 以 TDD 实施确定性计分概率引擎、empirical-Bayes 收缩与带 typed abstention 的 PredictionService。

## 当前已验证状态

- T61 验收（全部实际运行）：焦点 5 个测试文件 32 passed；CLI 三命令 exit 0，fail-closed exit 2/3/4 实测；确定性 backend 696 passed/70 deselected；`verify-artifact` 捕获字节篡改；prediction 模块零 `app.markets` import（grep 证明）；新文件 ruff 干净；sklearn 1.9.1 全 NaN 列崩溃已由中性 rank_diff 修复（常量列实测 OK）。
- 晋升纪律：fixture 产物 `not_promoted` 是正确结果而非失败；生产在无晋升证据时必须 `MODEL_UNPROMOTED + NO BET`。model card 晋升规则已预声明（test CI95 上界 < ln2），不得事后改门槛。
- T57–T60 保持关闭（`e7da341`/`02516c6`/`0d6728c`/`6aac68f`）；T56 视觉真源保持；P2 保持 `done`；真实下单明确延期。
- 真实历史数据集尚未接入：仓库只有合成 fixture；真实数据来源/许可审计将在 T71 以本地 `TENNIX_MODEL_DATA_PATH` 输入执行（当前为带日期的诚实缺口，非伪造通过）。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-16 | `9ef4937` | T61 完成：审计 walk-forward benchmark、三候选三校准、fail-closed CLI、合成 fixture；诚实 `not_promoted` |
| 2026-09-16 | `0708ab2` | Claude 领取 T61（起始 `0dbb0dc`） |
| 2026-09-16 | `6aac68f` | T60 完成：market WS feed/reducer/热状态/worker/replay + 重启恢复；P3.2 关闭 |
| 2026-09-16 | `0d6728c` | T59 完成：只读 Polymarket adapter + 精确 mapping + 真实公开 REST smoke |
| 2026-09-16 | `02516c6` | T58 完成：migration `0004` 十二表可逆 + 幂等 ledger repositories |

## 下一步

1. 完成 T62 的 TDD 实施与验收（scoring/shrinkage/service 焦点测试 + P2 reducer/momentum 回归），更新三份总控，提交并推送 `origin/main`。
2. T62 边界：`ScoringProbabilityEngine` 确定性 DP 计分（love-all 对称、发球优势、盘点/局点/赛点、BO3/BO5、标准与决胜盘抢七、终态、未知赛制弃权不猜测）；发球分能力从赛前 prior 出发用 beta-binomial/empirical-Bayes 吸收当场证据且只计预测时点前的发球分；PBP 修正从受影响 sequence 确定性重算；主巡单打覆盖、Challenger/ITF `MODEL_UNAVAILABLE`、artifact/hash 不匹配 fail-closed、零 `app.markets` import。
3. T62 关闭后按同一流程领取 T63（executable quote 与 versioned decision engine），顺序执行至 T71。
