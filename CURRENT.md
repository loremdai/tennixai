# TennixAI 当前任务与交接

> 快速了解现在做到哪里、最近做完什么、接下来由谁接手。长期路线与阶段证据见 [ROADMAP.md](./ROADMAP.md)，产品定位和稳定架构见 [PROJECT.md](./PROJECT.md)。

**最后更新：** 2026-09-26（北京时间）

**当前主任务：** T103 — 彻查并修复历史赛果盘分/局分丢失（`in_progress`）。

**最近任务：** T103 — 彻查并修复历史赛果盘分/局分丢失（`in_progress`），起始 HEAD `0d63c48`。

**执行者 / 分支：** Codex / `main`；T103 起始 HEAD `0d63c48`。保留工作区已有 P3 修改与未跟踪文件，不纳入本任务。

**运行手册与证据：** [本地真实运行手册](docs/runbooks/local-real-runtime.md)；[T98 审计规格与完成证据](docs/superpowers/specs/2026-09-24-tennixai-whole-product-audit.md)；[T97 审计计划](docs/superpowers/plans/2026-09-24-tennixai-t97-global-field-presentation-audit.md)；[T95–T98 字段矩阵](docs/research/2026-09-24-tennixai-t95-match-field-integrity-matrix.md)。

## T101 修复过期比赛误入当前列表（`done`）

- **领取：** 2026-09-25 21:22 CST，Codex，`main`，起始 HEAD `5af1b49`；用户已授权修复并要求复核方案。
- **目标：** 当前直播和近期赛程只展示可确认的有效比赛，首页与比赛列表/问答使用一致的时间语义；多日赛程注明北京日期。
- **边界：** 保留历史 canonical 行，不根据时间推定最终赛果；不变更供应商、数据库 schema、市场、模型或 paper。先做确定性回归，再用运行中的本地真实服务复核；不读取或输出根 `.env`。
- **现场保护：** `backend/app/service.py` 中 P3QueryService 的两处用户已有修改及 `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 均不纳入本任务提交。
- **实现：** `2b6e217`。当前直播按最后观测时间限制为 5 倍同步间隔、近期赛程为 3 倍同步间隔且必须有未来开赛时间；使用真实 `age_seconds/is_stale`，配置变更时窗口随同步间隔变化。过滤放在共用 TennisService 读取处，覆盖 Home、目录、列表、球员当前比赛和 Chat，不删除历史行、不推断结束比分。Home 将多日赛程命名为「近期赛程」，展示北京日期与时间，并修正空态和旧市场浏览器验收文案。
- **验证：** 目录/Chat/首页回归先红后绿；后端非 integration 测试文件 `1334 passed`，前端 Vitest `36 files / 485 passed`、TypeScript 与 Next production build 通过；真实本地桌面/手机 Playwright `6 passed`。重启后状态为数据库/Redis healthy，sports stream、schedule、rankings、Polymarket 均 `ok`，runtime/API/frontend 运行中；真实 Home 从旧的默认 44 场直播/186 场赛程收敛为 3 场有效直播/17 场未来赛程，页面核对显示北京日期。包含旧 integration 库的粗跑为 `1409 passed / 16 failed / 12 skipped / 25 deselected`，16 例因本机旧测试库 schema 缺列/约束不符，未把这次运行声称为全绿；未修改或重置该测试库。用户既有 P3 代码与未跟踪文件保留，根 `.env` 未输出或提交；真实服务继续运行。

## T102 逐字段走查并修复球员详情页（`done`）

- **领取：** 2026-09-25 22:04 CST，Codex，`main`，起始 HEAD `5c8e998`。
- **目标：** 对 `/players/ply_44ff6e422d48462aa51b5a06b8d72fdc` 的真实页面逐字段核对数据来源、API 响应、转换和呈现，修复确认的问题，并验证同一路径上的筛选、分页和桌面/手机视口。
- **范围：** 英文/中文名、赛事属性、国籍/旗帜、生日/年龄、排名/积分/变化/时间、赛季摘要、当前比赛、历史记录筛选与表格各字段、空值/错误态。根据证据区分上游未提供与本地映射/展示错误；不推测真实数据，不增加供应商能力。
- **已确认的数据规则：** 完整的 API-Tennis 赛季统计优先显示。供应商没有给出完整统计时，只从本地已记录、可验证的单打赛果计算场数、胜负和胜率，并在对应指标上单独标注来源；不推算冠军数或场地胜负。当前赛果若关键日期、参赛球员或胜者缺失，则不派生摘要；没有可靠指标时隐藏整块摘要。历史比分不补造空值；对手姓名、中文名和国籍由现有 canonical 球员目录补齐，不增加供应商请求。
- **已完成修复：** 比赛摘要与逐场赛果分开；可用局分标为“部分局分”，不再出现空盘占位符；移除赛事轮次重复前缀和面向开发者提示；后端批量目录读取补齐当前结果页对手信息；赛季摘要优先权威供应商统计，无可用供应商统计时按上述可信规则派生，并仅在派生指标上标注来源。
- **验证：** 真实浏览器检查目标球员 profile、结果筛选/重置/分页以及桌面和 390px 手机视口。重启后 2026 赛季显示已收录单打赛果 47 场、44 胜 3 负、胜率 93.6%，没有推算冠军数/场地数据；2025 年使用 API-Tennis 统计，显示 64 场、58–6、90.6%、6 冠及硬地 39–3 / 红土 11–2 / 草地 8–1。历史对手显示完整姓名、中文名和国籍。`./scripts/tennix-live down` / `up` 均成功，数据卷保留且未运行 `init`；数据库、Redis、runtime、API、frontend 与同步状态均正常。后端确定性测试 `1338 passed`；前端 Vitest `37 files / 494 passed`；TypeScript、球员专项测试、P3 查询新鲜度回归、Ruff 与 `git diff --check` 通过。未读取或输出根 `.env`。
- **完成提交：** 实现与回归测试 `a885a6a`；本任务不包含用户已有 P3 工作区差异。总控关闭记录随下一提交。
- **环境与保护：** 复用已运行本地真实服务；不运行 `init`、不读根 `.env`；保留 `backend/app/service.py` 中两处既有 P3 修改及 `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts`，不纳入本任务提交。

## T103 彻查并修复历史赛果盘分/局分丢失（`in_progress`）

- **领取：** 2026-09-26，Codex，`main`，起始 HEAD `0d63c48`；领取记录 `c82cd11`、`0e63258` 已推送。
- **目标：** 查清为什么历史赛果中经常缺少盘分或每盘局分，逐层比较供应商原始返回、provider 解析、canonical `Match/SetScore`、存储读回、REST DTO、前端 view model 与最终页面；修复实际丢失数据的根因，而不是只调整空值文案。
- **调查范围：** 检查 API-Tennis 官方数据契约与多个真实不完整/完整样本；区分“供应商确实未提供”与“本地解析、归约、持久化、缓存、序列化或展示丢失”；覆盖球员历史列表和共享比赛详情路径；确认已落库空值能否通过正常有限重取恢复，以及不可恢复时的诚实呈现。
- **已验证根因（2026-09-26）：** 本地真实 `get_fixtures` 返回抢七盘分为 `score_first="6.7"`、`score_second="7.9"`（另有 `7.7` / `6.2`）；当前 `parse_non_negative_int()` 只接受纯数字字符串，因而把两侧都转成 `null`。同一响应保留 `event_final_result="3 - 1"`，所以盘数在、含抢七的逐盘局分缺失；普通数字分如 `6` / `3` 正常通过。球员赛果 API 与比赛详情 API 都能复现。API-Tennis 官方文档说明 fixtures 内联提供 `scores` 与 `pointbypoint`，但未写明点号编码；该真实响应还含 `Set 1 TieBreak` 等逐分记录，与数值吻合。官方参考：[REST fixtures](https://api-tennis.com/documentation)，[WebSocket score payload](https://api-tennis.com/documentation_websocket)。
- **下一步设计（待确认）：** 把抢七编码解析为可选的局数与抢七小分，贯通现有比赛 DTO 和 UI；对已落库但分数不完整的已结束比赛，仅在用户打开详情时做有缓存的单场刷新并补齐，不批量扫历史、不初始化/迁移数据库；同时防止后续稀疏更新覆盖已知比分。真实缺失仍保持未知。设计获批后再落书面规格与实施计划。
- **执行顺序：** 先建立同一批比赛的逐层证据矩阵与可重复回归，再根据实际故障边界写出实现计划；不猜测缺失比分、不依据胜负反推局分、不改变供应商请求频率或抓取无限历史。
- **验收门：** 至少包含供应商有完整比分、仅有部分比分、确实无比分三类样本；证明有值时端到端不丢、空值不造；修复必须有先失败后通过的测试，覆盖 provider/service/存储/API/UI 中实际受影响层；后端确定性套件、前端相关与全量测试、TypeScript、改动文件 Ruff、`git diff --check` 通过；真实页面/API 用安全脱敏的内部 ID 和比分字段复核。未经必要性确认不迁移 schema、不执行 `init`、不重置数据库。
- **安全与现场：** 不直接查看或输出根 `.env` 文件内容；允许通过应用现有配置对象安全读取凭据，进行有界只读 API 核验。任何 API key、查询凭据、无关供应商 payload 均不得打印或落盘。优先复用已运行本地服务，当前服务/数据保持运行。`backend/app/service.py` 的两处既有 P3 freshness 修改及 `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 均为用户已有改动，不纳入 T103 提交。

## T99 初始化并启动本地真实服务（`done`）

- **目标：** 经用户批准运行一次 `./scripts/tennix-live init`，随后启动真实本地服务并检查健康状态。
- **起始状态：** `main` / `8ee0807`，与 `origin/main` 同步；PostgreSQL/Redis 容器停止。启动后发现保留的数据卷已有数据库（迁移前 `0006`、已有目录数据和历史 init 标记），没有删除或重置数据。工作区内既有用户修改和未跟踪文件全部保留。
- **边界：** 仅通过根目录运行手册和 `./scripts/tennix-live` 操作；不输出或提交 `.env` 凭据；只操作 TennixAI 自有容器/进程，不触碰其他项目容器。初始化可能同步目录并消耗 LLM 配额；用户已明确批准。
- **首次尝试：** `init` 将 schema 从 `0006` 迁移至 `0008`，之后在目录排名引导阶段失败（启动器只报告脱敏的 `AppError`）。ATP/WTA 最新排名仍为 `2026-09-23T13:32:27Z`；初始化顺序证明该次失败发生在中文别名 LLM enrichment 之前，没有调用 LLM。目录数据未删除或重置。
- **首次尝试的供应商核验：** 按官方文档使用大写 `ATP`/`WTA` 的 `get_standings` 请求，均返回 HTTP 200，但响应含 `error` 字段、缺少文档成功响应的 `success` 字段，未返回可用排名。错误正文未输出；官方文档说明 standings 数据取决于当前订阅计划：[API-Tennis 文档](https://api-tennis.com/documentation)。具体账户/套餐原因尚不能从脱敏结果确定。
- **此前状态：** `./scripts/tennix-live status` 显示 PostgreSQL、Redis healthy；runtime、API、frontend 均 stopped，故真实服务尚未启动。此前 `up` 因本地 launcher 初始化成功标记被失败的 `init` 清除而拒绝。
- **本次续接与完成提交：** 用户报告已更新根目录 `.env` 中的 API key 并要求重试；领取记录 `e31c623`，`.env` 内容未读取或输出。验收证据提交 `4d1289a`：`init` exit 0（`revision=0008 players=3976 matches=185`）；`up` exit 0；随后 `status` 显示 PostgreSQL、Redis、sports stream、schedule、rankings、Polymarket 全为 `healthy/ok`，runtime/API/frontend 三进程均 running，`paper_only` / `model not_promoted` 保持原状。首页和 API health 均为 200。`init` 含离线中文名补齐，可能使用 LLM 配额；启动器没有报告实际翻译批次数，无法据此核算。未执行浏览器视觉测试或额外 provider/LLM 核验。
- **安全与范围：** 没有重置既有数据、没有绕过初始化标记、没有碰其他项目容器，也没有输出或提交任何凭据。真实服务保持运行；浏览器视觉/全站内容验收不属于本次启动任务。

## T100 排查首页展示过期比赛（`done`）

- **目标：** 查明首页为什么显示已经结束的旧比赛，区分是 API 源数据、查询范围/排序、日期时区、前端过滤还是缓存导致。
- **起始状态：** `main` / `45a4308`，与 `origin/main` 同步；TennixAI 本地真实服务正在运行。已知工作区改动均为用户所有，本任务只读，不修改产品代码。
- **边界：** 只读取当前浏览器页面、本机应用的只读 HTTP 响应和相关实现；不读取根 `.env`，不发起供应商/LLM 请求，不重启或关闭服务，不改数据库数据，不改任何代码。完成后报告证据与根因；如需修复，另行授权。
- **调查结论：** 不是 API key 过期或服务未运行。北京时间 2026-09-25 20:01 的本机 API 查询中，默认 ATP/WTA 单打“直播”结果 43/43 的开赛时间都已过去，最早为 9 月 18 日；“即将比赛”187 场中 168 场的开赛时间也已过去，最早为 9 月 17 日。最近条目的时间已到 9 月 27 日，因此首页“今晚比赛”还会把未来多日赛程当作今晚展示。
- **根因证据：** 19:59:48 的本机 runtime health 快照显示 `live_catalog` 和 `upcoming_catalog` 最近一次同步分别在 19:59:10 和 19:59:16 成功，说明后台活着；但最旧直播记录仍是 `status=live`、`scheduled_at=2026-09-18T16:55Z`、最后观测时间 `2026-09-18T18:11Z`。目录同步只 upsert 新结果、不清除 feed 中消失的比赛；`MatchCatalogRepository.list_matches` 只按状态查询，不检查开赛时间/最后观测时间；前端按 ATP/WTA 等筛选后直接展示 API 返回的所有比赛，没有过期过滤。目录加载还只设置 freshness 的 `observed_at`，`is_stale=false`、`age_seconds=0` 使用默认值，错误地把一周未观测的数据标成新鲜。
- **完成提交：** `c81c222`（调查结论与证据）、`105a487`（标记调查完成）。没有产品代码改动。现场验证为本机 live/upcoming catalog GET、runtime health GET、Home 与筛选/排序/目录实现核对，`git diff --check` 通过。具体证据见上方调查结论。

## T98 全产品缺陷与字段真相审计（`done`）

- **目标：** 以当前代码、测试、演示页面和官方数据契约为证据，跨 Home、Players、Match、Markets、Opportunities、Paper 及关键后端链路逐域走查；修复可复现 bug，并为每个对外字段确认来源、转换、空值/异常语义及验证证据。
- **起始状态：** `main` / `4ccf257`，与 `origin/main` 同步；工作区现有用户改动按下方已知清单保留。
- **边界：** 继续使用演示/fixture 数据；不运行 `init`、真实 provider/LLM 请求，不读取或修改根 `.env`，不访问 `.next`，不启停本任务之外的服务或容器。
- **完成提交：** `ad3edb9`（实现/测试）；总控与收口说明随后提交。
- **完成情况：** 已修复并有回归的缺陷：Chat 结构化市场机会卡缺失/多条 data 漏卡、EOF 与 `done(ok=false)` 被当成功、错误图标误报比赛卡、候选球员国家码裸露、旧 `/players/search` 客户端类型不符及畸形响应误当无结果、市场未知原因码泄漏、市场价差/最佳档金额文案不精确、持仓退出估算误称可退出金额且未披露未扣费用/未按盘口深度成交、Polymarket 结算 WS 提示未触发及时 REST 核验、已确认结算没有 `resolution_delta` 广播导致页面不及时刷新/盘口不冻结、未知或缺失 phase 被当成完赛/赛前、缺失的单人模型概率被伪造为 0%、待确认/未成交 Paper 行把计划报价误写成已投入/已持有、全部市场的单一模型胜率未注明对应球员，以及球员历史查询在 `unavailable` 时误说“暂无赛果”、`partial/stale` 有结果时未披露限制。另修复首次读取 Home 赛程时球员目录懒加载竞态导致排名短暂为空：目录同步完成前不再读取/覆盖比赛卡球员资料，并确保并发调用等待同一轮同步完成。完整 DTO 字段与未消费项记录在字段矩阵 T98 附录。
- **Chat/市场结算结果：** P3 `market_opportunities` 现显示结构卡并披露截断；`match_decision` 仅 Match scope，独立工作台继续消费 REST/SSE 快照。官方 `market_resolved` 订阅带 `custom_feature_enabled: true` 后只触发 REST 核验；只有供应商 REST `FINAL` 能结算 Paper。该确认在即时提示和 120 秒兜底路径都会发布 `resolution_delta`，重复相同终态只结算、不重复广播；Markets/Home 订阅该事件后刷新，市场 hook 将终态盘口冻结。WS 本身从不决定结算结果。
- **字段结论：** 已逐项记录 Match Catalog facets、Player Resolution、Chat 请求/事件/结构化字段、Home 市场脉搏、基础/runtime 健康、Match/P3 SSE、错误信封，以及此前比赛、球员、历史、市场、机会与 Paper 字段的来源、转换、消费和空值规则。未供普通用户页面消费的字段明确标为内部/未消费；provider 语义未知和真实 runtime 未验收均保留为限制。
- **演示数据覆盖：** 当前没有全站统一的演示模式。`/players?preview=1`、`/match?status=...`、`/markets?preview=p3` 各自可看固定样例；首页 `/?preview=p3` 只控制 P3 预览，首页比赛/搜索仍走后端数据链路。为覆盖全站交互，本次在 `/tmp` 隔离副本里运行 Next + FastAPI：`env -i`、fake provider/LLM、P3 disabled、固定时钟，不复制 `.env`，不触碰项目目录的 `.next`、数据库或真实服务。该做法只验证演示/fixture 链路，不表示真实 provider 全站可用。
- **视觉基线核查：** 旧 Home/Markets/Players 截图已由隔离的演示环境重新生成并写回 76 张桌面/手机基线，覆盖 Home、Players、Markets、P3 Match 多状态；代表页面已人工查看。Playwright 视觉对比 `30 passed / 4 skipped`。4 项是演示模式不运行的 P2 Replay 状态；P1 Match live/upcoming 的 Redis 依赖视觉用例从本轮排除，不能据此声称实时详情页通过。
- **验证：** 前端 Vitest `36 files / 484 passed`；隔离副本 Next production build 与其 TypeScript 检查通过；静态 source check `173 files` 通过，均未检查项目 `.next`；用户未跟踪的 `next-env.d.ts` 未纳入 source check。字段名盘点确认 `frontend/lib/api/types.ts` 的 211 个属性名、`backend/app/api/schemas.py` 的 100 个公开 DTO 属性名均已出现在矩阵。后端最新完整确定性套件以 `env -i` 运行，`1332 passed / 128 skipped`；pytest 测试启动器在导入 `app.main` 前将未显式指定的 `Settings` 环境文件设为 `None`，生产设置仍保留根 `.env` 默认路径；哨兵 `.env` 防回归测试先红后绿，证明测试不继承环境文件。API/Chat 测试使用内存 `RealtimeBundle`，无需 Redis/PostgreSQL；resolution publisher、两条 FINAL 路径和公开 SSE 透传均有测试。Playwright 功能 `80 passed`、首页问答另 `4 passed`、P1 首页结果移动端重复 `5 passed`；视觉 `30 passed / 4 skipped`。Ruff lint 与 `git diff --check` 通过；两份旧 API 测试文件的 formatter 差异均在未改动行，未做整文件重排。P1 Match live/upcoming 截图视觉用例仍因浏览器后端需要 Redis 而未计入通过；P2 Replay 视觉 4 项仍跳过。未读取根 `.env`，未调用真实 provider/LLM/Polymarket；未运行项目 `.next` 或真实运行栈。
- **执行边界：** 当前 Goal 已授权修复可复现 bug 并查清字段；用户明确选择不初始化、继续用演示/fixture。仍不运行 `init`、真实 API/LLM/Polymarket，不读取或修改根 `.env`，不访问项目目录 `.next`，不启动/停止真实运行栈或容器。隔离临时目录中的假数据 E2E 服务按测试配置自动启停；不将 fixture 结果表述为线上验收。
- **保留的用户改动：** `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/app/service.py` 中原有的 freshness 两处改动、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts`。T98 在 `service.py` 的独立 phase 代码段做了最小修复，没有覆盖原 freshness 改动。

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
| 2026-09-26 | `cadc5d0` | T103 已由真实 API 锁定根因：抢七盘分 `6.7` / `7.9` 被纯数字解析器丢弃；结果接口与比赛详情均复现。开始拟定跨层最小修复，未改产品代码。 |
| 2026-09-26 | `a885a6a` | T102 球员详情页修复与回归测试提交；2026 赛季展示逐项标注来源的已收录单打赛果，官方可用统计继续优先显示。 |
| 2026-09-25 | `5c8e998` | T101 实现与三份总控收口已推送；工作区现有 P3 修改与未跟踪文件继续保留。 |
| 2026-09-25 | `2b6e217` | 完成 T101：共用读取过滤过期当前比赛，首页显示北京日期；后端非 integration 1334 passed、前端 485 passed、真实浏览器 6 passed，服务同步健康。 |
| 2026-09-25 | `105a487` | 关闭 T100 只读调查；只更新项目总控并推送，未动产品代码或用户已有改动。 |
| 2026-09-25 | `c81c222` | T100 确认首页过期比赛根因：过期目录行未退役、API 不按时间/观测时间过滤、freshness 默认值掩盖陈旧记录；真实服务保持运行，未改产品代码。 |
