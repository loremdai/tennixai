# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-17 06:50 CST

**当前任务：** 无（P3 已于 2026-09-17 关闭；P4 `planned` 未领取）

**任务状态：** 无 `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（T57–T71 顺序执行授权已完成使命）

**分支：** `main`

**最后提交：** `3fde00a`（T71 shadow gate 测试）+ 本次关闭文档提交

**当前动作：** P3 关闭交接。T71 以真实只读 shadow gate 收尾：根 `.env` 无 `TENNIX_MODEL_DATA_PATH`、audit/verify-artifact fail-closed（exit 2/4）→ 模型保持 `not_promoted`；真实 API-Tennis + 公共 Polymarket smoke 3 passed/1 带日期诚实 skip（UTC 2026-09-16 公共 WS 网球通道 45s 静默，tokens=4、control=1）；shadow backend 4 passed（零交易凭据、UNPROMOTED 只输出 NO BET/MARKET_ONLY、映射市场只读观察、rules 缺失 fail-closed、公共面零 wallet 材料）；真实浏览器 4 passed（desktop+mobile 只读流、零交易 CTA、DOM/URL 零 provider ID、404 逐路径诚实核验）。T70 门复跑全绿。下一步若启动 P4，须先由用户在 ROADMAP 领取并定义范围；自动下单仍为 `deferred`，不因 P3 完成而获得授权。

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
| 2026-09-17 | `3fde00a` | T71 完成：真实只读 shadow gate（backend live 4 passed + 浏览器 4 passed）与证据表；P3 关闭 |
| 2026-09-17 | `90dedf3` | T70 关闭 + Claude 领取 T71 |
| 2026-09-17 | `01e6ba0` | T70 完成：dual-stream replay/recovery/latency integration 门、exit-missed 缺陷修复、全量回归与视觉门 |
| 2026-09-17 | `2f6fb89` | T69 关闭 + Claude 领取 T70 |
| 2026-09-17 | `64bb505` | T69 完成：生产 Match Decision Workbench |

## 下一步

1. 无已领取任务。P4 启动前需要用户明确领取与范围定义（ROADMAP 里程碑表）。
2. 若复跑 P3 门：命令见 ROADMAP T70/T71 行（infrastructure、live smoke、shadow、Playwright 全量与 `p3.visual`）。
3. 任何 P4 工作不得回溯放宽 P3 边界：只读 provider、one-shot FOK、PostgreSQL 权威、独立 cursor、未晋升即 NO BET。
