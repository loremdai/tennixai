# TennixAI 当前任务与交接

> 快速了解现在做到哪里、最近做完什么、接下来由谁接手。长期路线与阶段证据见 [ROADMAP.md](./ROADMAP.md)，产品定位和稳定架构见 [PROJECT.md](./PROJECT.md)。

**最后更新：** 2026-09-24 19:52（北京时间）

**当前主任务：** T98 — 全产品缺陷与字段真相审计（`in_progress`）。按用户当前 Goal，检查全部产品页面与关键数据链路，修复有证据的 bug，并查清其余字段的来源、语义、缺失规则和显示方式。当前继续使用演示/fixture 数据；用户明确选择暂不初始化，不运行 `init`、真实 API 或 LLM。

**最近任务：** T98 — 全产品缺陷与字段真相审计（`in_progress`），起始提交 `4ccf257`。

**执行者 / 分支：** Codex / `main`；T98 起始提交 `4ccf257`。保留工作区内已存在的用户改动，未纳入 T98。

**运行手册与计划：** [本地真实运行手册](docs/runbooks/local-real-runtime.md)；[T98 审计规格（待审阅）](docs/superpowers/specs/2026-09-24-tennixai-whole-product-audit.md)；[T97 审计计划](docs/superpowers/plans/2026-09-24-tennixai-t97-global-field-presentation-audit.md)；[T95–T97 字段矩阵](docs/research/2026-09-24-tennixai-t95-match-field-integrity-matrix.md)。

## T98 全产品缺陷与字段真相审计（`in_progress`）

- **目标：** 以当前代码、测试、演示页面和官方数据契约为证据，跨 Home、Players、Match、Markets、Opportunities、Paper 及关键后端链路逐域走查；修复可复现 bug，并为每个对外字段确认来源、转换、空值/异常语义及验证证据。
- **起始状态：** `main` / `4ccf257`，与 `origin/main` 同步；工作区现有用户改动按下方已知清单保留。
- **边界：** 继续使用演示/fixture 数据；不运行 `init`、真实 provider/LLM 请求，不读取或修改根 `.env`，不访问 `.next`，不启停本任务之外的服务或容器。
- **进度：** 已完成代码/路由/DTO/既有矩阵的只读盘点。发现三项待回归验证的 Chat 缺陷：① 后端会发出 `market_opportunities` / `match_decision` 结构化结果，但前端类型未包含这两种 `kind`，首页可能将其误报为“没有符合条件的比赛”且不呈现结构化 P3 结果；② Chat 流在 `done/error` 前 EOF 会走成功分支，并把部分回答写入下一轮历史；③ 后端可在同一轮发出多个不同 `data` 结果、前端也累积了 `dataItems`，但首页比赛卡片只读最后一条 `chat.data`，多项比赛查询可能丢卡。证据：`backend/app/chat/tools.py`、`backend/app/chat/executor.py`、`backend/app/chat/orchestrator.py`、`backend/tests/test_chat_orchestrator.py`、`frontend/lib/api/types.ts`、`frontend/components/home/home-assistant.tsx`、`frontend/hooks/use-chat-stream.ts`、`frontend/hooks/use-chat-stream.test.tsx`。字段清单对照还发现既有 T95–T97 矩阵没有逐字段覆盖 Player Resolution、Match Catalog（筛选项/计数/featured match）、全部公开 Chat 事件与 P3 Chat 结构化字段、P3 SSE 事件、错误信封及运行健康 DTO；这些字段需继续追踪并标为面向用户或仅技术用途。另经 [Polymarket 官方价格与订单簿文档](https://docs.polymarket.com/market-data/prices-order-books) 核验，供应商给的是各结果独立的盘口档位；本地 `spread` 实为有 bid/ask 的结果价差均值，`depth_usd` 实为两种结果的最佳 bid/ask 名义金额合计，而生产页写作“买卖价差/可交易金额”。这是需进一步评估的字段语义/文案不匹配线索，尚未认定或修复。审计规格已写入，待用户审阅确认后编制逐项执行计划；上述缺陷和文案线索均未修改或以回归测试验收。

## T97 Global Field Presentation Audit (`done`)

- **目标：** 按全站页面核对字段可见性与表达是否准确，不把真实供应商缺项误报为 UI bug，也不把测试夹具通过当成真实数据通过。
- **范围：** Home/全局搜索与结构化回答、Players 排名目录/球员主页/历史结果、Match 详情（比分/时间/球员/赛事/统计/PBP/momentum/chat/决策）、Markets（两侧报价/深度/时间/模型状态/机会原因）、Paper ledger，以及桌面/窄屏布局、缺省/错误/partial/stale 状态、北京时区和供应商字段隔离。
- **起始状态：** `main` / `c84fa6d`，工作区只有已知用户未跟踪文件；服务栈停止，`./scripts/tennix-live up` 之前返回 `LOCAL_NOT_INITIALIZED`。不读取或修改根 `.env`，不运行 LLM 消耗型 `init`，不手工迁移数据库。
- **证据方法：** 复用 T95–T96 canonical 字段矩阵和现有 E2E/fixtures；打开实际页面检查完整用户可见字段，按供应商能力、映射/数据、传输/缓存、展示层分层记录；每个确认缺陷必须有复现样例和回归测试。
- **验收门：** 全部列出页面至少有浏览器或 E2E 实际覆盖证据；真实运行时无法启动则单独列为阻塞，不声称真实数据通过；修复已证实问题并更新矩阵；运行受影响测试、前端测试/typecheck、相关 Playwright、改动文件 lint 和 `git diff --check`；最终提交并推送。
- **交付：** Home 移除产品阶段开关、重复入口、未实现的球员关注/历史入口和虚构市场概率卡；搜索与赛程发现仍在首页主路径。Players、Match、Markets、机会和 Paper 页面统一为面向网球用户的中文文案，保留数据来源、空值、延迟、未成交和模拟状态的区别。球员排名更新时间明确标为北京时间；未知决策原因不再泄漏内部代码。未改变供应商、预测、决策或 paper 语义。
- **验证：** 前端 Vitest `35 files / 454 passed`；TypeScript `tsc --noEmit` 通过；Playwright 的 P3 市场/比赛页面桌面与手机检查 `58 passed`，Home 结构化问答桌面/手机 `2 passed`；后端问答文案定向测试 `2 passed`；`git diff --check` 通过。较宽的两份 Chat 测试有 `53 passed / 1 failed`：唯一失败的比赛上下文流测试因本机 Redis `127.0.0.1:6379` 未运行而无法执行；没有为此启动 Redis。仓库无前端 lint 脚本或 ESLint 可执行文件。
- **真实数据边界：** 用户批准使用真实服务，但选择不执行首次初始化。`tennix-live status` 显示受管运行栈停止、无持久健康记录、无 Postgres/Redis 容器；真实浏览器数据门因此保持阻塞。首页/球员页所见是演示数据，Match 页面显示可恢复的加载错误，Markets 显示 P3 未开放状态；这些不是实时 API 验收。未运行 `init`、真实供应商/LLM 调用，未读取/修改根 `.env`，未启动/停止容器或服务，未访问 `.next`。
- **保留的用户改动：** `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/app/service.py`、`backend/tests/test_p3_query_freshness.py` 与 `frontend/next-env.d.ts` 均未纳入 T97 提交。

## T96 Player and Historical Results Field Audit (`done`)

- **范围与结论：** 审计排名、球员资料/赛季统计、球员历史赛果与 Home Chat 历史查询，并逐字段更新证据矩阵。共修复 25 个已由回归证明的问题，包括国家名称归一化/旗帜显示、历史比分缺少逐盘行时保留明确标注的总盘数、单双打边界、日期语义与不完整历史误报。
- **修复：** API-Tennis 国家名称通过 ISO registry 映射为 canonical alpha-3；alpha-2 仅作派生展示字段，前端使用动态旗帜资源，不维护手绘国家清单。历史比分仅在详细盘分不可用时显示供应商真实的总盘数，不臆造每盘局分。Home Chat 的 last/recent/yesterday 结果只取单打，遇到无法确定日期的供应商记录时标记为 partial。
- **验收：** 定向后端 `161 passed`；全量确定性后端 `1314 passed, 4 failed, 103 skipped, 25 deselected`。4 个失败用例在断开的 `127.0.0.1:6379` Redis 处无法执行到断言；按本任务边界未启动 Redis。前端 Vitest `432 passed`、TypeScript、改动 Python Ruff、`uv lock --check` 与 `git diff --check` 通过。实现提交 `b4acb8b`；细节与限制见 [T96 实施计划](docs/superpowers/plans/2026-09-24-tennixai-t96-history-h2h-field-audit.md) 和 [字段矩阵](docs/research/2026-09-24-tennixai-t95-match-field-integrity-matrix.md)。
- **边界与后续：** 未运行 `init`、未启动服务/容器、未调用真实 API/LLM、未触碰 `.env` 或 `.next`。数据库中先前已存为 null 的国家值需等下一次正常数据同步才会被供应商映射补齐；本任务未做运行中页面复验。T94 的本地浏览器复验仍待初始化授权。

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
- T96 实现提交 `b4acb8b` 已完成；P4.5 的 T93–T96 代码审计均已关闭，只剩 T94 修复后的服务/浏览器复验。模型晋升证据链需另行设计与授权，自动下单继续 `deferred`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-24 | `b4acb8b` | 完成 T96：修复球员国家名/旗帜归一化、历史总盘数缺失显示、Chat 单打与不完整历史标记；后端定向 161 passed、前端 432 passed、TypeScript 通过 |
| 2026-09-24 | `3ae508c` | 完成 T95：新增端到端字段矩阵；修复当前盘误标、未知 PBP 标记、统计/比分校验和 freshness 持久化；后端 1289 passed、前端 422 passed，PostgreSQL round-trip 与迁移回滚守卫通过 |
| 2026-09-24 | `93e1243` | 完成 T94：REST 排名权威修正同步至热快照/SSE，实时 worker 对临时目录故障保留 frame 并重试；全后端 1336 passed、12 skipped，PostgreSQL player directory 9 passed |
| 2026-09-24 | `fa00f46` | 按独立审查补齐逐项统计时间显示及数值不变时的新观测时间更新 |
| 2026-09-24 | `a28b971` | 完成 T93 主体：保留稀疏 WebSocket 帧遗漏的技术统计并标记过时 |
