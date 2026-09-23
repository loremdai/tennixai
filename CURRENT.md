# TennixAI 当前任务与交接

> 这是给项目参与者快速接手的状态摘要。阶段计划与长期证据见 [ROADMAP.md](./ROADMAP.md)，产品稳定约束见 [PROJECT.md](./PROJECT.md)。

**最后更新：** 2026-09-24 00:15 CST

**当前任务：** T92 — Audit and Repair Player Data Field Integrity

**任务状态：** `in_progress`

**执行者 / ADE：** Codex；**分支：** `main`；**起始提交：** `08c4c1a`
**领取记录：** `3f7f121`（已推送）；**完成提交：** —

## 当前目标

查清球员数据链路中排名、积分、变动、快照时间、球员身份/中英文名、国家、资料与赛季统计字段的权威来源和映射；修复可由本项目代码证明的错误，保留供应商未提供或语义不明字段的 unavailable，不编造数据。覆盖排名页、搜索/Resolver、比赛卡和球员主页，验证当前本地真实运行数据。

## 任务开始基线

- 本地 `main` 与 `origin/main` 同步，起始 HEAD `08c4c1a`，tracked 工作区干净。
- 本地完整应用已在运行；不停止、不重启其所有者进程，必要时只使用只读本地 API 核验。
- 根 `.env` 不读取/改写/输出；现存未跟踪文件均属用户，保持原样。
- API-Tennis 官方 standings 文档示例字段为 `place/player/player_key/league/movement/country/points`，没有正式生效日期字段；供应商 `get_players.stats` 是按赛季且区分 singles/doubles 的资料，不能未经筛选作为当前单打世界排名。
- 本地复现（2026-09-24）：Alycia Parks 排名页 `rank=70, points=957`，嵌套 `player.ranking=72`；搜索和个人页也返回 72。WTA 官方记录 Sep 21 为 70、Sep 14 为 72。ATP/WTA Top 200 共 400 行中，97 行嵌套 rank 缺失、另有 2 行非空 rank 不一致；97 行名字缩写、103 行缺国家代码、98 行缺中文主名。
- 根因方向已证实：搜索/个人页使用 `PlayerRow.ranking` 或 `_latest_ranking(get_players.stats)`；比赛 persistence 可覆盖排名/国家/姓名；profile frontend 将积分、变动和快照时间硬编码映射为空。逐项实施见 [T92 计划](docs/superpowers/plans/2026-09-24-tennixai-player-data-integrity-implementation.md)。

## 最近完成

完成了 Gamma 完整目录、市场安全退役、未映射/双打真实报价展示、REST 快照轮转、独立只读行情 WebSocket、报价变化 SSE，以及 `/markets` 分页和 Load more。用户选定的边界保持：所有活跃网球胜者市场展示供应商真实名称/报价；未严格映射的场次不进入模型、机会或 Paper。机会页在模型未晋升时仍诚实为空。

完整实现与验收证据见 [T91 实施计划](docs/superpowers/plans/2026-09-23-tennixai-polymarket-quote-refresh-implementation.md)。

## 已验证结果

- 后端确定性测试：`1223 passed, 122 deselected`；隔离 PostgreSQL 集成测试：`19 passed`。
- 前端：Vitest `410 passed`；TypeScript、生产 build 通过。
- Playwright：功能 `92 passed / 40 gated skips`；视觉 `34 passed / 4 gated skips`；批准的视觉截图无变化。
- Gamma/CLOB 无凭据只读核验成功；样本的两个 outcome 均返回真实报价。未输出供应商标识或原始 payload。
- 官方 WebSocket 文档确认 `best_bid_ask`、`custom_feature_enabled` 与 10 秒应用心跳：[Polymarket Realtime Data](https://docs.polymarket.com/market-data/realtime-data)。
- Ruff lint 与 `git diff --check` 通过。3 个历史文件在 `origin/main` 上已有 Ruff formatter 差异；未做大范围无关重排。

## 环境与保护

- 完整项目应用未启动；Playwright 临时服务已退出，3100/8000 端口关闭。
- 本任务创建的隔离数据库 `tennix_t91_test` 已删除。PostgreSQL/Redis 容器早于本任务创建，保留运行。
- `.env` 未改。不得修改、删除或提交用户原有未跟踪内容：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 下一步

T92 完成后，再安排下一项工作。模型晋升证据链需单独设计和授权；自动下单继续 `deferred`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-24 | — | 领取 T92：球员排名/资料字段完整性排查与修复；具体代码和验收证据待完成后记录 |
| 2026-09-23 | `784ccf8` | 完成并推送 T91：全目录真实报价与刷新，未映射/双打仅展示，模型与 Paper 边界保持不变 |
