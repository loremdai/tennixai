# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-16 20:30 CST

**当前任务：** T60 — Build the Market WebSocket Reducer, Hot State, and Replay Feed

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `35b08d9`

**领取提交：** 本次提交（T60 领取记录）

**当前动作：** T59 已以 `0d6728c`（代码）与 `35b08d9`（关闭）交付并推送。现按 [P3 实施计划 T60](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t60-build-the-market-websocket-reducer-hot-state-and-replay-feed) 以 TDD 实施公开 market WS feed、canonical book reducer、Redis 热状态 publisher、有界 worker、确定性 replay 与 infrastructure 恢复测试，外加 opt-in 公开 WS smoke。只订阅公开 market channel；不逐 delta 同步写 SQL。

## 当前已验证状态

- T59 验收（全部实际运行）：契约测试 `tests/test_polymarket_provider.py` + `tests/test_market_match_mapping.py` 31 passed（moneyline 过滤、typed skip、双语别名、两侧独立 book 规范化、动态 tick/fee/delay、rules hash 变更、FINAL/50–50/disputed/pending resolution、429/404/5xx/坏 JSON typed 翻译零泄漏、仅公开 GET 请求审计、45 分钟窗口、AMBIGUOUS/UNRESOLVED/OUT_OF_WINDOW、link 冻结决策表）；确定性 backend 639 passed/68 deselected；infrastructure 38 passed；`create_app` 装配验证（`p3_mode=disabled`→None、`shadow`→PolymarketProvider）；新文件 ruff check/format 干净。
- 真实 opt-in smoke `TENNIX_RUN_POLYMARKET_LIVE=1 uv run pytest -m polymarket_live tests/live/test_polymarket_live.py` 1 passed（2026-09-16）：discovery events=100 / markets=1608 / tennis_moneylines=84；canonical mapped=27（skipped：closed=352、not_moneyline=1172、unresolved_player=57——本地目录 2026-09-13 快照的覆盖缺口，属诚实数据）；真实 book_levels=52、tick=0.01、delay_s=1、fee_rate=0.05、resolution=pending；仅打印聚合计数与内部 ID，零 condition/token 泄漏。
- 官方依据：Gamma `/events`、`/markets?condition_ids`；CLOB `/clob-markets/{condition_id}`（V2 紧凑字段 mts/mos/fd{r,e,to}/t[{t,o}]）、`/book?token_id`、`/fee-rate/{token_id}`（404 时回退 fee schedule）。见 [Polymarket Prices & Orderbook](https://docs.polymarket.com/concepts/prices-orderbook)、[CLOB V2 migration](https://docs.polymarket.com/v2-migration)。
- T57（`e7da341`）/T58（`02516c6`）保持关闭；T56 视觉真源保持；P2 保持 `done`；仓库尚无 market WebSocket、prediction 引擎、decision 引擎或 paper 服务编排；真实下单明确延期。
- 模型未通过晋升门时生产必须诚实 `NO BET`；不得伪造 `BUY`。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-16 | `0d6728c` | T59 完成：只读 Polymarket adapter + 精确 mapping + 真实公开 smoke（mapped=27/84） |
| 2026-09-16 | `0681527` | Claude 领取 T59（起始 `1dc7766`） |
| 2026-09-16 | `1dc7766` | T58 关闭：三份总控记录持久化证据 |
| 2026-09-16 | `02516c6` | T58 完成：migration `0004` 十二表可逆 + 幂等 ledger repositories |
| 2026-09-16 | `e7da341` | T57 完成：P3 canonical domain、provider protocol、安全配置 |

## 下一步

1. 完成 T60 的 TDD 实施与验收（reducer/worker 焦点测试、replay fixture、infrastructure 恢复、公开 WS smoke、确定性全量回归），更新三份总控，提交并推送 `origin/main`。
2. T60 边界：只订阅公开 market channel，绝不订阅 user/authenticated channel；ping 按官方间隔；断线后先 REST reconcile 再接受 delta；高频 book 只更新内存/Redis 热状态，observation 异步批量落库。
3. T60 关闭后 P3.2 完成，按同一流程领取 T61（审计 walk-forward benchmark），顺序执行至 T71。
