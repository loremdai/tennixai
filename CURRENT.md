# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-17 05:15 CST

**当前任务：** T71 — Run the Real Read-Only Shadow Gate and Close P3

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `01e6ba0`

**领取提交：** 本次提交（T70 关闭 + T71 领取记录）

**当前动作：** T70 已以 `01e6ba0` 交付：`p3_dual_stream.jsonl`（含 50-50/无入场第二 fixture）对真实 PostgreSQL+Redis 证明 sports+books+decisions+one-shot ledger+settlement 全链（upcoming→live→finished、双边订单簿、correction、disconnect/reconcile 显式 `tracking_gap`、BUY→FILLED、HOLD→SELL→EXIT_MISSED、provider-final settlement 与三条评估轨；双跑 digest 相同、restart 仅从 PostgreSQL 恢复 cursor 与 demand、intent/fill 零重复、公共输出零 provider ID/密钥、队列零溢出）；延迟门 integration 变体在真实 observation 写入 + Redis hot book 下 book→decision p95<500ms、sports→decision p95<1s 实测通过。门暴露并修复真实缺陷：exit intent 在 BOOK_UNVERIFIABLE/EXPIRED 短路下位置永久 exit_pending 导致结算非法转移，现统一记 EXIT_MISSED（`app/paper/service.py` + 回归测试）。现按 [P3 实施计划 T71](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t71-run-the-real-read-only-shadow-gate-and-close-p3) 执行真实只读 shadow gate：审计/benchmark 复跑、public REST/WS smoke、shadow backend、真实浏览器只读流、证据表，然后关闭 P3。

## 当前已验证状态

- T70 验收（全部实际运行）：integration 3 passed（end-to-end replay：双跑 digest 相同、restart 恢复、tracking gap、one-shot、三轨结算、公共面扫描）+ 1 passed（latency gate with durable persistence）；backend 855 确定性 passed/81 deselected、infrastructure 50 passed；新文件 ruff check+format 干净；前端 392 单测（32 文件）、typecheck/build 干净、完整 Playwright 110 passed/34 skipped（单次干净运行）。
- T70 视觉门：52 张 P3 基线（Home 4 + Markets 8 + Match 14 场景 × desktop/mobile）自冻结提交 `f29a789` 起字节不变（`git diff f29a789 HEAD -- frontend/e2e/__screenshots__` 仅列出 4 张 P1 match 图）；26 场景 × 双视口全部 actual==expected（suite 绿即逐像素相等）。本会话唯一像素变化 = 4 张 P1 match 基线（`64bb505`），因生产 Match Page 按 P3 规格移除旧侧栏市场占位；四张 expected/actual/diff 逐张审阅：差异仅卡片区域与其引起的移动端布局位移，无其他像素变化，审阅后重生成。检查项：无横向溢出、层级与状态标签、$10 算术、stale 动作抑制、图表缺口、mobile DOM 顺序、≥36px 目标。
- T57–T69 保持关闭；T56 视觉真源保持；P2 保持 `done`；真实下单明确延期。诚实缺口：T61 真实历史数据未接入（模型保持 `not_promoted`，生产 `NO BET`）；artifact 键对齐与 `match_info` 真实来源留待 P4。
- 模型未晋升时生产必须 `NO BET`；不得伪造 `BUY`。前端只渲染服务端提供的 action/reason/lifecycle。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-17 | `01e6ba0` | T70 完成：dual-stream replay/recovery/latency integration 门（真实 PostgreSQL+Redis）、exit-missed 缺陷修复与回归、全量回归与视觉门证据 |
| 2026-09-17 | `2f6fb89` | T69 关闭 + Claude 领取 T70 |
| 2026-09-17 | `64bb505` | T69 完成：生产 Match Decision Workbench；4 张 P1 match 基线逐张审阅后重生成 |
| 2026-09-17 | `1f36773`/`e96e1a7`/`99c980e`/`32ab3bd` | T69 后端补强：workbench 快照扩展与 intent-only 时间线 |
| 2026-09-17 | `5ac7b1e` | T68 关闭 + Claude 领取 T69 |

## 下一步

1. T71 Step 1：在真实本地源（若存在）复跑数据审计与冻结 benchmark；无真实历史数据则记录诚实 `not_promoted` 与原因，运行时保持 `NO BET`。
2. Step 2：`TENNIX_RUN_API_TENNIS_LIVE=1 TENNIX_RUN_POLYMARKET_LIVE=1 uv run pytest -m "api_tennis_live or polymarket_live" tests/live -v`；无活跃网球市场 = 带日期的诚实 skip + discovery counts。
3. Step 3：新建 `backend/tests/live/test_p3_shadow_live.py`（`end_to_end_live`），shadow backend 观察已映射市场、freshness 对照、hard gates 与持久化、禁私有端点/钱包凭据；未晋升模型只允许 MARKET_ONLY/NO BET。
4. Step 4：新建 `frontend/e2e/p3-live.spec.ts`，真实浏览器只读流（Home Pulse、/markets 三 tab、Match 双 SSE、refresh/reconnect、双语链接、terminal/empty/degraded 文案、零 console 错误、DOM/URL 零外部/provider ID）。
5. Step 5：任何 live 修复后重跑 T70 确定性门；Step 6 以证据表关闭 P3（提交、命令/计数、promotion 结论、带日期覆盖/skip、延迟百分位、审阅截图、P4 延期项），更新三份总控并推送 origin/main。
