# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-17 17:52 CST

**当前任务：** T78: Run Bounded Discovery, Freshness, and Paper Maintenance（P4.1）

**任务状态：** `in_progress`

**执行者 / ADE：** Claude Code（Fable 5）

**分支：** `main`

**起始提交：** `9758288`（T77 完成提交；main 与 origin/main 一致）

**当前动作：** T77 已完成并通过 opus 评审（spec ✅ / Approved）：`RuntimeDemand`（viewer lease ∪ P3 durable tracking 按 match 去重、零 viewer 保活）、`RealtimeWorker` 三个 None-默认零漂移 hook（`on_snapshot` 严格提交+发布后触发且异常隔离、`on_connection` 仅稳定值）、`MarketWorker.active_market_ids()` 与 REST baseline 后 `on_state`（与 `publish_book` 1:1）、`catalog_match_info` 工厂；同场双源仅一条上游订阅经 feed 记录证明。焦点 21 + 回归门 55 passed、全量确定性 1038 passed/5 skipped/30 deselected、infrastructure 59 passed。本提交关闭 T77 并领取 T78 为唯一 `in_progress`；随后按实施计划 Task 6 以 TDD 实现 `RuntimeHealthRegistry`（fresh/degraded/stale/gap，连接/心跳健康的体育流不因比分安静判 stale）、`DecisionWorker` 可选 freshness overlay（stale/gap 撤销新 BUY/SELL）、`LocalRuntimeDaemon`（唯一上游 WebSocket 所有者：精确间隔 live 60s/upcoming 600s/ranking 86400s/discovery 120s 的有界调度、严格映射市场发现、paper intent 到期以真实热 book 执行或 `BOOK_UNVERIFIABLE`/`NO_FILL`、resolution 只经 `DecisionWorker.on_resolution`、优雅停机 flush 有界缓冲）与重启恢复 integration 证明（durable demand/catalog/ledger 重建订阅、REST 恢复 cursor 与热 book、恢复前显式 gap、零重复 intent/fill）。同时处置遗留 Minor：catalog upsert 单写者假设注释、partial fixture 字段防 None 覆盖、`reason_code` 只写消毒稳定码、T77 评审的 demand 源隔离/幂等消费/健康面统一。

## P3 关闭证据摘要（详见 ROADMAP T57–T71 行）

- 设计/原型冻结：T55 `d7cc25e`、T56 `f29a789`（26 场景 × desktop/mobile 52 张基线，逐张审阅）。
- 数据与实时：T57–T60（只读 Polymarket、精确 mapping、replay；真实 REST/WS 验证）。
- 预测与决策：T61–T65（fail-closed benchmark `not_promoted`、quote/policy/engine、one-shot paper、双流编排与延迟门）。
- 产品面：T66–T69（只读 REST/SSE/Chat、typed transport、Home Pulse/`/markets`、Match workbench）。
- 完成门：T70 `01e6ba0`（dual-stream replay/recovery/latency/全回归/视觉门）、T71 `3fde00a`（真实只读 shadow + 证据表）。
- 回归基线：backend 855 确定性 + 50 infrastructure；frontend 392 单测、typecheck/build 干净、Playwright 110 passed/38 skipped（live 门按 env 跳过）。
- 诚实缺口转入 P4：真实历史数据与模型晋升证据、artifact 键对齐、`match_info` 真实来源、退出阈值/仓位优化、性能打磨；自动下单永久 `deferred` 直至单独批准。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-17 | （本提交） | T77 关闭 + Claude Code 领取 T78：daemon、低频 discovery、freshness/stale/gap 与 paper maintenance；起始 `9758288` |
| 2026-09-17 | `9758288` | T77 完成：统一 P2/P3 demand 与 worker 扩展点（焦点 21 + 门 55 passed；确定性 1038 passed；infra 59 passed） |
| 2026-09-17 | `8ce33e0` | T76 关闭 + Claude Code 领取 T77 |
| 2026-09-17 | `8860136` | T76 完成：FastAPI 只读角色与 runtime ownership 分离（焦点 8 + 门 35 passed；确定性 1017 passed） |
| 2026-09-17 | `e8f6bb0` | T75 关闭 + Claude Code 领取 T76 |

## 下一步

1. T78 只执行 [实施计划](./docs/superpowers/plans/2026-09-17-tennixai-p4-local-real-runtime-implementation.md) 的 Task 6：先写失败的 health/scheduler fake-clock 测试，再实现 `RuntimeHealthRegistry`、decision freshness overlay 与 `LocalRuntimeDaemon`；跑恢复 integration 与 worker/decision/延迟回归门；完成后记录实际测试证据、提交、推送，并将 T79 从 `planned` 转为 `ready` 后领取。
2. 后续严格一次一个任务推进 T79–T80；任何 P4 工作不得回溯放宽 P3 边界：只读 provider、one-shot FOK、PostgreSQL 权威、独立 cursor、未晋升即 NO BET。
3. T78 必办遗留项：MarketWorker `_start` 重入防护或注册先于通知、P3 消费幂等（按 book_hash 去重重复 baseline）、RealtimeWorker `callback_failures` 与 P3Metrics 统一进健康面、RuntimeDemand 双源 per-source 隔离/避免 lease 双读、catalog upsert 单写者注释与 partial-fixture 防 None 覆盖、`reason_code` 只写消毒稳定码、`RuntimeHealthDto` 随 `RuntimeHealth` 扩展同步。其余 Minor 留最终整枝评审。
