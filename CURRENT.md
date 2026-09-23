# TennixAI 当前任务与交接

> 快速了解现在做到哪里、最近做完什么、接下来由谁接手。长期路线与阶段证据见 [ROADMAP.md](./ROADMAP.md)，产品定位和稳定架构见 [PROJECT.md](./PROJECT.md)。

**最后更新：** 2026-09-24 04:13 CST

**当前主任务：** T95 — Audit Match Data Fields End-to-End（`in_progress`）。逐项查清比赛相关字段从 API-Tennis 到 canonical/数据库/API/SSE/页面的来源、语义、缺失与时间行为；确认的 bug 要修复并验证。保持服务不重启。

**最近任务：** T95 — Audit Match Data Fields End-to-End (`in_progress`)

**执行者 / 分支：** Codex / `main`；T95 起始提交 `38723c9`；领取提交待记录。T94 已完成（实现 `bbb7d4a`、`d302316`、`93e1243`）；共享运行服务未重启，因此尚未加载 T92/T94 修复。

**实施计划：** [T95 端到端字段审计计划](docs/superpowers/plans/2026-09-24-tennixai-t95-match-field-integrity-audit.md)（正在建立）。

## T95 范围与交接

- 目标：不预设其余字段没有问题；建立 canonical 字段清单，逐一追踪 API-Tennis 官方语义与原始值、provider mapping、reducer/持久化、REST/SSE DTO、前端显示及 `as_of`/freshness。重点覆盖比赛状态/时间、赛事与轮次、场地/赛制、球员身份/国家/排名、比分/发球方、PBP、22 项统计和 momentum。
- 按端到端数据流分批验收，不以“测试全绿”替代真实字段覆盖；有官方文档不清楚之处先核对官方文档，有值不一致之处记录样本、预期和证据。
- 修复范围限于已证实的 bug；不要加入轮询、供应商字段外泄、虚构值或新的架构/产品能力。
- 保留当前运行栈及根目录 `.env`，不读取/输出凭据；不触碰 `.next` 与已知用户未跟踪文件。
- **当前状态：** T95 刚领取；下一步建立字段来源矩阵并识别未被现有测试证明的映射，再对官方文档未覆盖项做有界核验。

## T94 调查结论与验收

- 现场复现：比赛详情/球员资料仍返回 Martin Damm `741`，排名快照为 `106`（快照时间 `2026-09-23T13:32:20Z`），ATP 官方排名页也列为 `106`；搜索结果排名为 `null`。T92 修复已提交，但共享 backend 尚未重启。
- 新发现的代码路径：`RealtimeWorker` 从 PostgreSQL 恢复旧快照；API-Tennis 新资料不含当前排名；`reduce_live_snapshot` 默认会把 incoming `None` 解释为字段缺失并保留旧非空排名，再经 Redis/SSE 发布。T92 未覆盖这条实时恢复路径。
- 目标：REST 与实时发布都只以最新 standings snapshot 为排名依据；缺少当前记录时必须输出 `null`，同时继续保留稀疏 feed 中完整姓名/国家。通过单元/worker 回归证明后完成；生产构建与运行时浏览器验证需另行获准重启共享服务。
- Task 1 已完成代码与 RED→GREEN：比赛详情中目录缺失球员曾错误回退显示供应商旧 rank `40`；现在目录已配置时缺少最新 standings 就返回 `null`。Reducer 新增显式权威模式，rank `106/null` 能替换旧 `741/999`；默认稀疏更新行为不变。验证：`tests/test_live_reducer.py tests/test_player_profile_service.py` 为 `47 passed`。
- Task 2 已完成：`RealtimeWorker` 在每次实时更新前按内部球员 ID 投影最新 standings，排名缺失时清空旧值；`main.py` 与 runtime assembly 都传入现有目录 repo。旧快照和后续稀疏 frame 的存储/SSE 回归均通过，worker suite `10 passed`，Ruff lint 通过。
- 独立审查后补齐两个一致性边缘：REST 排名修正现在同步发布到 Redis/SSE 热快照，worker 会先基于更新后的热快照归约；目录读取临时失败会保留当前 frame 并在 1 秒后重试，不会把错误当作“排名缺失”。新增回归覆盖这两条路径。
- **验收：** 全量后端 `1336 passed, 12 skipped, 25 deselected`（208.49 秒）；player-directory PostgreSQL `9 passed`；改动文件 Ruff 与 `git diff --check` 通过；差异无新增供应商调用、凭据、UI/schema/config 改动。实现提交 `93e1243`。
- **范围说明：** 共享服务未重启，当前浏览器仍可能显示旧进程中的错误排名；服务重启和运行时界面复验需用户授权。排名快照单独同步时不主动 fan-out 到空闲实时订阅；下一次 REST/worker reconcile/feed event 才会看到更新。每个 feed frame 会多做目录与 Redis 热快照读取，先观察延迟/积压再决定是否优化。P4.5 其他字段审计继续，T94 不代表整个 P4.5 完成。

## 最近完成：T93

实施计划：[T93 实施计划](docs/superpowers/plans/2026-09-24-tennixai-t93-live-statistics-preservation.md)。

修复内容：实时 reducer 现在按 `(统计名, 周期)` 合并。WebSocket 更新中缺失的指标会保留原数值和采集时间、标为过时；同时到来的新指标正常更新。页面使用统计自身的最新采集时间，并明确显示旧数据，不再把比赛快照时间误作统计更新时间。未增加轮询、供应商调用或数据库迁移。

验证：最终确定性 backend `1241 passed, 127 deselected`；实时 reducer/provider 定向测试 `71 passed`；frontend Vitest `416 passed`、统计卡定向测试 `7 passed`、TypeScript 检查通过；改动文件 Ruff lint 与 `git diff --check` 通过。独立审查发现并修复两点：旧指标现在显示各自采集时间；数值相同的新观测也会刷新时间戳，重复空帧仍不重复发布。格式检查仍报告两个被修改的 Python 文件有旧格式差异；对照任务前版本确认差异在未触碰的历史代码，没有整文件重排。共享运行栈在使用中，因此未运行会触碰 `.next` 的 build/Playwright，也没有重启服务。

## 最近完成：T92

排名不一致的根因是把 `get_players.stats[].rank`（按赛季、单双打分类的统计）当成当前单打世界排名；同时，目录表的缓存排名和排名快照不一致，导致排名页、搜索、profile 各自显示不同数值。比赛数据写入还可能用缩写名或空字段覆盖较完整的球员资料。

现已统一：排名页、搜索候选、球员主页和比赛卡均从每个 tour 最新的 standings 快照读取当前排名。前后快照用于计算变动；供应商变动字段没有明确比较周期，不直接信任。积分与快照时间随 profile 返回；没有可靠数据的赛季数字保持“暂无”，不补成 0。空排名结果不会覆盖最后一次成功快照。v0 页面布局没有改动。

实施细节、源头核验与限制见 [T92 实施计划](docs/superpowers/plans/2026-09-24-tennixai-player-data-integrity-implementation.md)。

## 验证结果

- 最新 T94 全量确定性 backend：`1336 passed, 12 skipped, 25 deselected`；包括 PostgreSQL 集成用例。T92 历史验证为 `1237 passed`。
- PostgreSQL：player-directory `9 passed`；runtime-catalog `13 passed`。
- 前端最近验证：T93 Vitest `416 passed`；`tsc --noEmit` 通过。T94 无前端改动。
- 本次改动文件 Ruff 通过；`git diff --check` 通过。全仓 Ruff 仍有 27 条旧问题，均位于本次未修改的文件。
- 为保护运行现场，没有执行 Next production build/Playwright：本地 Next 服务正在使用共享 `.next`，且 `frontend/next-env.d.ts` 是用户未跟踪文件。

## 运行状态与交接

- `.env` 未读取、改写或输出；用户原有未跟踪文件均保留。
- 本地服务没有重启。现场核验显示 Match API 对 Martin Damm 返回排名 `741`，最新 standings 与 ATP 官方排名页均为 `106`。代码中的 T92/T94 修复已完成，但浏览器仍连接旧 backend 进程；须经用户授权重启后才能确认页面实际显示修复后的排名。
- T93 实现与审查修复提交 `a28b971`、`fa00f46` 已完成；本文件和 ROADMAP 的最终关闭记录随本次推送。
- P4.5 其余实时字段审计仍在继续。模型晋升证据链需另行设计与授权，自动下单继续 `deferred`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-24 | `93e1243` | 完成 T94：REST 排名权威修正同步至热快照/SSE，实时 worker 对临时目录故障保留 frame 并重试；全后端 1336 passed、12 skipped，PostgreSQL player directory 9 passed |
| 2026-09-24 | `fa00f46` | 按独立审查补齐逐项统计时间显示及数值不变时的新观测时间更新 |
| 2026-09-24 | `a28b971` | 完成 T93 主体：保留稀疏 WebSocket 帧遗漏的技术统计并标记过时 |
| 2026-09-24 | `ec60ad8` | 领取 T93：修复稀疏 WebSocket 帧清空已有技术统计及统计时间戳误用 |
| 2026-09-24 | `0621c18` | 修复排名快照权威性、球员资料覆盖、profile/前端字段和空值语义；测试证据见上方及 T92 计划 |
| 2026-09-23 | `784ccf8` | 完成 T91：全目录真实 Polymarket 报价与刷新；未映射/双打只展示，不进入模型或 Paper |
