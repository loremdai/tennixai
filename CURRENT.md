# TennixAI 当前任务与交接

> 快速了解现在做到哪里、最近做完什么、接下来由谁接手。长期路线与阶段证据见 [ROADMAP.md](./ROADMAP.md)，产品定位和稳定架构见 [PROJECT.md](./PROJECT.md)。

**最后更新：** 2026-09-24 10:45 CST

**当前主任务：** T96 — Player History and Head-to-Head Field Audit（`in_progress`）。T94 本地运行时/浏览器复验仍因 `LOCAL_NOT_INITIALIZED` 阻塞；`init` 会初始化运行库并可能消耗 LLM 配额，尚未获准执行。

**最近任务：** T95 — Audit Match Data Fields End-to-End (`done`)，实现提交 `3ae508c`。

**执行者 / 分支：** Codex / `main`；T96 起始提交 `843bae4`，领取记录随本次计划提交。T94 复验起始提交 `6694c7a`，领取提交 `19e2156`；T95 起始提交 `38723c9`，领取提交 `c52ffc4`，实现提交 `3ae508c`。T94 代码已完成（`bbb7d4a`、`d302316`、`93e1243`），运行时/浏览器门等待初始化授权。

**运行手册与背景计划：** [本地真实运行手册](docs/runbooks/local-real-runtime.md)；[T94 排名一致性计划](docs/superpowers/plans/2026-09-24-tennixai-t94-realtime-ranking-authority.md)；[T96 历史赛果/H2H字段审计计划](docs/superpowers/plans/2026-09-24-tennixai-t96-history-h2h-field-audit.md)。最近完成的比赛字段审计：[T95 计划](docs/superpowers/plans/2026-09-24-tennixai-t95-match-field-integrity-audit.md)；[T95 字段矩阵](docs/research/2026-09-24-tennixai-t95-match-field-integrity-matrix.md)。

## T96 Player History and Head-to-Head Field Audit (`in_progress`)

- **范围：** 补查 T95 未覆盖的 canonical `HeadToHead` 与 service 层 `HeadToHeadResult`、`PlayerResults`，从 API-Tennis DTO/provider 映射追踪至服务缓存、REST/chat 和球员结果 UI；补齐矩阵中每个字段的来源、顺序/身份、空值、截断、freshness 和消费者。
- **待验证疑点：** 服务仅在 `meetings` 达到内部十条上限时标记 aggregate `partial`，但 provider 也会分别把 `first_player_recent`、`second_player_recent` 截到十条。先用回归测试确认，再决定是否修复。
- **官方语义：** API-Tennis 文档说明 `get_H2H` 返回 `H2H`、`firstPlayerResults`、`secondPlayerResults` 三组结果，但没有声明最大条数；十条限制是本项目的本地上限。未知含义不得猜测。
- **边界：** 本任务不运行 `init`、不启动项目服务、不调用真实 API、不读取/修改根 `.env`，不触碰 `.next`；Colima 保持运行，但用户要求停止的其他项目容器和 Tennix 服务均保持停止。
- **验收：** 先看到回归测试按预期失败；若证实缺陷则最小修复并测试各列表上限/未截断边界。运行相关 service/provider/API/chat/player-results 测试、可运行的确定性后端测试、改动文件 Ruff 与 `git diff --check`。准确记录因 PostgreSQL 未运行而未能执行的测试，不宣称通过。

## T95 范围与交接

- 目标：不预设其余字段没有问题；建立 canonical 字段清单，逐一追踪 API-Tennis 官方语义与原始值、provider mapping、reducer/持久化、REST/SSE DTO、前端显示及 `as_of`/freshness。重点覆盖比赛状态/时间、赛事与轮次、场地/赛制、球员身份/国家/排名、比分/发球方、PBP、22 项统计和 momentum。
- 按端到端数据流分批验收，不以“测试全绿”替代真实字段覆盖；有官方文档不清楚之处先核对官方文档，有值不一致之处记录样本、预期和证据。
- 修复范围限于已证实的 bug；不要加入轮询、供应商字段外泄、虚构值或新的架构/产品能力。
- 保留当前运行栈及根目录 `.env`，不读取/输出凭据；不触碰 `.next` 与已知用户未跟踪文件。
- **完成结果：** 建立覆盖 canonical 比赛字段的端到端证据矩阵；依据 API-Tennis 官方 REST/WS 文档及 fixtures 记录每个字段的来源、单位、缺失值和未公开语义。修复错误的当前盘标签/高亮、未文档化 PBP 关键分被误当成 false、比分/技术统计非法值或单位不准确、freshness 持久化丢失等问题。比分盘数只在供应商明确返回 `Set N` 时展示；无依据的值保持未知。
- **验证：** 后端确定性 `1289 passed, 128 deselected`；前端 Vitest `422 passed`；TypeScript、改动 Python 文件 Ruff 与 `git diff --check` 通过。真实 PostgreSQL round-trip `1 passed`；迁移 `0008` 在有 freshness 数据时安全拒绝回滚，实测版本仍为 `0008`、数据和列均保留。API-Tennis standings 真实只读 smoke `1 passed`。
- **运行边界：** 未运行项目 `init/up`、未触碰 `.env` 或 `.next`，未做浏览器/运行服务复验。真实 standings API 映射已单独验证，但当前页面是否已刷新排名、后台健康状态是否恢复，仍须启动服务后确认。其他项目的 Supabase 容器和本次 T95 临时 PostgreSQL/Redis 容器均已停止，未删除容器卷或数据；Colima 保持运行。

## T94 本地运行时/浏览器复验（阻塞：等待用户批准初始化）

- 用户已授权启用本地 API/服务；其他项目自动启动的容器按用户选择已停止。
- `./scripts/tennix-live up` 已尝试，明确拒绝并返回 `LOCAL_NOT_INITIALIZED`；API、runtime、frontend 没有启动。
- 启动依赖容器后读到的持久健康快照生成于 `2026-09-23T22:26:54Z`（约 4 小时旧），当时 schedule/rankings 标为 `ok`；这不是本次运行的刷新证明。数据库停着时健康快照不可读，因此之前显示 `unknown`。
- 下一步必须运行 `./scripts/tennix-live init` 才能初始化专用运行库并继续；按 runbook，此步骤会同步赛程/排名，且可能通过 LLM 批量补齐中文名、消耗配额。等待用户明确批准，不绕过 `init` 或改用手工迁移。
- 已执行 `./scripts/tennix-live down`；Tennix PostgreSQL/Redis 与其他项目自动启动的 Supabase 容器均已停止，未删除容器或 Docker volume；最终 `docker ps` 为空，Colima 保持运行。

## T94 调查结论与验收

- 现场复现：比赛详情/球员资料仍返回 Martin Damm `741`，排名快照为 `106`（快照时间 `2026-09-23T13:32:20Z`），ATP 官方排名页也列为 `106`；搜索结果排名为 `null`。T92 修复已提交，但共享 backend 尚未重启。
- 新发现的代码路径：`RealtimeWorker` 从 PostgreSQL 恢复旧快照；API-Tennis 新资料不含当前排名；`reduce_live_snapshot` 默认会把 incoming `None` 解释为字段缺失并保留旧非空排名，再经 Redis/SSE 发布。T92 未覆盖这条实时恢复路径。
- 目标：REST 与实时发布都只以最新 standings snapshot 为排名依据；缺少当前记录时必须输出 `null`，同时继续保留稀疏 feed 中完整姓名/国家。代码与单元/worker 回归已完成；运行时浏览器验证尚未执行，用户之后已允许启用本地 API/服务，可作为独立复验任务。
- Task 1 已完成代码与 RED→GREEN：比赛详情中目录缺失球员曾错误回退显示供应商旧 rank `40`；现在目录已配置时缺少最新 standings 就返回 `null`。Reducer 新增显式权威模式，rank `106/null` 能替换旧 `741/999`；默认稀疏更新行为不变。验证：`tests/test_live_reducer.py tests/test_player_profile_service.py` 为 `47 passed`。
- Task 2 已完成：`RealtimeWorker` 在每次实时更新前按内部球员 ID 投影最新 standings，排名缺失时清空旧值；`main.py` 与 runtime assembly 都传入现有目录 repo。旧快照和后续稀疏 frame 的存储/SSE 回归均通过，worker suite `10 passed`，Ruff lint 通过。
- 独立审查后补齐两个一致性边缘：REST 排名修正现在同步发布到 Redis/SSE 热快照，worker 会先基于更新后的热快照归约；目录读取临时失败会保留当前 frame 并在 1 秒后重试，不会把错误当作“排名缺失”。新增回归覆盖这两条路径。
- **验收：** 全量后端 `1336 passed, 12 skipped, 25 deselected`（208.49 秒）；player-directory PostgreSQL `9 passed`；改动文件 Ruff 与 `git diff --check` 通过；差异无新增供应商调用、凭据、UI/schema/config 改动。实现提交 `93e1243`。
- **范围说明：** 该任务当时未重启共享服务；T95 也按范围保持项目应用未启动。T92/T94 代码与真实 standings 只读 smoke 已验证，但页面排名和后台健康状态尚未通过运行时确认；用户已允许启用服务，可在单独复验中完成。排名快照单独同步时不主动 fan-out 到空闲实时订阅；下一次 REST/worker reconcile/feed event 才会看到更新。每个 feed frame 会多做目录与 Redis 热快照读取，先观察延迟/积压再决定是否优化。

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
- T95 未执行 Next production build/Playwright：任务边界要求不重启共享服务，且 `frontend/next-env.d.ts` 是用户未跟踪文件；Vitest 与 TypeScript 检查已通过。

## 运行状态与交接

- `.env` 未读取、改写或输出；用户原有未跟踪文件均保留。
- T95 没有启动或重启本地服务。此前现场比对发现旧 Match API 对 Martin Damm 返回 `741`，最新 standings 与 ATP 官方排名页均为 `106`；T92/T94 代码已修复，真实 standings 只读 smoke 也通过，但页面排名和后台健康状态尚未通过新进程/浏览器复验。用户已允许启用 API/服务，可在下一任务中执行该复验。
- T93 实现与审查修复提交 `a28b971`、`fa00f46` 已完成；本文件和 ROADMAP 的最终关闭记录随本次推送。
- T95 字段审计已完成；P4.5 只剩 T94 修复后的服务/浏览器复验。模型晋升证据链需另行设计与授权，自动下单继续 `deferred`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-24 | `3ae508c` | 完成 T95：新增端到端字段矩阵；修复当前盘误标、未知 PBP 标记、统计/比分校验和 freshness 持久化；后端 1289 passed、前端 422 passed，PostgreSQL round-trip 与迁移回滚守卫通过 |
| 2026-09-24 | `93e1243` | 完成 T94：REST 排名权威修正同步至热快照/SSE，实时 worker 对临时目录故障保留 frame 并重试；全后端 1336 passed、12 skipped，PostgreSQL player directory 9 passed |
| 2026-09-24 | `fa00f46` | 按独立审查补齐逐项统计时间显示及数值不变时的新观测时间更新 |
| 2026-09-24 | `a28b971` | 完成 T93 主体：保留稀疏 WebSocket 帧遗漏的技术统计并标记过时 |
| 2026-09-24 | `ec60ad8` | 领取 T93：修复稀疏 WebSocket 帧清空已有技术统计及统计时间戳误用 |
