# TennixAI 当前任务与交接

> 快速了解现在做到哪里、最近做完什么、接下来由谁接手。长期路线与阶段证据见 [ROADMAP.md](./ROADMAP.md)，产品定位和稳定架构见 [PROJECT.md](./PROJECT.md)。

**最后更新：** 2026-09-24 01:53 CST

**当前主任务：** T93 — Preserve Live Statistics Across Sparse WebSocket Updates (`in_progress`)

**最近任务：** T93 — Preserve Live Statistics Across Sparse WebSocket Updates (`in_progress`)

**执行者 / 分支：** Codex / `main`；起始提交 `86a6812`；任务领取记录正在提交。此前 T92 已完成并推送（实现 `0621c18`，总控 `86a6812`）。

## 当前任务：T93

实施计划：[T93 实施计划](docs/superpowers/plans/2026-09-24-tennixai-t93-live-statistics-preservation.md)。

已验证的问题：API-Tennis WebSocket 的消息可以带空 `statistics` 数组；当前 reducer 会用空数组覆盖 REST 首次快照里已有的技术统计。最小复现确认统计行数从 1 变成 0，并额外发出 `statistics_updated`。前端还把整份比赛快照的 `as_of` 当作统计更新时间。计划修复为保留最后一次真实统计、明确标记其可能过时，并显示统计自身的采集时间；不增加 REST 轮询或供应商调用。

任务起始提交：`86a6812`；运行服务不重启，根 `.env` 与用户未跟踪文件保持不动。

## 最近完成：T92

排名不一致的根因是把 `get_players.stats[].rank`（按赛季、单双打分类的统计）当成当前单打世界排名；同时，目录表的缓存排名和排名快照不一致，导致排名页、搜索、profile 各自显示不同数值。比赛数据写入还可能用缩写名或空字段覆盖较完整的球员资料。

现已统一：排名页、搜索候选、球员主页和比赛卡均从每个 tour 最新的 standings 快照读取当前排名。前后快照用于计算变动；供应商变动字段没有明确比较周期，不直接信任。积分与快照时间随 profile 返回；没有可靠数据的赛季数字保持“暂无”，不补成 0。空排名结果不会覆盖最后一次成功快照。v0 页面布局没有改动。

实施细节、源头核验与限制见 [T92 实施计划](docs/superpowers/plans/2026-09-24-tennixai-player-data-integrity-implementation.md)。

## 验证结果

- 确定性 backend：`1237 passed`（不含 live 与 integration 测试）。
- PostgreSQL：player-directory `9 passed`；runtime-catalog `13 passed`。
- 前端：Vitest `415 passed`；`tsc --noEmit` 通过。
- 本次改动文件 Ruff 通过；`git diff --check` 通过。全仓 Ruff 仍有 27 条旧问题，均位于本次未修改的文件。
- 为保护运行现场，没有执行 Next production build/Playwright：本地 Next 服务正在使用共享 `.next`，且 `frontend/next-env.d.ts` 是用户未跟踪文件。

## 运行状态与交接

- `.env` 未读取、改写或输出；用户原有未跟踪文件均保留。
- 本地服务没有重启。只读 API 核验确认当前进程仍是 T92 前的旧代码，因此浏览器暂时不会显示排名修复；需要用户同意后再安排重启验证。
- 完成提交 `0621c18` 已推送；当前关闭记录将与本文件、ROADMAP 一起推送。
- 下一项尚未领取；模型晋升证据链需另行设计与授权，自动下单继续 `deferred`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-24 | 待提交 | 领取 T93：修复稀疏 WebSocket 帧清空已有技术统计及统计时间戳误用 |
| 2026-09-24 | `0621c18` | 修复排名快照权威性、球员资料覆盖、profile/前端字段和空值语义；测试证据见上方及 T92 计划 |
| 2026-09-23 | `784ccf8` | 完成 T91：全目录真实 Polymarket 报价与刷新；未映射/双打只展示，不进入模型或 Paper |
