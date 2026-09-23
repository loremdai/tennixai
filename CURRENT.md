# TennixAI 当前任务与交接

> 快速了解现在做到哪里、最近做完什么、接下来由谁接手。长期路线与阶段证据见 [ROADMAP.md](./ROADMAP.md)，产品定位和稳定架构见 [PROJECT.md](./PROJECT.md)。

**最后更新：** 2026-09-24 02:40 CST

**当前主任务：** 无。T93 已完成（实现提交 `a28b971`、审查修复 `fa00f46`）；接下来需经用户同意重启本地服务，验证 T92 排名修复，再继续 P4.5 字段审计。

**最近任务：** T93 — Preserve Live Statistics Across Sparse WebSocket Updates (`done`)

**执行者 / 分支：** Codex / `main`；起始提交 `86a6812`；领取提交 `ec60ad8`；实现提交 `a28b971`、审查修复 `fa00f46`。此前 T92 已完成并推送（实现 `0621c18`，总控 `86a6812`）。

## 最近完成：T93

实施计划：[T93 实施计划](docs/superpowers/plans/2026-09-24-tennixai-t93-live-statistics-preservation.md)。

修复内容：实时 reducer 现在按 `(统计名, 周期)` 合并。WebSocket 更新中缺失的指标会保留原数值和采集时间、标为过时；同时到来的新指标正常更新。页面使用统计自身的最新采集时间，并明确显示旧数据，不再把比赛快照时间误作统计更新时间。未增加轮询、供应商调用或数据库迁移。

验证：最终确定性 backend `1241 passed, 127 deselected`；实时 reducer/provider 定向测试 `71 passed`；frontend Vitest `416 passed`、统计卡定向测试 `7 passed`、TypeScript 检查通过；改动文件 Ruff lint 与 `git diff --check` 通过。独立审查发现并修复两点：旧指标现在显示各自采集时间；数值相同的新观测也会刷新时间戳，重复空帧仍不重复发布。格式检查仍报告两个被修改的 Python 文件有旧格式差异；对照任务前版本确认差异在未触碰的历史代码，没有整文件重排。共享运行栈在使用中，因此未运行会触碰 `.next` 的 build/Playwright，也没有重启服务。

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
- 本地服务没有重启。只读 API 核验发现当前 Match API 对 Martin Damm 返回排名 `741`，排名列表 standings 快照为 `106`，而官网个人页也显示 `106`。原因是运行中的 backend 进程早于 T92 修复；T92 代码现已改为从最新 standings 快照读取排名。需要用户同意后重启本地服务，才能验证浏览器中的修复结果。
- T93 实现与审查修复提交 `a28b971`、`fa00f46` 已完成；本文件和 ROADMAP 的最终关闭记录随本次推送。
- P4.5 其余实时字段审计仍在继续。模型晋升证据链需另行设计与授权，自动下单继续 `deferred`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-24 | `fa00f46` | 按独立审查补齐逐项统计时间显示及数值不变时的新观测时间更新 |
| 2026-09-24 | `a28b971` | 完成 T93 主体：保留稀疏 WebSocket 帧遗漏的技术统计并标记过时 |
| 2026-09-24 | `ec60ad8` | 领取 T93：修复稀疏 WebSocket 帧清空已有技术统计及统计时间戳误用 |
| 2026-09-24 | `0621c18` | 修复排名快照权威性、球员资料覆盖、profile/前端字段和空值语义；测试证据见上方及 T92 计划 |
| 2026-09-23 | `784ccf8` | 完成 T91：全目录真实 Polymarket 报价与刷新；未映射/双打只展示，不进入模型或 Paper |
