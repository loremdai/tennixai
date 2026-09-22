# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-22 19:05 CST

**当前任务：** T86 — Schedule Snapshot Coverage and Harden Market Stream Recovery

**任务状态：** `in_progress`

**执行者 / ADE：** Claude Code（Opus 5）

**分支：** `main`

**起始提交：** `f413196`

**当前动作：** T85 已实际验证并关闭（提交 `8c311d8`、`27d0cc9`、`5c1f94b`、`f413196`）。正在实施 T86：四个有界 snapshot 配置贯通、有界 120 秒 snapshot 作业与公平轮转、聚合 coverage 健康、WebSocket 正常关闭/每连接 keepalive 加固、实时热 book 镜像进共享投影。详细步骤见 [P4.3 实施计划](./docs/superpowers/plans/2026-09-22-tennixai-p4-market-data-truthfulness-and-coverage-implementation.md)。

## T86 范围与硬边界

- snapshot 车道只写展示报价：不得触发 PredictionService、DecisionWorker、PaperTradingService，不得创建 WebSocket 订阅、不得调用 LLM。
- 不扩大 decision WebSocket roster（严格映射 + 主巡单打 + tracking demand 三者同时满足才可订阅）。
- 429 必须尊重 `Retry-After` 并以有界退避跳过后续轮次，绝不忙等重试；单批失败不删除旧 projection。
- WebSocket 正常关闭（`ConnectionClosedOK`）是显式生命周期分支：停止该订阅、不记 gap、不把整个 market source 误标为故障；异常关闭/keepalive/overflow 仍按既有 `GAP → REST reconcile → resume` 处理。
- coverage 健康只输出聚合数字与稳定 reason code，零 token/URL/provider ID。

## T85 完成证据（2026-09-22，全部实际运行）

- 实现提交：`8c311d8`（reversible migration `0006` + `MarketQuoteSnapshotRow`）、`27d0cc9`（`app/markets/quotes.py` 七个状态、批量投影、共享 level 格式与 precedence）、`5c1f94b`（公开只读 CLOB `POST /books` 批量适配器）、`f413196`（投影仓库、raw batch 保留与 integration 证据）。
- `uv run alembic upgrade head → downgrade 0005 → upgrade head` 三次 exit 0；`alembic current` = `0006 (head)`（仅本地回环库）。
- `cd backend && uv run pytest tests/test_market_quote_snapshot.py -q` → `10 passed`（表形状、七个状态、单边/空盘/坏 payload、precedence 真值表、幂等重跑、实时镜像记录）。
- `cd backend && uv run pytest tests/test_polymarket_batch_books.py -q` → `6 passed`（POST `/books` 数组 body、去重保序、按 `asset_id` 取值不假设顺序、零 Authorization、单 token 隔离、missing 不伪造、429 `Retry-After`、非数组 payload、空输入不发请求）。
- `cd backend && uv run pytest tests/integration/test_market_quote_persistence.py -q` → `4 passed`（连续两次运行均通过）。含：幂等 upsert、source precedence（同刻 realtime 可覆盖 snapshot、反向不可）、每 market 恰好一行、投影零 provider identity、raw batch 每批一行且 14 天清理（用唯一标记精确计数）、canonical 投影经 PostgreSQL 往返。
- `cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not infrastructure" -q` → `1154 passed, 12 skipped, 93 deselected`，0 failed。
- `cd backend && uv run pytest -m infrastructure -q` → `68 passed`。
- ruff：新增/改写文件 `check` 通过并已 `format`；既有 format 债务文件未触碰。
- 实施偏差（已记录）：raw batch 测试首版用全局计数断言，在共享开发库上被此前单跑留下的同时刻行污染（实测残留 2 行）；已改为按每次运行的唯一 marker 精确计数，隔离共享库噪声。另：`QuoteState` 的实时/快照命名由 lane 映射（fresh hot book → `realtime`，batch → `snapshot`，单边 → `partial`），避免把 WebSocket 来源标成「快照报价」。

## 受保护的既有未跟踪文件

不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-22 | 本提交 | T85 关闭（证据见上）并领取 T86：Claude Code（Opus 5）、`main`、起始 `f413196` |
| 2026-09-22 | `f413196` | T85 实现（末项）：投影仓库、raw batch 保留与 integration 证据 |
| 2026-09-22 | `8c311d8`–`5c1f94b` | T85 实现：migration `0006`、canonical 报价模块、CLOB 批量适配器 |
| 2026-09-22 | `a0d5f5f`、`27f1c01` | T84 关闭：active link 成为唯一 market→match 真相，批量装载消除 N+1 |
| 2026-09-22 | `ff317f1` | T84–T89 详细实施计划（5349 行）入库并推送 |

## 下一步

1. 按 T86 → T87 → T88 → T89 顺序逐项实现、验证、提交并推送；每个任务的领取、节点与完成更新三份总控。
2. T89 完成全链回归、有界真实本地 coverage run（零 LLM）、runbook 与总控收口后，本文件不再有 active 任务。
3. P4.3 完成后单独排期模型晋升证据链；自动下单继续 `deferred`。