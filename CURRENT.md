# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-16 21:10 CST

**当前任务：** T61 — Add the Audited Walk-Forward Pre-Match Benchmark Pipeline

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `0dbb0dc`

**领取提交：** 本次提交（T61 领取记录）

**当前动作：** T60 已以 `6aac68f`（代码）与 `0dbb0dc`（关闭）交付并推送，P3.2 关闭。现按 [P3 实施计划 T61](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t61-add-the-audited-walk-forward-pre-match-benchmark-pipeline) 以 TDD 实施数据 source/audit、Elo/dynamic rating/HGBM 候选、chronological walk-forward、校准选择与 versioned model card CLI。CLI 在数据路径/许可/audit 门缺失时 fail closed；仓库只提交脱敏最小 fixture。

## 当前已验证状态

- T60 验收（全部实际运行）：焦点 `tests/test_market_reducer.py + test_market_live_feed.py + test_market_worker.py` 25 passed；`uv run pytest -m infrastructure` 39 passed（含新 `test_market_recovery.py` 重启恢复：仅凭 PostgreSQL 重载 durable demand、REST 重建 book、离线区间记 `tracking_gap`、零补造信号/成交）；确定性 backend 664 passed/70 deselected；新文件 ruff check/format 干净。
- Reducer 契约已冻结：单写者、full book 替换、price_change 精确档位增/改/size0 删、timestamp/hash 回退拒绝、无基线 delta 要求 REST snapshot、tick 变更仅元数据、reconnect 一律 `baseline_from_rest`。worker 契约：REST-first、有界队列且接收回调零 I/O、overflow/disconnect → REST reconcile + tracking_gap、Redis 热丢失 REST 恢复、observation 批量落库、14 天 raw cleanup、capacity_limited 显式。
- 真实公开 WS smoke（2026-09-16）：网球 4 tokens 45 秒零消息；活跃市场对照 token 20 秒内收到 1 事件，证明公共 market channel 与订阅帧正确 → 网球侧为诚实 skip（市场安静，非伪造通过）。该对照证据可复用于 T71。
- T57–T59 保持关闭（`e7da341`/`02516c6`/`0d6728c`）；T56 视觉真源保持；P2 保持 `done`；仓库尚无 prediction 引擎、decision 引擎、paper 服务编排或 P3 REST/SSE；真实下单明确延期。
- 模型未通过晋升门时生产必须诚实 `NO BET`；不得伪造 `BUY`。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-16 | `6aac68f` | T60 完成：market WS feed/reducer/热状态/worker/replay + 重启恢复 integration；P3.2 关闭 |
| 2026-09-16 | `2b98ea2` | Claude 领取 T60（起始 `35b08d9`） |
| 2026-09-16 | `0d6728c` | T59 完成：只读 Polymarket adapter + 精确 mapping + 真实公开 REST smoke |
| 2026-09-16 | `02516c6` | T58 完成：migration `0004` 十二表可逆 + 幂等 ledger repositories |
| 2026-09-16 | `e7da341` | T57 完成：P3 canonical domain、provider protocol、安全配置 |

## 下一步

1. 完成 T61 的 TDD 实施与验收（fixture/泄漏测试、确定性候选测试、walk-forward/校准测试、CLI 三条命令与 fail-closed 门、fixture benchmark 报告审阅），更新三份总控，提交并推送 `origin/main`。
2. T61 边界：真实历史数据集若不可得，按事实记录带日期的诚实缺口（fixture 证明管线可复现，真实数据审计留给 T71 的本地路径输入），不得伪造许可或覆盖审计。
3. T61 关闭后按同一流程领取 T62（live probability/校准装载/安全降级），顺序执行至 T71。
