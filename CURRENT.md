# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-22 18:20 CST

**当前任务：** T85 — Add Read-Only Batch Quote Coverage

**任务状态：** `in_progress`

**执行者 / ADE：** Claude Code（Opus 5）

**分支：** `main`

**起始提交：** `a0d5f5f`

**当前动作：** T84 已实际验证并关闭（提交 `a0d5f5f`）。正在实施 T85：可逆 migration `0006` 与 `market_quote_snapshots` 投影、canonical 报价状态机（七个可见状态）、公开只读 CLOB `POST /books` 批量适配器、幂等 upsert 与 raw batch 14 天保留。详细步骤见 [P4.3 实施计划](./docs/superpowers/plans/2026-09-22-tennixai-p4-market-data-truthfulness-and-coverage-implementation.md)。

## T85 范围与硬边界

- 只读公开 Polymarket CLOB `POST /books`；不新增凭据、钱包、签名或下单路径；不调用 LLM。
- snapshot 车道只负责展示报价：不得触发 PredictionService、DecisionWorker、PaperTradingService，不得创建或扩大 WebSocket 订阅。
- 投影每 market 最多一行，只存 canonical 两侧 levels 与展示统计、`source`、`state`、`as_of`、`expires_at`、`book_hash`；不存 token/condition/event ID、原始 provider JSON、模型概率、decision 或 paper 状态。
- 原始批量响应按 batch 写入既有 `raw_provider_events`，沿用 14 天清理；公共 API、日志、Chat 与页面零 provider identity。
- 幂等与 precedence：同一内容重跑不写；旧值绝不覆盖新值；同一时刻只允许 realtime 车道覆盖 snapshot 车道，绝不反向。

## T84 完成证据（2026-09-22，全部实际运行）

- 实现提交 `a0d5f5f`：`market_match_links.status='active'` 成为唯一 market→match 查询真相，`markets.match_id` 不再被读取。
- `cd backend && uv run pytest tests/test_market_overview_projection.py -q` → `1 passed`（spy 断言 overview/facts/predictions/hot books 各恰一次调用；per-row 调用直接抛错）。
- `cd backend && uv run pytest tests/integration/test_p3_query_service.py -q` → `5 passed`，含两条新证据：active link 生效且 replaced link 不泄漏（旧 `markets.match_id` 仍存值但被忽略）；`markets()` 在行数增加后 SQL 语句数不变（`expanded == baseline`，≤8）。
- `cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not infrastructure" -q` → `1138 passed, 12 skipped, 89 deselected`，0 failed。
- `cd backend && uv run pytest -m infrastructure -q` → `64 passed`。
- ruff：触碰文件 `check` 全部通过；对本人新增/改写文件执行 `format`（`app/markets/publisher.py`、`tests/test_market_overview_projection.py`）；既有 format 债务文件未触碰。
- 实施偏差（已记录）：计划中 T84.1（仓储）与 T84.2（服务）的两次提交合并为一次，因为单独的仓储改动会让 `P3QueryService.markets()` 处于红色中间态。

## 受保护的既有未跟踪文件

不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-22 | 本提交 | T84 关闭（证据见上）并领取 T85：Claude Code（Opus 5）、`main`、起始 `a0d5f5f` |
| 2026-09-22 | `a0d5f5f` | T84 实现：active link 成为唯一 market→match 真相；批量装载消除 Markets 查询 N+1 |
| 2026-09-22 | `ff317f1` | T84–T89 详细实施计划（5349 行）入库并推送 |
| 2026-09-22 | `61c460d` | 用户书面确认规格后 T83 关闭、T84 领取 |
| 2026-09-22 | `89de518` | T83 规格草案与总控记录推送；规格随后获用户书面确认 |

## 下一步

1. 按 T85 → T86 → T87 → T88 → T89 顺序逐项实现、验证、提交并推送；每个任务的领取、节点与完成更新三份总控。
2. T89 完成全链回归、有界真实本地 coverage run（零 LLM）、runbook 与总控收口后，本文件不再有 active 任务。
3. P4.3 完成后单独排期模型晋升证据链；自动下单继续 `deferred`。