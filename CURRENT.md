# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-22 20:35 CST

**当前任务：** T87 — Expose Explicit Market and Opportunity Semantics

**任务状态：** `in_progress`

**执行者 / ADE：** Claude Code（Opus 5）

**分支：** `main`

**起始提交：** `46ea3cc`

**当前动作：** T86 已实际验证并关闭（提交 `9821b79`、`ef07be7`、`f220d57`、`f00ea13`、`46ea3cc`）。正在实施 T87：Markets DTO 显式化（`quote` 对象 + `quote_state`/`quote_source`/`quote_as_of`、`model_availability`、真实 `decision_action`）、机会端点 aggregate availability、前端 typed decoder/view model 同步，删除「null action 当 MARKET_ONLY」的推断。详细步骤见 [P4.3 实施计划](./docs/superpowers/plans/2026-09-22-tennixai-p4-market-data-truthfulness-and-coverage-implementation.md)。

## T87 范围与硬边界

- `MARKET_ONLY` 只能来自真实 `DecisionObservation`；`decision_action` 为 null 时前端不得推断任何决策状态。
- `match_id` 只来自 active link；无 link 的行不得出现内部导航。
- quote state/source/as-of 与决策安全 overlay（`is_stale`/`has_gap`）不得混写。
- 机会行内容不变（仍只有 `BUY`/`WAIT`），Chat 工具继续消费行列表。
- 公共 API/SSE/Chat/日志零 provider identity。

## T86 完成证据（2026-09-22，全部实际运行）

- 实现提交：`9821b79`（四个有界 snapshot 配置贯通 + `MarketOverviewRow.event_start` + `list_external_ids`）、`ef07be7`（`MarketQuoteCoverage` 模型/registry/公开 DTO）、`f220d57`（有界 snapshot 作业与 `mark_limited`）、`f00ea13`（WebSocket 正常关闭与每连接 keepalive）、`46ea3cc`（daemon 接线、实时热 book 镜像、stored realtime 报价按实时窗口过期）。
- `cd backend && uv run pytest tests/test_market_snapshot_job.py -q` → `8 passed`（分批 ≤ token 上限、每批一行 raw、单次私有 token 批量读、live→开赛时间→tier→稳定 ID 轮转、`limited` 保号不丢、429 尊重 `Retry-After` 且下一轮整体跳过、非 429 批失败计数并继续、无 identity/token 的市场被排除、realtime 桶来自一次批量热读、作业构造签名不含 decision/paper/feed/LLM）。
- `cd backend && uv run pytest tests/test_market_live_feed.py tests/test_market_worker.py -q` → `24 passed`。新增证据：`ConnectionClosedOK` → `MarketFeedClosed`（正常关闭分支，帧仍先送达）、两条并发订阅各自保持 PING 且无泄漏 keepalive task、worker 正常关闭后订阅 parked 为 `closed`（零 gap、零连接转移、零 REST 风暴、demand 撤销后释放并可重新订阅）、异常关闭仍写 gap 并 REST 对账（既有契约回归守护）。
- `cd backend && uv run pytest tests/test_runtime_daemon.py -q` → `47 passed`。新增证据：snapshot 作业按 120 秒自身间隔运行且 coverage 随 `persist()` 落库、实时热 book 镜像为 `source=realtime` 的记录、缺失热 book 不写任何行、投影写入失败只降级 `polymarket` 源且 tick 与 decision pump 继续、snapshot 车道零 decision/paper 副作用且 roster 不变。
- `cd backend && uv run pytest tests/integration/test_market_quote_persistence.py -q` → `6 passed`（新增 `list_external_ids` 批量私有映射、`mark_limited` 保留最后可信 levels 与 `as_of` 且为未报价 market 建最小 limited 行）。
- `cd backend && uv run pytest tests/integration/test_runtime_recovery.py -q` → `2 passed`（新增真实 PostgreSQL 证据：一轮真实 snapshot 写入 durable projection + raw batch + 持久化 coverage；ledger 计数与 WebSocket roster 未变；随后 realtime 镜像取得 precedence 且旧 snapshot 无法夺回）。
- `cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not infrastructure" -q` → `1181 passed, 12 skipped, 96 deselected`，0 failed。
- `cd backend && uv run pytest -m infrastructure -q` → `71 passed`。
- ruff：触碰文件 `check` 通过；本人新增/改写文件已 `format`；既有 format 债务文件（`app/config.py`、`app/service.py`、`app/persistence/market_repositories.py` 等）未触碰。
- 实施中发现并修复的真实缺陷（均有先行失败测试）：① 实时车道写进共享投影的记录会被 300 秒快照窗口「担保」，导致 5 分钟前的 WebSocket 报价仍显示「实时盘口」→ 改为按车道使用各自 freshness 窗口（realtime 用 5 秒、snapshot 用配置窗口）；② `PolymarketMarketFeed` 用单个 `_ping_task` 槽位，第二条订阅会覆盖第一条的 keepalive 引用，留下孤儿 ping task 并在关闭时误取消他人的保活 → 改为每连接一个 ping task + 实例级登记集合，`shutdown()` 取消全部在途任务。
- 测试双保真度修正：`FakeProjections.mark_limited` 现镜像真实仓储的落库效果（retag 保留 levels / 建最小 limited 行）；`make_daemon` 透传 snapshot 车道参数。

## 受保护的既有未跟踪文件

不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-22 | 本提交 | T86 关闭（证据见上）并领取 T87：Claude Code（Opus 5）、`main`、起始 `46ea3cc` |
| 2026-09-22 | `46ea3cc` | T86 接线：snapshot 作业、coverage、实时镜像与车道级过期窗口 |
| 2026-09-22 | `f220d57`、`f00ea13` | T86：有界 snapshot 作业；WebSocket 正常关闭与每连接 keepalive |
| 2026-09-22 | `9821b79`、`ef07be7` | T86：配置贯通与批量读助手；聚合 coverage 健康 |
| 2026-09-22 | `f413196`、`df04f9c` | T85 关闭：批量报价、canonical 状态与 durable 投影 |

## 下一步

1. 按 T87 → T88 → T89 顺序逐项实现、验证、提交并推送；每个任务的领取、节点与完成更新三份总控。
2. T89 完成全链回归、有界真实本地 coverage run（零 LLM）、runbook 与总控收口后，本文件不再有 active 任务。
3. P4.3 完成后单独排期模型晋升证据链；自动下单继续 `deferred`。