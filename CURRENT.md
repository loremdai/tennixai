# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-12 16:43 CST

**当前任务：** T45 — 持久化球员目录、别名与排名快照

**任务状态：** `in_progress`

**当前执行者 / ADE：** Claude Code / Claude Code

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**最近完成任务提交：** `4e882b9`

**最后验证的产品提交：** `4e882b9`

**本次任务起始提交：** `fdd39b4`

**本次任务领取时间：** 2026-09-12 16:43 CST

**本次任务起始提交：** `44cd9d5`（v0 原型已入库；本执行者从该提交继续 T43 工程收口）

**本次任务领取时间：** 2026-09-12 15:38 CST（自 v0 显式交接）

**T30 完成提交：** `8c9e161`

**T31 完成提交：** `128518f`

**T32 起始提交：** `128518f`

**T32 领取时间：** 2026-09-10 00:50 CST

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- P1/T16 已于 2026-09-08 完成并推送：fake 模式全链路确定性地跑通；真实 LiveTennisAPI provider、真实 Qwen 单项与组合 chat、Next 同源代理浏览器门均通过。
- T17 已于 2026-09-08 完成并推送：upcoming 改用当前 `/matches?status=upcoming` canonical 映射，指定球员使用供应商过滤，Home 的 live/upcoming 支持单侧失败降级，429 保留重试提示；实现提交为 `69c8238`。
- T18 已于 2026-09-09 完成并推送：Home 与 Match 的问答 prose 统一使用安全 Markdown 渲染，粗体、无序列表和段落不再显示原始标记；实现提交为 `5572960`。
- T19 已于 2026-09-09 完成并推送：回答结束且结构化卡片不在视口内时，Home 会将结果区域滚动到粘性导航下方；尊重 reduced-motion，不改变卡片数据来源或原型视觉结构；实现提交为 `fdb0131`。
- T16 已确认的事实：真实 provider 可返回 50 场 live matches；完整 `data` SSE 仍保留全部 canonical matches；LLM 只接收最多 12 条摘要并有持久化的 45 秒总时限；真实 Djokovic 查询不再因重复实名/组合名报歧义，空赛程会诚实返回并以 `done` 结束。
- 最终验证：backend `pytest -m "not llm_live and not provider_live and not end_to_end_live"` 126 passed；frontend `pnpm test` 69/69、`pnpm typecheck`、`pnpm build` 通过；隔离 fake 服务下完整 Playwright `32 passed + 4 skipped`。
- T18 验证：前端 `pnpm test` 71/71、`pnpm typecheck`、`pnpm build` 通过；隔离服务下 P1 Playwright 10/10；真实浏览器回答区检测到 `strong=10`、`ul=1`、原始 `**` 不存在。
- 真实 key 验收：REST 全局 upcoming 返回 50 场；以 `Qinwen Zheng` 查询返回 Rybakina vs Zheng 的 US Open WTA 1/4 决赛；浏览器完成 Home → 结构化比赛卡片 → Match Page → 上下文问答，返回 2026-09-09 23:00 澳门时间。
- 视觉：prototype 10 张基线（home 4 张经 T13/T15 审阅更新，match 6 张自 T01 起零变化）+ p1.visual 12 张新基线（逐张审阅入库）。
- Final P1 Completion Gate 八条已人工核对（凭据仅服务端、无自动轮询、无超范围实现、结构化事实来源、供应商/LLM 失败降级、预览与生产路由分离、双视口视觉一致、泄漏检查业务代码零命中）；T16/T17 额外通过真实 provider、LLM、组合及浏览器门。
- 本地运行与 opt-in 真实门命令见 [docs/runbooks/p2-local.md](./docs/runbooks/p2-local.md)。
- P2（Live Match Intelligence）设计已逐项批准：API-Tennis REST/WebSocket、FastAPI + 独立 worker、PostgreSQL + Redis、snapshot + versioned SSE、Home facets、PBP/statistics、Recent Control、轻量 history/H2H 和 Replay 测试。
- P2 详细规格已写入 [P2 设计规格](./docs/superpowers/specs/2026-09-09-tennixai-p2-live-match-intelligence-design.md)，T21–T32 的逐任务文件、接口、TDD 步骤和验收命令见 [P2 实施计划](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md)。
- T21 已于 2026-09-09 完成并推送：P2 canonical domain（CircuitTier/Gender/Discipline/ConnectionStatus/CapabilityStatus、22 项 StatisticName、PointEvent/MatchStatistic/MomentumObservation/DataQuality/HeadToHead/MatchSnapshot/ProviderLiveEnvelope）、async `IdentityRepository` 与扩展后的查询/live-feed provider contracts；实现提交为 `5b479fc`。
- T21 已确认的事实：`MatchSnapshot` 强制与 `match.live_state.state_version` 一致（无 live_state 时版本必须为 0）；缺失能力用 `DataQuality` 声明而不是 0；备用 LiveTennis adapter 对 P2 独有能力返回 typed `unsupported`(501)；全套确定性 backend 150 passed/6 deselected，P1 验收矩阵 10/10 不回归。
- M01 已把本地配置统一迁移到根目录 `.env`；FastAPI、Next.js、Playwright 和真实测试均从该入口读取，Next 进程只接收 `TENNIX_BACKEND_URL`，不接收后端凭据。
- T22 已于 2026-09-09 完成并推送：`compose.yaml`（仅 postgres:16 + redis:7，127.0.0.1 绑定、named volumes、healthchecks、无供应商/LLM 凭据）、SQLAlchemy async + asyncpg + Alembic + redis + websockets 依赖、`infrastructure`/`api_tennis_live`/`realtime_live` markers、P2 core schema（13 张表，migration `0001`）、`Database`/`PostgresIdentityRepository`/`MatchSnapshotRepository`/`RawProviderEventRepository` 与 typed settings（retention 14 天、max_live_subscriptions 8、lease 45s、grace 60s）；实现提交为 `20dac5f`。
- T22 已确认的事实：`get_or_create` 在 20 路并发下收敛为同一内部 ID 且跨 repository 实例（模拟进程重启）稳定；`point_events(match_id, sequence)` 与 `point_event_revisions(point_event_id, revision)` 唯一约束拒绝重复；snapshot 每场只保留一行当前状态；`purge_raw_events(before)` 严格删除 `< before` 的 raw payload（边界值保留），canonical point 行不受影响；alembic downgrade base → upgrade head 往返 exit 0。
- 本地基础设施：colima 已于 18:12 启动；`tennix-postgres`/`tennix-redis` 容器 healthy（pg_isready 通过、redis PONG）。integration 测试在 PostgreSQL 不可达或 schema 未迁移时如实 skip。
- T23 已于 2026-09-09 完成并推送：`ApiTennisProvider` REST adapter（live/fixtures/search/player/match/snapshot/recent/H2H）、permissive vendor DTO、event 分类映射、provider mode `fake|live|livetennis|api_tennis`（api_tennis 用 `PostgresIdentityRepository`）、5 个脱敏 fixtures、40 项契约测试与真实 REST smoke；实现提交为 `015ff7f`。
- T23 已确认的事实：`get_players` 无名称搜索，`search_players` 在 livescore + 3 天 fixtures 窗口做有界扫描；upcoming 窗口 7 天且只保留 SCHEDULED；recent 30 天 + FINISHED + limit≤10；scheduled 且无真实比分不构造 live_state；PBP winner 由比分推进推导、不可判定→PARTIAL；`Last 10 balls` 与未知 stat 丢弃；错误翻译零 key/URL 泄漏；真实 smoke（Trial key）通过：get_events 认证、72 场 live canonical 映射、snapshot 版本一致。
- T24 已于 2026-09-09 完成并推送：catalog 筛选/排序/facet counts、昨天（Asia/Macau）/近期/H2H 服务方法（10min/60s TTL、PARTIAL/UNAVAILABLE 语义）、新 REST 路由 `GET /api/v1/matches/catalog`、`GET /api/v1/players/{id}/results`、`GET /api/v1/head-to-head`；P1 `/matches` 与 Chat 历史 guard 未动；实现提交为 `dddb734`。
- T24 已确认的事实：默认 facet=ATP+WTA/全部性别/单打，空组=全部；排序 tier→live→开赛时间→id；facet counts 尊重另外两组且保留 0 值；Featured=排序后首项；recent fetch 满 10 条→PARTIAL；unsupported→UNAVAILABLE 且 matches 为空；全套确定性 backend 241 passed/7 deselected。
- T25 已于 2026-09-09 完成并推送：Home 叠加筛选（chip 组 + 计数 + 零计数禁用 + 恢复默认）、catalog 消费（`/api/matches/catalog` Next 代理）、Featured 取 `featured_match_id`、双视口 e2e；实现提交为 `e904485`。
- T25 已确认的事实：前端筛选语义与后端一致（空组=全部、默认 ATP+WTA/全部性别/单打）；facet counts 为 live+upcoming 合并；筛选为空只显空态、不放宽；P1 failure 注入 glob 已修正为 `**/api/matches**`；视觉 spec 已加滚动稳定化；4 张 Home 基线经审阅有意更新，match 页零变化。
- T26 已于 2026-09-09 完成并推送：canonical live reducer（去重/append/correction/尾段重建/版本语义）与事务化 `save_reduction`（migration `0002` 增 quality 列）；实现提交为 `98a1a22`。
- T26 已确认的事实：相同 supplier snapshot 不进版本不发事件；纠错 revision+1 且 `recompute_from_sequence` 指向变化序列；删除尾段自首个差异重建连续序列；仅 freshness 差异不算状态变化；重复保存幂等、失败回滚旧版本可读；全套确定性 256 passed/7 deselected。
- T27 已于 2026-09-09 完成并推送：WS feed adapter（batch 帧 + 客户端过滤）、Redis leases（TTL/grace/arrival-order）、publisher（hot snapshot + pub/sub）、realtime worker（REST 先行/断线 reconcile/terminal 即关/capacity/retention）；实现提交为 `d354aba`。
- T27 已确认的事实：vendor WS 每帧为约 10 场全量对象数组，需客户端按 `event_key` 过滤；断线前积压帧在 reconnect 时丢弃；lease 同刻 acquire 的容量优先用 1e-6 arrival stamp 保证确定序；全套确定性 276 passed/8 deselected，真实 WS/REST smoke 各 1 passed。
- T28 已于 2026-09-09 完成并推送：snapshot REST（hot→PG→provider 回存）、版本化 SSE（ready/delta/ended/heartbeat、lease 生命周期）、Next 代理与 `useMatchStream`；实现提交为 `f03985b`。
- T28 已确认的事实：SSE 每版本仅一帧且 id=state_version；gap 只转发不造事件；隐藏 60s abort 释放 lease；httpx ASGITransport 缓冲响应，SSE 测试须用进程内 uvicorn；全套确定性 286 passed/8 deselected、infrastructure 12、frontend 106、e2e 40/4 skipped 且视觉零变化。
- T29 已于 2026-09-09 完成并推送：生产 Match 页渲染 canonical snapshot 的 22 项技术统计（分组/单位/partial/缺失不猜测）与 Set→Game→Point 时间线（关键分徽章、纠错提示、近底自动跟随）；实现提交为 `ecd916b`。
- T29 已确认的事实：preview 原型与卡片顺序零变化；fake 模式统计/逐分为空时显示诚实缺失文案；`p1-match-live` 生产视觉基线经审阅有意重生成（desktop+mobile）；另以 `6c1b448` 修复 T27 提交遗漏的 `api_tennis.py`/`realtime/models.py`（HEAD 曾无法 import live feed）。
- T31 已于 2026-09-10 完成并推送：compact intelligence packet、三项 P2 Chat 工具、有限历史/H2H 能力路由和不可变 `answer_context`；实现提交为 `128518f`。
- T31 验证事实：focused backend 56 passed；全确定性 backend 322 passed/11 deselected；frontend 127 passed、typecheck/build；完整 Playwright 40 passed/4 skipped；真实 LLM opt-in 运行结果为 7 failed，根因是 endpoint 对配置模型返回 403 `AccessDenied.Unpurchased`，不能作为通过证据。
- T32 已完成并推送产品提交 `ac9c6e5`；P2 已关闭。本次用户明确提出的 UX 修复已在 `525d701` 完成：仅隐藏计数为 0 且未激活的 `unknown` facet，不改变 canonical `unknown` 数据语义。
- T36 已完成并推送产品提交 `28b316d`：Match Chat SSE 暴露 resolving/planning/fetching_data/generating 阶段，Home 与 Match 详情页显示阶段文案，完成/失败/取消时清理进度状态；真实 SSE 和真实浏览器流程均已复核。
- T33 已完成并推送产品提交 `b60217e`：按 [API-Tennis REST 文档](https://api-tennis.com/documentation) 与 [WebSocket 文档](https://api-tennis.com/documentation_websocket) 修复 livescore 终态过滤、`event_live` 状态映射、默认筛选下直播发现、统计多周期 key、实时推送覆盖球员全名、重复 PBP identity 和 PostgreSQL 重排冲突；官方未返回的场地/室内外/赛制/ISO 国家代码继续显示诚实缺失。
- T38 已完成产品提交 `ddaf24b`：保留 API-Tennis `World` 为 canonical `world`；目录接口复用详情档案补齐国家与排名；首页比赛卡显示国旗，详情页显示国旗+ISO 代码，`world` 使用 Globe 图标，缺失/未知值不请求国旗资源；真实浏览器 Home→Match→Home 鼠标流程已复核。
- T39 已完成并提交 `61d8fee`：作用域感知工具目录、多工具并行/依赖串行、非法调用重规划、部分失败降级、冻结事实综合分析与可见进度均已落地；真实 Qwen 全局查询不再误调用 match-only 工具。
- T39 质量修复：综合分析强制覆盖 overview/statistics/points/momentum；统计值向模型按球员姓名标注；未知 `format` 的正文先完整校验，违规时自动重写，仍违规则保守降级，避免把 `BO3` 等未经事实支持的赛制泄漏给用户。
- Markdown 已升级为 CommonMark + GFM：表格、任务列表、删除线、脚注、自动链接、标题、引用、代码块等由共享 `MarkdownAnswer` 渲染；原始 HTML 保持关闭。
- T40 已完成并提交 `17ccdb7`：修复真实服务未知赛制回答的二次生成失败路径，保留结构化数据并以 `done` 正常结束；用户正文移除原问题回显、内部 `format`/工具/质量校验话术和“重要说明”模板，赛制缺口改为独立的友好资料提示；补齐 CommonMark + GFM 语义回归与浏览器断言。
- 已知非 T17 限制：LiveTennisAPI 的 `/players?search` 当前不能把中文显示名“郑钦文”直接映射到 `Qinwen Zheng`；canonical English name 查询已通过，中文别名/名称归一化需另立任务批准。
- T42 已于 2026-09-12 完成并推送（`c8c7c24`）：[球员目录设计规格](./docs/superpowers/specs/2026-09-12-tennixai-player-directory-multilingual-identity-design.md) 明确 Top 200 排名、全目录双语搜索、profile、五赛季历史、离线中文名和共享 resolver。
- T42A 已于 2026-09-12 完成并推送（`60543ea`）：[P2.6 实施计划](./docs/superpowers/plans/2026-09-12-tennixai-player-directory-multilingual-identity-implementation.md) 已重排为 T43 v0 原型 → T44–T50 后端/数据/Chat → T51 真实前端集成 → T52 总门。
- v0 交付入口已准备：[球员页面 v0 Prompt](./docs/v0/2026-09-12-player-pages-prompt.md)；T43 必须先取得用户确认的 v0 输出并冻结双视口视觉基线，后端 T44 才可开始；ADE 不得自行重设计。
- P2.6 当前代码事实仍是：API-Tennis `search_players` 扫 live + 3 天 fixtures 并字符串匹配，`Ben Shelton` 对 `B. Shelton` 会 `not_found`；修复尚未实施，T48/T50 负责关闭。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`、`REALTIME_LATENCY_INVESTIGATION.md`（任务外调查文档）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`、`frontend/next-env.d.ts`；保留原样，不纳入 T42A。

## 当前任务

### T45 — 持久化球员目录、别名与排名快照

- **状态：** `in_progress`
- **执行者 / ADE：** Claude Code / Claude Code
- **分支：** `main`
- **起始提交：** `fdd39b4`
- **领取时间：** 2026-09-12 16:43 CST
- **范围：** 按 [P2.6 实施计划 T45](./docs/superpowers/plans/2026-09-12-tennixai-player-directory-multilingual-identity-implementation.md#t45-persist-the-player-directory-aliases-and-ranking-snapshots)：migration `0003`（players 扩列 + `player_aliases` + `player_rankings`，不替换 identity 表）、`PlayerDirectoryRepository` protocol 与 `MemoryPlayerDirectoryRepository`、`PostgresPlayerDirectoryRepository`、`MatchSnapshotRepository.player_or_placeholder` 双名映射、integration 门与 alembic 往返。
- **验收门：** schema 约束、alias 重复幂等、同 alias 多球员、最新排名快照选择、国家筛选、50 行分页、并发 external-ID 收敛、`localized_name` 快照重建；alembic upgrade→downgrade 0002→upgrade 往返 exit 0 且旧行无损；全套确定性 backend 不回归。
- **阻塞：** 无。

### T44 — 增加 canonical 排名模型与 API-Tennis standings adapter

- **状态：** `done`
- **执行者 / ADE：** Claude Code / Claude Code
- **分支：** `main`
- **起始提交：** `91b180c`（领取记录 `974c523`）
- **领取时间：** 2026-09-12 16:23 CST
- **完成提交：** `4e882b9`
- **完成事实：** 新增 `backend/app/players/`（`Tour`/`RankingMovement`/`RankingEntry`/`PlayerCatalogProvider`）；`Player` 兼容增加可选 `localized_name`；permissive `StandingDto`（容忍未知字段、仅文档化 wire 字段）；`ApiTennisProvider.get_rankings()` 调 `get_standings(event_type=ATP|WTA)`，跳过缺 key/name/rank/points 的坏行，movement 读不懂时回退 UNKNOWN，国家名走既有 `country_code_from_name`，内部 ID 经 identity repository，按 `(rank, player.id)` 排序，`fetched_at` tz-aware；fake provider 确定性 7 条排名（跨 ATP/WTA、中国、up/down/same、rank 200 边界与 201 外），复用 fake 球员内部 ID；未把 standings 加入 `TennisDataProvider`。
- **验证门：** TDD 先红（`ModuleNotFoundError: app.players`）后绿；focused `tests/test_domain.py tests/test_player_ranking_provider.py tests/test_provider_contract.py tests/test_api_tennis_provider.py` 75 passed；全确定性 backend 382 passed/14 deselected；opt-in 真实门 `TENNIX_RUN_API_TENNIS_LIVE=1 uv run pytest -m api_tennis_live tests/live/test_api_tennis_live.py -q` 2 passed（两 tour 认证、canonical 排序映射、`player_key`/key 零泄漏；403/429 为如实失败路径）。
- **阻塞：** 无。

### T43 — 生成、导入并冻结 v0 球员页面视觉真相

- **状态：** `done`
- **执行者 / ADE：** Claude Code / Claude Code（自 v0 显式交接）
- **分支：** `main`
- **起始提交：** `44cd9d5`（领取记录 `cd45108`）
- **领取时间：** 2026-09-12 15:38 CST
- **完成提交：** `42c7a36`
- **完成事实：** v0 已接受视觉方向保持不变，仅按 T43 计划补齐工程收口：①有 q 时搜索完整本地单打目录、不受 ATP/WTA tab 限制（默认 ATP 页输入“郑钦文”命中 Qinwen Zheng）；②无当前排名固定文案“暂无当前排名”（搜索结果行、资料头排名块、快捷示例）；③live/next/历史赛果均链 `/matches/{internalMatchId}`；④赛季摘要改为硬地/红土/草地胜负记录（缺失为 unavailable，不以 0–0 冒充）；⑤2026 赛季 Finished 样例最晚 2026-09-10，不晚于快照 2026-09-11；⑥新增 `players-page.test.tsx`、`player-profile-page.test.tsx`（合计 28 项）与 `e2e/player-directory.visual.spec.ts`，冻结并逐张审阅 1440×1000/390×844 四张基线（players-directory、players-profile 各双视口），规格内含横向溢出守卫断言。
- **验证门：** TDD 先红后绿（定向 10 项失败→28/28 通过）；`pnpm test` 179 passed、`pnpm typecheck` 通过、`pnpm build` exit 0；`pnpm test:e2e:update --grep "player directory visual"` 4 passed 后 plain 复跑 4 passed；回归 `pnpm test:e2e --grep "player directory visual|prototype|visual"` 16 passed/4 skipped/10 failed，10 项失败全部为 prototype.visual 且与父提交 `44cd9d5` 干净 worktree 复跑的失败集完全相同（基线漂移：期望 1440×2216 vs 实际 2182，约 34px 垂直偏移），属任务前旧债，未重录 Home/Match 基线；p1-home-result mobile 单次抖动单独与整轮复跑均通过（T29 起已知移动端抖动）。
- **阻塞：** 无。

### T42A — 修正 P2.6 为原型优先实施顺序

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `89bc04c`
- **领取时间：** 2026-09-12 14:14 CST
- **范围：** 纠正 T42 计划中把 v0 原型排在后端之后的顺序错误；将球员目录与详情页的 v0 生成、导入和视觉冻结提升为 T43，后端/数据/Chat 任务顺延，真实前端集成仍等待视觉和 API 契约完成。只改规格、计划与总控，不改产品代码或已批准功能。
- **验收门：** `ROADMAP.md`、`CURRENT.md`、设计规格和实施计划必须一致表达“先原型、后实现”；T43 是唯一 next-ready；T44–T52 的编号、前置依赖和交叉引用无旧顺序残留；链接、敏感模式和 `git diff --check` 通过。
- **完成提交：** `60543ea`
- **完成事实：** 规格发布顺序、任务拆分、实施计划和三份总控均改为原型优先；v0 生成/导入/视觉冻结成为 T43，canonical ranking 从 T44 开始，真实页面集成为 T51；未修改产品代码或已批准功能。
- **验证门：** 实施计划任务标题严格为 T43–T52 且各出现一次；ROADMAP 任务行严格为 T43–T52 且依赖顺序一致；旧 T50 v0、T50 视觉基线、T48 DTO 等引用零残留；三个本地入口文件存在；新增差异未命中占位符、64 位十六进制、`sk-` 或凭据赋值模式；`git diff --check` 通过。
- **阻塞：** 无。

### T42 — 冻结球员目录、多语言身份与历史赛果设计

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `ee71605`
- **领取时间：** 2026-09-12 13:29 CST
- **范围：** 将已批准的 `/players` Top 200 排名页、球员详情页、历史赛果、多语言球员主数据、离线中文别名生成、确定性 PlayerResolver、Home/Match Chat 共用解析与 v0 交付边界写成唯一设计规格和可执行实施计划；同步 `PROJECT.md`、`ROADMAP.md`、`CURRENT.md`。本任务不实现产品代码、不引入运行时翻译 LLM、RAG、向量库、双打或 Player Chat。
- **执行方式：** 先基于最新代码与 API-Tennis 已验证能力固化领域模型、数据流、API/Chat/UI 契约、迁移和回滚边界；规格自审通过后，按用户免审授权直接编写逐任务 TDD 实施计划和 v0 交付要求，再完成三份总控的一致性更新。
- **验收门：** 规格与计划不得包含未决产品选择或占位项；每个实施任务必须写清文件、接口、测试、真实门和提交边界；总控必须只有 T42 一个 `in_progress`；所有链接可解析；文档泄漏扫描与 `git diff --check` 通过；既有未跟踪文件保持不变。
- **完成提交：** `c8c7c24`
- **完成事实：** 已写入 740 行设计规格、1317 行 T43–T52 逐任务实施计划和 222 行可直接交给 v0 的两页设计 Prompt；三份总控已同步 P2.6 长期边界和 v0 外部输入门；原任务编号顺序已由 T42A 纠正，本任务未修改产品代码。
- **验证门：** 规格/计划占位符扫描零命中；类型与接口自审补齐整批中文名原子写入、fake 内存目录和 8 份/巡回赛排名快照上限；8 个本地文档链接均存在；ROADMAP 任务表当时仅 T42 一个 `in_progress`；新增文档未命中 64 位十六进制、`sk-` 或凭据赋值模式；`git diff --check` 通过；已知未跟踪文件保持不变。
- **阻塞：** 无。

### T41 — 同步首页问答用户展示策略

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `096dce9`
- **领取时间：** 2026-09-12 12:08 CST
- **范围：** 将 T40 已验证的用户可见回答策略同步到 Home 生产问答卡：去除内部实现提示、统一用户可见状态话术、保留结构化比赛卡与资料缺失提示；不扩大 Home 的工具能力，不改变预览原型。
- **执行方式：** 先为 Home 补充完整流式回答的失败回归测试，再做最小前端展示层修复；随后运行前端单测、类型检查、构建、隔离服务 Playwright，并用真实浏览器等待首页回答完整结束后检查内容质量。
- **验收门：** Home 回答必须收到 `done` 后才判定通过；原问题、内部上下文/工具/字段说明和实现来源 footer 不得出现在生产回答卡；结构化比赛卡、友好 warning、失败重试和进度文案保持可用；预览内容不变；已知未跟踪文件保持不变。
- **完成提交：** `5c3d469`
- **完成事实：** Home 生产回答卡已移除结构化数据来源 footer；Home 与 Match 详情页共享用户可见回答标签；结构化比赛卡、资料缺失提示、失败重试和流式进度保持可用；预览内容未改。
- **验证门：** 前端 `pnpm test` 151 passed；`pnpm typecheck`、`pnpm build` 通过；隔离 fake Home 流程 desktop/mobile 2 passed、P1 视觉 12 passed；真实浏览器重启服务后等待首页回答至完成，`progress=0`、`internalFooter=0`、`quotedQuestion=0`、`availabilityNotice=1`、`structuredCards=10`；完整 `pnpm test:e2e` 为 28 passed/14 skipped/14 failed，失败集中于既有 P2 默认 `gender=*` 断言不一致和过期 prototype 视觉基线，未归因于 T41；backend 未改动；已知未跟踪文件保持不变；服务 health 与首页 HTTP 均为 200；`git diff --check` 通过。
- **阻塞：** 无。

### T40 — 修复真实服务回答未完成并完善 Markdown 渲染验收

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `29a2bf1`
- **领取时间：** 2026-09-12 11:02 CST
- **范围：** 修复真实比赛详情页在未知赛制回答触发二次模型生成失败后被错误标记为“查询未完成”的问题；保证已有结构化数据时模型生成失败也能安全完成；补齐 CommonMark + GFM 渲染的剩余语义/布局回归验证；不扩大 P2 能力边界。
- **执行方式：** 先用确定性测试复现“未知赛制违规回答/修复失败/流式生成异常”并确认失败，再做最小后端降级与 Markdown 渲染补丁；完成后运行确定性后端、前端、构建、隔离 Playwright、真实 LLM 和真实浏览器鼠标流程，必须等待完整回答并检查内容质量。
- **验收门：** 真实未知赛制综合问题不出现终止 `error`/“查询未完成”，最终必须有 `done`、可读正文、结构化数据和明确不可用说明；重试有界，不能因质量门拖垮请求；Markdown 表格、脚注、自动链接、任务列表、删除线、标题、引用和代码块按语义元素渲染；未跟踪用户文件保持不变。
- **完成提交：** `17ccdb7`
- **完成事实：** 真实比赛详情页提交复杂综合问题后，完整等待至生成结束；正文显示自然的比赛结论和逐盘分析，不显示原问题、`format`、工具过程、质量校验或“重要说明”；赛制信息单独显示为“赛制信息暂缺，以下分析未对具体盘数结构作判断”。模型输出含 Markdown 表格时页面使用语义 `<table>`，原始 HTML 仍关闭。
- **验证门：** backend 确定性 `374 passed, 2 skipped, 11 deselected`；真实 Qwen `9 passed`；frontend `149 passed`、`pnpm typecheck`、`pnpm build`；隔离 fake Playwright `12 passed, 6 skipped`；真实浏览器复杂分析完整完成、无 `查询失败`/`查询未完成`、错误/警告日志为空；服务已重启，health 200、首页 200；`git diff --check` 通过；原有未跟踪文件保持不变。

### T39 — 设计并实现作用域感知的多工具对话编排

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `fcfcc55`
- **领取时间：** 2026-09-12 08:25 CST
- **当前节点：** 已完成实现、质量修复和真实浏览器复验；完成提交为 `61d8fee`。
- **范围：** 依据已批准的多工具编排设计，修复 global scope 暴露 match-only 工具的问题；建立工具能力/作用域/阶段/依赖声明；支持无依赖工具并行调用、有依赖工具串行调用、有限重规划、部分失败降级和真实 Qwen `parallel_tool_calls`；保持 match snapshot `state_version/as_of`、结构化数据优先、前端流式进度和 P2 能力边界。
- **执行方式：** 先写 scope、并行批次、依赖顺序、非法调用和降级场景的失败测试，再按最小责任层实现；综合问题补齐四类比赛上下文，最终正文增加事实质量门；Markdown 渲染补齐 CommonMark + GFM；随后运行 backend/frontend 全量、typecheck/build、隔离 fake Playwright、真实 Qwen 和真实浏览器矩阵。
- **验收门：** `tiafoe 的比赛如何了` 不再出现卡片成功后 `invalid_request`；global 不可调用 `get_match_intelligence`；一轮多个独立 tool call 全部执行且并行；依赖调用严格串行；可选工具失败不终止核心回答；非法工具自动重规划或给出明确降级；复杂 match 问题覆盖 overview/statistics/points/momentum；完整回答无空结果、未知赛制臆测和统计错位；真实 SSE 阶段和浏览器 UI 可见；Markdown 表格等 GFM 结构按语义元素渲染；无凭据/供应商原始字段泄漏，未跟踪用户文件保持不变。
- **完成提交：** `61d8fee`
- **验证门：** backend 确定性 `373 passed, 2 skipped, 11 deselected`；真实 Qwen `9 passed, 377 deselected`；frontend `147 passed`、`pnpm exec tsc --noEmit`、`pnpm build`；隔离 fake Playwright `12 passed, 6 skipped`；真实 LLM 浏览器桌面/移动 `6 passed`；质量回归覆盖首次违规重写和二次违规保守降级；`git diff --check` 通过。

### T38 — 保留 World 国家代码并适配球员国旗展示

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `b592c4d`
- **领取时间：** 2026-09-11 15:39 CST
- **范围：** 按用户提供的原型截图，API-Tennis `player_country=World` 映射为 canonical `world`；建立统一的国家代码→国旗、中文国名和可访问名称映射；首页比赛卡展示国旗，比赛详情页展示国旗与国家代码，保持原型布局密度；补充 provider、view-model、组件、双视口视觉和真实浏览器回归。
- **执行方式：** 先写并运行失败的 `World` 映射、旗帜/国家展示和组件回归测试，再做最小共享适配；完成后运行后端、前端、typecheck/build、P1 Playwright 与真实服务鼠标流程。
- **验收门：** `World` 不再变成缺失值；俄罗斯/白俄罗斯等明确国家仍显示各自国旗与代码；首页所有比赛卡可显示国旗；详情页与原型一致显示国旗+代码；未知/缺失值不请求不存在的国旗资源；未跟踪用户文件保持不变。
- **完成提交：** `ddaf24b`
- **完成事实：** API-Tennis 的明确 `World` affiliation 保留为 canonical `world`，俄罗斯/白俄罗斯仍映射为各自代码；catalog 对筛选后的比赛复用短 TTL player profile cache，补齐首页此前缺失的国家代码与排名；共享 `PlayerViewModel` 提供国家名称、代码和旗帜 URL；首页仅显示国旗，详情页显示国旗+ISO 代码，`world` 显示 Globe/WORLD，缺失/未知值不发起不存在的旗帜请求。
- **验证门：** provider/service/view-model/component 测试均按 TDD 先红后绿；backend 确定性 `352 passed, 2 skipped, 9 deselected`；frontend `140 passed`、`pnpm typecheck`、`pnpm build`；隔离 fake 服务 P1 功能 `12 passed`、视觉 `12 passed`；真实 API-Tennis REST smoke `1 passed`；真实 catalog/detail 国家数据一致；真实浏览器鼠标 Home→Match→Home 确认德国国旗+`DEU`、World Globe+`WORLD`，error/warn 为空；`git diff --check` 通过。
- **阻塞：** 无。

### T37 — 适配可获得比赛元数据并解释不可用字段

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `d776443`
- **领取时间：** 2026-09-11 15:04 CST
- **范围：** 依据 API-Tennis 官方 REST 文档，补齐比赛详情可通过 `get_draw` 获得的赛事场地与可安全映射的球员国家代码；为官方响应明确为空或语义不足的室内外、赛制、赛前比分/PBP/统计/走势等字段提供准确说明，补充后端映射、前端展示和真实数据回归测试。
- **执行方式：** 先写并运行失败的 provider/view-model 回归测试，再做最小适配；完成后运行后端、前端、构建、真实 API smoke，并用真实浏览器鼠标复核目标比赛详情页。
- **验收门：** 目标比赛详情页不再把 API-Tennis `get_draw` 已提供的硬地信息显示为缺失；可映射的球员国家代码可见；仍无官方值的字段显示“官方未返回/赛前待产生”等解释，不伪造值；未跟踪用户文件保持不变。
- **完成提交：** `54059fe`
- **完成事实：** 详情快照按官方 `get_draw` 响应补齐并规范化 `hard/clay/grass` 场地；`get_players` 的明确国家名称安全映射为 ISO alpha-3（例如 Germany→`deu`），`World` 等非国家标记不猜测；缺失元数据采用短 TTL 缓存并持久化，避免重复消耗供应商配额；reducer 对元数据变化发出版本化事件；前端将轮次、场地、室内外、赛制、开赛时间、国家代码、比分、逐分、统计和动量的缺失分别解释，不再显示裸“暂未提供”。
- **验证门：** TDD focused provider/service/reducer `91 passed`；backend 确定性 `349 passed, 2 skipped, 9 deselected`；frontend `136 passed`、`pnpm typecheck`、`pnpm build`；隔离 fake 服务 P1 Playwright 功能+视觉 `24 passed`；真实 API-Tennis REST smoke `1 passed`；真实服务 health 200、目标 Match API 200；真实浏览器鼠标进入并刷新目标页后显示硬地、`DEU/#2`、`#142`，室内外/赛制/逐分/统计/动量缺失解释正确，浏览器 error/warn 为空。一次误触全套 Playwright 时发现 4 个范围外 P2 Home filter 请求断言失败，未作为 T37 通过证据，也未改动其代码。
- **阻塞：** 无。

### T36 — 暴露 Match Chat 流式进度阶段

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `d6b33b6`
- **领取时间：** 2026-09-11 11:35 CST
- **完成提交：** `28b316d`
- **范围：** 将 Chat SSE 已有的阶段事件转成前端可见的进度文案，并保留现有结构化数据优先、回答流式输出、快照冻结和取消语义；补充前后端回归测试与真实浏览器验证。
- **执行方式：** 先写并运行失败的阶段事件/前端渲染测试，再用最小补丁实现，最后运行受影响测试和真实服务鼠标流程。
- **完成事实：** 后端在快照锁定、工具取数、再次规划和最终生成前发出阶段事件；前端统一映射为“锁定比赛快照/拆解问题/读取比赛数据/组织回答”，并兼容旧事件流，在 done/error/cancel 时清理阶段。
- **验证门：** TDD focused 用例先红后绿；backend `env -u NO_PROXY -u no_proxy uv run pytest -q` 为 `355 passed, 2 skipped`；frontend `pnpm test` 为 `135 passed`、`pnpm typecheck`、`pnpm build` 通过；隔离假服务关键 Playwright `4 passed`；真实 SSE 顺序为 resolving→planning→fetching_data→data→planning→generating→text_delta→done，真实浏览器已看到“正在拆解问题…”和“正在组织回答…”；最终真实 backend health 200、Match Page HTTP 200。
- **阻塞：** 无。

### T34 — 修复详情页实时 worker 因 PBP 主键冲突退出

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `d16dbfe`
- **领取时间：** 2026-09-11 10:28 CST
- **完成提交：** `84eb146`
- **范围：** 修复 API-Tennis 实时快照在供应商 PBP 重排/修正后生成重复 `point_events.id`，导致 PostgreSQL `save_reduction` 唯一约束异常并使后台 realtime worker 静默退出；保持详情页 REST/SSE、Home 数据和官方缺失字段语义不变。
- **完成事实：** 根因是供应商按当前 PBP 位置编号，插入/修正后旧 canonical point 移到新序号却继续携带旧主键；reducer 现在在新序号上为冲突点生成确定性、唯一的内部 ID，并保留安全的供应商 ID。新增单元与 PostgreSQL integration 回归覆盖新点复用旧 ID、已存尾部点移到新序号两种形态；真实比赛演算 96→152 个逐分、序号连续且无重复 ID，worker 重启后持续推进至 state version 16 / 158 个逐分。
- **验证门：** TDD focused 用例先红后绿；backend `env -u NO_PROXY -u no_proxy uv run pytest -m 'not llm_live and not provider_live and not end_to_end_live' -q` 实际为 341 passed、2 skipped、9 deselected；frontend `pnpm test -- --runInBand` 为 130 passed，`pnpm typecheck` 通过；改动文件 lint、`git diff --check` 通过；`GET /api/v1/health` 返回 200。真实浏览器按 Home→打开 Gauff 对阵 Rybakina→Match Page 流程复核，首页与详情均为 10:40、第三盘 1–2、当前局 30–0，详情页时间戳持续前进且后端日志无 worker 异常。实现依据 [API-Tennis REST 文档](https://api-tennis.com/documentation) 与 [WebSocket 文档](https://api-tennis.com/documentation_websocket)。
- **阻塞：** 无。

### T35 — 修复 Match Chat 查询时快照冻结与可选球员数据降级

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `6ab89c5`
- **领取时间：** 2026-09-11 10:55 CST
- **完成提交：** `054062b`
- **范围：** 真实比赛详情页的 Match Chat 在提问时固定一份 canonical snapshot，后续工具调用全部基于同一版本；当前比赛的综合分析在可选球员背景或历史能力缺失时继续回答，并将缺失字段如实标注；前端将回答期间的实时更新展示为快照时间说明，不再要求用户重新提问或把已有回答标记为失败。
- **完成事实：** backend 在一次请求开始冻结 `MatchSnapshot`，所有 Match Chat 主题工具复用同一 `state_version/as_of`；当前比赛默认只开放 `get_match_intelligence`，明确询问近期/交手时才开放有限历史工具；可选球员查询的 `not_found/unsupported` 作为不可用事实回传，不再中止已有分析；最终 Qwen 流式回答按阿里云兼容 Chat Completions 文档携带工具目录并关闭思考模式，避免历史 tool message 被误判为新工具调用。
- **验收门：** TDD 回归先红后绿；确定性 backend `354 passed, 2 skipped`；真实 LLM `tests/live/test_llm_live.py` `7 passed`；frontend `130 passed`、`pnpm typecheck` 通过、`git diff --check` 通过；真实服务健康且真实浏览器复杂分析问题返回完整正文，无 `查询失败`、`not_found` 或“请重新提问”，完赛后重新提问也保留正文。实现依据 [阿里云 Function Calling 文档](https://help.aliyun.com/en/model-studio/qwen-function-calling) 与 [OpenAI 兼容 Chat Completions 文档](https://help.aliyun.com/en/model-studio/qwen-api-via-openai-chat-completions)。
- **阻塞：** 无。

### P2 post-close real-data hardening — 修复直播发现、终态混入和统计周期渲染

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `626feab`
- **领取时间：** 2026-09-10 10:42 CST
- **范围：** 按已完成的真实浏览器排查结果，修复 API-Tennis livescore 将终态比赛混入直播、默认筛选下真实直播不可发现、统计多周期使用重复 React key，以及由此产生的“数据暂未提供”误判；不填充供应商明确未返回的场地、室内外、赛制或国家代码。
- **执行方式：** 相关回归测试先红后绿；修复后重新运行后端/前端门，并用真实浏览器从 Home 筛选到 Match Page 复核。
- **完成提交：** `b60217e`
- **完成事实：** worker 在 REST 初始/重连时用官方 `get_players` profile 补全可用姓名/排名，后续 WebSocket 缩写不会覆盖；重建两个本地陈旧 derived snapshot 后，真实直播持续更新无唯一约束错误，PBP identity 与 sequence 均唯一；实时详情持续 5 秒仍显示完整姓名，统计富集比赛的“全场/第 N 盘”标签无重复 key，最新前端错误/警告为空。
- **验证门：** backend `env -u NO_PROXY -u no_proxy uv run pytest -m 'not llm_live and not provider_live and not end_to_end_live' -q` 实际为 337 passed、2 skipped、9 deselected；`env -u NO_PROXY -u no_proxy uv run pytest -m infrastructure -q` 为 14 passed；frontend `pnpm test` 为 130 passed、`pnpm typecheck`、`pnpm build` 通过；真实 `TENNIX_RUN_API_TENNIS_LIVE=1 env -u NO_PROXY -u no_proxy uv run pytest -m api_tennis_live tests/live/test_api_tennis_live.py -q` 为 1 passed；真实浏览器完成 Home 默认筛选→显示全部直播→打开 Roddick/Tanuma→Match Page，并复核统计详情。
- **阻塞：** 无。

### P2 post-close UX patch — 隐藏无数据的“未知”筛选项

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `5c504b7`（领取记录 `932ceb0`）
- **完成提交：** `525d701`
- **完成事实：** Home 筛选栏仅在 `unknown` 计数为 0 且未激活时隐藏；若存在真实未知数据，仍保留该筛选项；其他 0 计数 facet 行为不变；新增组件回归测试。
- **验证门：** TDD focused 用例先红后绿；frontend `pnpm test` 128 passed；`pnpm typecheck` 通过；本地浏览器数据加载后的真实页面复核通过；`git diff --check` 通过。
- **阻塞：** 无。

### T32 — Add Replay E2E, Fault Recovery, Runbook, and Final P2 Gate

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `128518f`
- **领取时间：** 2026-09-10 00:50 CST
- **完成提交：** `ac9c6e5`
- **前置完成：** T31 已以 `128518f` 完成并通过确定性验证；本次领取从该产品提交开始，未创建分支。
- **范围：** 按 [P2 实施计划 T32](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t32-add-replay-e2e-fault-recovery-runbook-and-final-p2-gate)：deterministic replay、重启/纠错/断线恢复、双视口功能/视觉验收、真实 smoke、runbook 与 Final P2 Gate；不引入预测、odds、market 或交易能力。
- **完成事实：** Replay 仅替换上游 provider，仍经 PostgreSQL identity、reducer、Redis、FastAPI SSE 和 Next.js 页面；fixture 覆盖首帧、逐分、重复、统计、纠错、断线、REST reconcile 与完赛。focused replay/recovery 3 passed；确定性 backend 325 passed/11 deselected；infrastructure 13 passed/323 deselected；frontend 127 passed、typecheck/build；默认 Playwright 40 passed/10 skipped；Replay 功能 2 passed、视觉 4 passed（1440×1000 与 390×844），四张 PNG 已逐张审阅；真实 API-Tennis REST 1 passed、WebSocket 1 passed；真实浏览器业务流程手动核对至完赛，无需刷新。
- **外部验证：** 真实 LLM opt-in 7 failed，endpoint 返回 403 `AccessDenied.Unpurchased`，因此未计作通过；runbook 保留 entitlement 恢复后的重跑命令，不打印凭据或真实响应。
- **阻塞：** 产品与确定性/基础设施/Replay/REST/WS 门无阻塞；真实 LLM 仅有外部 entitlement 缺口。

### T31 — Add P2 Intelligence Tools and Versioned Chat Answers

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `8c9e161`
- **领取时间：** 2026-09-10 00:25 CST
- **完成提交：** `128518f`
- **范围：** 按 [P2 实施计划 T31](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t31-add-p2-intelligence-tools-and-versioned-chat-answers)：compact fact packet、history/H2H/tools、版本化上下文 Chat；不引入预测、odds、market 或交易能力。
- **完成事实：** Match Chat 按 topic 返回 compact canonical packet，最多 20 条近期 determinate points、20 条 momentum、20 条 key points，并保留 statistics/quality 的 partial/unavailable；LLM 不接收 vendor provider/raw/fingerprint 字段。新增有限昨天/近期赛果、H2H 和 broad-history typed unsupported 路由；Match scope 使用页面 context，首个结构化数据事件写入 `answer_context`，前端在 live 版本更新时只显示“比赛已更新”而不改写旧 prose 或自动重问。
- **验证门：** TDD focused backend 56 passed；全确定性 backend 322 passed/11 deselected；frontend 127 passed、typecheck/build；完整 Playwright 40 passed/4 skipped；`git diff --check` 通过。真实 opt-in `TENNIX_RUN_LLM_LIVE=1 env -u NO_PROXY -u no_proxy uv run pytest -m llm_live tests/live/test_llm_live.py -q` 实际为 7 failed，endpoint 明确返回 403 `AccessDenied.Unpurchased`，因此未写成通过；需具备模型 entitlement 后重跑。
- **阻塞：** 产品代码与确定性门无阻塞；真实 LLM entitlement 是外部验证缺口。

### T30 — Calibrate and Implement Recent Control Index v1

- **状态：** `done`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `ecd916b`
- **领取时间：** 2026-09-10 00:10 CST（异常接管）
- **完成提交：** `8c9e161`
- **接管事实：** 原执行者因额度耗尽中断；项目所有者明确批准接管。接管 HEAD 为 `577af46`，5 个未提交 T30 草稿均保留并逐项审阅。
- **完成事实：** 版本化 aggregate calibration（schema、样本计数、cohort prior/strength、alpha、scale、global fallback；无 vendor raw/ID）；Recent Control v1 使用分前发球校正残差 + EWMA，不确定 winner 跳过、关键分只作 annotation、少于 6 个确定分标记 provisional、纠错从受影响分重算；reducer 与 PostgreSQL observation persistence 接线；前端控制图展示最近 20 条、零线、leader/value、provisional、`as_of` 和关键分标记；CLI 小配额探测在无可用样本时不写文件，`--help` 无 import warning。
- **验证门：** TDD 先失败后通过；focused backend 33 passed，infrastructure 6 passed，全确定性 backend 309 passed/8 deselected；frontend 124 passed、typecheck/build 通过；完整 Playwright 40 passed/4 skipped，prototype 10/10、P1 visual 12/12；`git diff --check` 通过。
- **阻塞：** 无。

## 最近完成任务

### T29 — Render Full PBP and Available Match Statistics

- **状态：** `done`
- **执行者 / ADE：** Claude Code / Claude Code
- **分支：** `main`
- **起始提交：** `117fece`（领取记录 `a42a9c2`）
- **领取时间：** 2026-09-09 22:45 CST
- **完成提交：** `ecd916b`
- **范围：** 按 [P2 实施计划 T29](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t29-render-full-pbp-and-available-match-statistics)：`match-statistics.tsx`、`match-points.tsx`、view-models 映射与 `formatAsOf`、match-main/match-page 接线、e2e 文案与基线更新；preview 不动。
- **完成事实：** TDD 先行：统计 5 项 + 逐分 6 项 + 映射测试先失败后实现。STAT_META 22 项中文标签/单位按发球/接发/关键分/制胜与失误/体能/总计分组；`formatStatValue` null→“暂未提供”；MatchStatisticsCard 只渲染 available 指标、partial 徽章、有数据组内声明缺失、最近 10 分仅由 determinate points 派生、as_of 以澳门时间展示；MatchPointsTimeline Set→Game→Point disclosure（当前盘/局默认展开、旧组折叠）、破发/盘/赛点徽章、revision>1 的 role=status 校准提示、近底部自动跟随否则“有新分 ↓”、空态诚实；生产 StatsCard/MomentumCard 分支改为消费 snapshot（徽章 P2 实时），upcoming 与 preview 行为不变；match-page 将 `stream.snapshot` 传入主列；仓库无 vitest globals，新测试按既有模式显式 `afterEach(cleanup)`；`6c1b448` 修复 T27 提交遗漏的两个后端文件。
- **验证门：** frontend `pnpm test` 121 passed、typecheck 与 build exit 0；prototype e2e 20 passed；`p1-match-live` desktop+mobile 基线经审阅有意重生成；完整 e2e 40 passed/4 skipped（首轮 1 例 mobile prototype 抖动复跑通过）；backend 确定性 286 passed/8 deselected（HEAD 修复后）；`git diff --check` 通过。
- **阻塞：** 无。

### T28 — Expose Match Snapshots and Versioned SSE to the Browser

- **状态：** `done`
- **执行者 / ADE：** Claude Code / Claude Code
- **分支：** `main`
- **起始提交：** `fe1d48b`（领取记录 `3709fe9`）
- **领取时间：** 2026-09-09 21:55 CST
- **完成提交：** `f03985b`
- **范围：** 按 [P2 实施计划 T28](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t28-expose-match-snapshots-and-versioned-sse-to-the-browser)：snapshot REST、版本化 SSE、Next 代理、`useMatchStream`、MatchPage 接入。
- **完成事实：** TDD 先行：stream 9 项 + hook 8 项测试先失败后实现。`GET /matches/{id}` 切为 MatchSnapshot（hot→PG→provider 并回存；PG 重建经 `load_snapshot`，补 DataFreshness 导入修复 e2e 暴露的 NameError）；SSE：ready 带全量 snapshot、match_delta 的 SSE id=state_version 且每版本仅一帧、match_ended 后关流、heartbeat 无版本、lease acquire+20s renew+断开 release；gap 只转发不造事件（客户端跳号重取）；Next 代理转发 Accept/Last-Event-ID；hook：REST 先行、delta=local+1 原子替换、重复忽略、错误保留数据 2s 重连、隐藏 60s abort 释放、恢复先 snapshot 再 SSE、unmount abort；httpx ASGITransport 不支持流式响应，SSE 测试改用进程内 uvicorn。
- **验证门：** backend stream 9 passed、全套确定性 286 passed/8 deselected、infrastructure 12 passed（新增 load_snapshot 重建测试）；frontend `pnpm test` 106 passed、typecheck、build exit 0；完整 e2e 40 passed/4 skipped，P1 视觉基线零变化；`git diff --check` 通过。
- **阻塞：** 无。

（T27 详情见 ROADMAP 登记表与提交 `d354aba`。）

## 最近完成任务

### T27 — Add WebSocket Feed, Redis Leases, and the Realtime Worker

- **状态：** `done`
- **执行者 / ADE：** Claude Code / Claude Code
- **分支：** `main`
- **起始提交：** `1d5d3cf`（领取记录 `a5a0b23`）
- **领取时间：** 2026-09-09 20:50 CST
- **完成提交：** `d354aba`
- **范围：** 按 [P2 实施计划 T27](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t27-add-websocket-feed-redis-leases-and-the-realtime-worker)：WS feed adapter、Redis leases、publisher、realtime worker 与 opt-in WS smoke。
- **完成事实：** TDD 先行：leases 6 + worker 8 + feed 6 共 20 项测试先失败后实现。真实探测发现 vendor WS 每帧推送约 10 场全量 live 对象的数组批次，adapter 因此做 batch 解析 + 客户端 `event_key` 过滤（保留每 match 一条上游连接）；断线统一为 `FeedDisconnected`（reason 不含 key/URL）。worker：打开订阅前 REST 初始 snapshot；断线后丢弃断线前积压帧、REST reconcile 后再续流；terminal 立即关闭并发布 `match_ended`；grace 到期/lease 过期关闭上游；容量满返回 `capacity_limited`（arrival-order 优先）；`cleanup_raw_events` 按 14 天 cutoff。容量排序曾依赖同刻时间戳（float ulp 吞掉 1e-9 偏移）导致 flaky，改为 1e-6 严格递增 arrival stamp 后 20 轮 stress 全绿。
- **验证门：** 20 项确定性测试 20/20 轮 stress 全绿；全套确定性 276 passed/8 deselected；infrastructure 11 passed；真实 opt-in WS smoke 1 passed（探针式选取活跃 match、收到真实 push、canonical 映射零 vendor/key 泄漏）；REST smoke 1 passed；`git diff --check` 通过。
- **阻塞：** 无。

（T26 详情见 ROADMAP 登记表与提交 `98a1a22`。）

### T26 — Build the Canonical Live Reducer and Transactional Persistence

- **状态：** `done`
- **执行者 / ADE：** Claude Code / Claude Code
- **分支：** `main`
- **起始提交：** `8a21c12`（领取记录 `daed5ea`）
- **领取时间：** 2026-09-09 20:32 CST
- **完成提交：** `98a1a22`
- **范围：** 按 [P2 实施计划 T26](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t26-build-the-canonical-live-reducer-and-transactional-persistence)：`app/realtime/`（models/reducer）、repositories 原子 `save_reduction`、migration `0002`（snapshot quality 列）。
- **完成事实：** TDD 先行：reducer 单元 11 项与 integration 4 项先失败（模块不存在）后实现。reducer 以 (set,game,point) 为 point identity、fingerprint 判变：相同 supplier snapshot `changed=False` 且零事件；append 从 prev max+1 续号；旧分变化生成 `PointRevision`（revision+1，before/after 全量）并把 `recompute_from_sequence` 设为该 sequence；被删除/重排的尾段自首个差异重建连续序列；状态/比分/连接/统计/质量差异分别映射 §11 typed changes（固定顺序）；版本仅语义变化 +1；仅 freshness/as_of 差异不算变化。`save_reduction` 单事务 upsert snapshot(+quality)/points(on conflict 更新以应用纠错)/revisions(conflict 忽略)/statistics；重复保存幂等；FK 失败的保存回滚后旧版本仍可读。
- **验证门：** `uv run pytest tests/test_live_reducer.py` 11 passed；`uv run pytest -m infrastructure tests/integration/` 11 passed（T22 7 + T26 4）；`alembic downgrade base` → `upgrade head` 往返 exit 0；全套确定性 256 passed/7 deselected；`git diff --check` 通过。
- **阻塞：** 无。

（T25 详情见 ROADMAP 登记表与提交 `e904485`。）

### T25 — Add Stackable Home Facets and Priority Presentation

- **状态：** `done`
- **执行者 / ADE：** Claude Code / Claude Code
- **分支：** `main`
- **起始提交：** `13a545f`（领取记录 `f3cb4e2`）
- **领取时间：** 2026-09-09 19:55 CST
- **完成提交：** `e904485`
- **范围：** 按 [P2 实施计划 T25](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t25-add-stackable-home-facets-and-priority-presentation)：Home 叠加筛选（circuit/gender/discipline）、优先级展示与 catalog 消费、typed client、双视口 e2e。
- **完成事实：** TDD 先行：`lib/match-filters.test.ts`（13 项）与 `components/home/match-filters.test.tsx`（9 项）先失败后实现。默认 facet=ATP+WTA/全部性别/单打；空组=全部；toggle 不可自动补选（取消唯一值→空=全部）；排序 tier→live→开赛时间→id 与后端一致；chip 组 role=group+aria-label、aria-pressed、计数进 accessible name、零计数且未激活禁用、激活零计数仍可取消、`恢复默认` 仅非默认时出现；Home 改用 `getMatchCatalog`（新 Next 代理路由 `app/api/matches/catalog`），Featured 取 `featured_match_id`（非数组首项），Live/Upcoming/Featured 共用同一筛选状态，facet counts 为 live+upcoming 合并；筛选后为空只显示空态、不放宽筛选。P1 失败注入 glob 由 `**/api/matches*` 修正为 `**/api/matches**`（原 glob 的 `*` 不跨 `/`，catalog 请求未被拦截）；视觉 spec 增加“等待平滑滚动结束 + instant 回顶”稳定化。
- **验证门：** `pnpm test` 98 passed（含 26 项新测试）；`pnpm typecheck`、`pnpm build` exit 0；`pnpm test:e2e --grep "P2 Home filters|prototype"`：P2 Home filters 6/6 双视口、prototype match 页 10/10 零变化；4 张 Home 视觉基线（desktop/mobile × prototype home-initial/home-answer、p1-home-initial/p1-home-result）逐张 diff 审阅后有意更新（差异仅为新增筛选栏与整体下移，无布局回归）；完整 `pnpm test:e2e` 连续两轮 40 passed/4 skipped（live specs 无 flags 如实 skip；首轮 1 次 sticky-header 2px 抖动在滚动稳定化后未再复现）；后端回归 241 passed/7 deselected。
- **阻塞：** 无。

（T24 详情见 ROADMAP 登记表与提交 `dddb734`。）

### T24 — Add Match Catalog Filters, History, H2H, and P2 REST APIs

- **状态：** `done`
- **执行者 / ADE：** Claude Code / Claude Code
- **分支：** `main`
- **起始提交：** `85dd65d`（领取记录 `5dd7af1`）
- **领取时间：** 2026-09-09 19:37 CST
- **完成提交：** `dddb734`
- **范围：** 按 [P2 实施计划 T24](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t24-add-match-catalog-filters-history-h2h-and-p2-rest-apis)：`MatchFilters`/`FacetCounts`/`MatchCatalog`/`PlayerResults`/`HeadToHeadResult`、确定性排序、昨天/近期/H2H 服务方法与三个新 REST 路由，并保持 P1 回归。
- **完成事实：** TDD 先行：`test_p2_service.py`（17 项）与 `test_p2_api.py`（10 项）先失败（MatchFilters 不存在）后实现。默认 facet=ATP+WTA/全部性别/单打，空组=全部；排序 tier→live→scheduled_at→id（与计划代码一致）；facet counts 按“尊重另外两组、保留 0 值”计算；昨天=Asia/Macau 日历；recent 满 fetch 上限（10）→PARTIAL，否则 AVAILABLE；provider typed unsupported→UNAVAILABLE（非零值、非空猜测）；历史/H2H 成功缓存 600s、空/unsupported 60s（provider 调用计数证明）；`GET /matches/catalog` 注册在 `/matches/{match_id}` 之前；limit/scope/status/enum 非法输入全部 422；P1 `/matches` 形状、Chat 历史 guard、`chat/tools.py`、`main.py` 均未改动（guard 留待 T31）。共享多 facet 测试数据集移入 `tests/p2_fakes.py`；Fake 的 ATP Finals 补上诚实 facet（atp/men/singles）。
- **验证门：** `uv run pytest tests/test_p2_service.py tests/test_p2_api.py tests/test_service.py tests/test_api.py tests/test_p1_acceptance.py` 74 passed；全套确定性 241 passed/7 deselected；`git diff --check` 通过。
- **阻塞：** 无。

（T23 详情见 ROADMAP 登记表与提交 `015ff7f`。）

（T22 详情见 ROADMAP 登记表与提交 `20dac5f`。）

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-12 | `4e882b9` | TDD 先红（缺 `app.players`）后绿；focused 75 passed；全确定性 backend 382 passed/14 deselected；真实 `TENNIX_RUN_API_TENNIS_LIVE=1` api_tennis_live 2 passed（standings 两 tour 认证与 canonical 映射、零泄漏） | T44 完成；canonical 排名模型与 standings adapter 就绪 |
| 2026-09-12 | `42c7a36` | TDD：28 项 player 组件测试先红（定向 10 项失败）后绿；`pnpm test` 179 passed、typecheck、build exit 0；`player-directory.visual` 双视口 4/4（update 后 plain 复跑）；四张 PNG 逐张审阅无裁切/横向溢出/dev overlay/双语层级问题；回归 `--grep "player directory visual\|prototype\|visual"` 16 passed/4 skipped/10 failed，10 项 prototype.visual 失败在 `44cd9d5` 干净 worktree 复跑相同（旧债，未重录）；p1-home-result mobile 抖动复跑通过 | T43 完成；v0 球员页工程收口与四张双视口视觉基线冻结 |
| 2026-09-12 | `5c3d469` | TDD：Home 内部实现文字泄漏与完整流式结果回归先失败后通过；frontend `pnpm test` 151 passed、typecheck/build；隔离 fake Home 流程 desktop+mobile 2 passed、P1 视觉 12 passed；真实服务重启后浏览器等待 Home 回答至 `done`，10 张结构化比赛卡与资料缺失提示可见，progress/internal footer/原问题回显均为 0；full e2e 28 passed/14 skipped/14 failed（既有 P2 gender query 断言与 prototype 基线问题）；health/home 200；`git diff --check` 通过 | T41 完成；首页与详情页用户展示策略同步 |
| 2026-09-11 | `ddaf24b` | TDD focused provider/service/view-model/component 先红后绿；backend 确定性 `352 passed, 2 skipped, 9 deselected`；frontend `140 passed` + typecheck + build；隔离 fake 服务 P1 功能 `12 passed`、视觉 `12 passed`；真实 API-Tennis REST smoke `1 passed`；真实 catalog/detail 国家数据一致；真实浏览器鼠标 Home→Match→Home 确认德国国旗+`DEU`、World Globe+`WORLD`，error/warn 为空；`git diff --check` 通过 | T38 完成；首页比赛卡展示国旗，详情页展示国旗+国家代码，`World` 语义保留 |
| 2026-09-11 | `54059fe` | TDD focused provider/service/reducer `91 passed`；backend 确定性 `349 passed, 2 skipped, 9 deselected`；frontend `136 passed` + typecheck + build；隔离 fake 服务 P1 Playwright 功能+视觉 `24 passed`；真实 API-Tennis REST smoke 1 passed；真实服务 health 200、目标 Match API 200；真实浏览器鼠标进入并刷新目标页，浏览器 error/warn 为空；`git diff --check` 通过 | T37 完成；详情页补齐官方可获得场地与安全国家代码，所有仍缺失的元数据/实时能力均改为字段级解释 |
| 2026-09-11 | `28b316d` | TDD focused 用例先失败后通过；backend `355 passed, 2 skipped`；frontend `135 passed` + typecheck + build；隔离假服务关键 Playwright 4 passed；真实 SSE 阶段顺序与真实浏览器阶段文案复核通过；backend health 200、Match Page HTTP 200；`git diff --check` 通过 | T36 完成；Chat 长等待期间可见解析/规划/取数/生成进度，真实耗时未被掩盖 |
| 2026-09-10 | `b60217e` | TDD focused 先红后绿；backend 确定性 337 passed/2 skipped/9 deselected；infrastructure 14 passed；frontend 130 passed + typecheck + build；真实 API-Tennis REST smoke 1 passed；真实浏览器鼠标流程与最新前端错误/警告复核通过；`git diff --check` 通过 | T33 完成；直播发现、终态过滤、球员档案持久化、PBP 持久化冲突和统计周期 key 已修复；官方缺失字段仍诚实保留 |
| 2026-09-10 | `525d701` | TDD focused 用例先失败后通过；frontend `pnpm test` 128 passed；`pnpm typecheck` 通过；本地浏览器数据加载后的真实页面复核通过；`git diff --check` 通过 | 空 facet 的“未知”筛选项隐藏；canonical `unknown` 语义保留 |
| 2026-09-10 | `ac9c6e5` | T32 focused replay/recovery 3 passed；确定性 backend 325 passed/11 deselected；infrastructure 13 passed/323 deselected；frontend 127 passed + typecheck + build；默认 Playwright 40 passed/10 skipped；Replay 功能 2 passed、视觉 4 passed（双视口）；真实 API-Tennis REST 1 passed、WebSocket 1 passed；真实浏览器手动流程至完赛；范围审计与 `git diff --check` 通过；真实 LLM 7 failed（403 `AccessDenied.Unpurchased`） | T32 产品完成；P2 已关闭；LLM entitlement 缺口按 runbook 保留重跑命令 |
| 2026-09-10 | `128518f` | T31 focused backend 56 passed；全确定性 backend 322 passed/11 deselected；frontend 127 passed + typecheck + build；完整 Playwright 40 passed/4 skipped；`git diff --check` 通过；真实 LLM opt-in 7 failed（endpoint 403 `AccessDenied.Unpurchased`） | T31 产品完成并推送；T32 已领取，真实 LLM 门待 entitlement 后重跑 |
| 2026-09-10 | `8c9e161` | T30 focused backend 33 passed；infrastructure 6 passed；全确定性 backend 309 passed/8 deselected；frontend 124 passed + typecheck + build；完整 Playwright 40 passed/4 skipped，prototype 10/10、P1 visual 12/12；CLI `--help` 无 import warning，`git diff --check` 通过 | T30 完成；Recent Control v1、聚合校准、reducer/persistence 与控制图就绪，T31 进行中 |
| 2026-09-09 | `ecd916b` | TDD：统计 5 + 逐分 6 + 映射测试先失败后通过；frontend 121 passed + typecheck + build；prototype e2e 20 passed；完整 e2e 40 passed/4 skipped，p1-match-live 基线审阅后重生成；backend 286 passed/8 deselected（含 `6c1b448` HEAD 修复） | T29 完成；PBP 与统计 UI 就绪，T30 ready |
| 2026-09-09 | `f03985b` | TDD：stream 9 + hook 8 先失败后通过；backend 286 passed/8 deselected、infrastructure 12；frontend 106 + typecheck + build；完整 e2e 40 passed/4 skipped 视觉零变化 | T28 完成；snapshot + 版本化 SSE 就绪，T29 ready |
| 2026-09-09 | `d354aba` | TDD：leases 6 + worker 8 + feed 6 先失败后通过；20/20 轮 stress 全绿；全套确定性 276 passed/8 deselected；infrastructure 11 passed；真实 WS smoke 1 passed、REST smoke 1 passed | T27 完成；WS feed/leases/worker 就绪，T28 ready |
| 2026-09-09 | `98a1a22` | TDD：reducer 11 项 + integration 4 项先失败后通过；infrastructure 11 passed；alembic base↔head 往返 exit 0；全套确定性 256 passed/7 deselected；`git diff --check` 通过 | T26 完成；canonical reducer 与事务化持久化就绪，T27 ready |
| 2026-09-09 | `e904485` | TDD：match-filters 单元 13 + 组件 9 先失败后通过；`pnpm test` 98 passed；typecheck/build exit 0；e2e P2 Home filters 6/6 双视口；4 张 Home 基线审阅后更新、match 页零变化；完整 e2e 连续两轮 40 passed/4 skipped；后端 241 passed/7 deselected | T25 完成；Home 叠加筛选与优先级展示就绪，T26 ready |
| 2026-09-09 | `dddb734` | TDD：p2_service 17 项 + p2_api 10 项先失败后通过；service/API/P1 acceptance 门 74 passed；全套确定性 241 passed/7 deselected；`git diff --check` 通过 | T24 完成；catalog/history/H2H 服务与 REST 就绪，T25 ready |
| 2026-09-09 | `015ff7f` | TDD：40 项契约测试先失败后通过；adapter+contract 53 passed；全套确定性 214 passed/7 deselected；真实 opt-in REST smoke 1 passed（认证、live canonical、snapshot、零泄漏）；`git diff --check` 通过 | T23 完成；API-Tennis REST adapter 就绪，T24 ready |
| 2026-09-09 | `20dac5f` | TDD：persistence 单元 17 项 + integration 7 项先失败后通过；compose postgres/redis healthy；alembic upgrade→downgrade base→upgrade exit 0；全套确定性 174 passed/6 deselected；redis PONG、pg_isready；敏感模式/whitespace 扫描无命中 | T22 完成；P2 持久化地基就绪，T23 ready |
| 2026-09-09 | `5b479fc` | TDD：test_p2_domain 13 项与 async identity 先失败后通过；领域/兼容门 55 passed；全套确定性 150 passed/6 deselected（P1 验收矩阵 10/10）；`git diff --check` 通过 | T21 完成；P2 canonical domain 与 provider contracts 就绪，T22 ready |
| 2026-09-09 | `969c7ec` | root-env TDD 2/2；backend 128 passed；frontend 72/72 + typecheck/build；Playwright 34 passed/4 skipped；路径/权限/ignore/最小权限/敏感模式检查 | M01 完成；根目录 `.env` 成为唯一配置入口，T21 仍 ready |
| 2026-09-09 | `b7921c0` | P2 规格/计划覆盖审查；12 个任务和 60 个步骤结构核对；占位符/敏感模式扫描无命中；本地链接存在；whitespace 与 diff check 通过 | T20 完成；P2.0 关闭，T21 ready |
| 2026-09-09 | `fdb0131` | Home 单元 72/72；typecheck/build；长 Markdown 结构化卡片视口回归桌面/移动 12/12；完整 Playwright 34 passed/4 skipped，视觉基线通过 | T19 完成；回答完成后结构化比赛卡片保持可见 |
| 2026-09-08 | `5dcaa6a` | backend 确定性 124 passed；frontend 66/66 + typecheck + build + E2E 32 passed/4 skipped；provider_live 1/1；llm_live 4/4；end_to_end_live 1/1；真实浏览器 end-to-end 2/2；手动 Djokovic SSE 完整结束 | T16 与 P1 真实运行时验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T43 已由用户授权从 v0 交接给 Claude Code，于 2026-09-12 15:38 CST 在 `main` 领取；起始提交为 `44cd9d5`（v0 原型产物，已含用户确认的两页视觉方向）。

**交接说明：** v0 的输入门已完成（原型代码入库、导航改 `/players`、视觉方向被接受），但 T43 工程收口未完成。本执行者按 T43 计划以 TDD 修复已验证问题（搜索跨 tour、`暂无当前排名` 固定文案、内部 matchId 链接、分场地胜负、Finished 样例日期不晚于快照日），补齐组件测试、视觉规格与 4 张双视口基线，并运行全部回归门；旧 prototype.visual 历史失败须以父提交复跑归因，不盲目重录 Home/Match 基线。工作区保留既有未跟踪文件：`.codex/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`、`frontend/next-env.d.ts`。所有 ADE 只使用根目录 `.env`；凭据不得写入代码、文档、fixture、日志、提交或聊天输出。

**状态：** T41 已由 Codex 于 2026-09-12 12:25 在 `main` 完成；领取提交为 `86f931b`，实现提交为 `5c3d469`，起始提交为 `096dce9`。Home 与 Match 详情页已共享用户可见回答策略；真实浏览器等待首页回答至 `done` 后完成质量核对。

**交接说明：** T41 只修复 Home 生产问答卡的展示层策略：移除内部来源 footer，集中回答标签映射，并保留结构化卡片、资料缺失提示、失败重试和进度文案；Home 的工具能力与预览原型未扩大或改动。前端确定性测试、类型检查、构建、隔离 Playwright 和真实浏览器门已通过；完整 e2e 的既有 P2 默认 `gender=*` 断言与 prototype 视觉基线失败未混入本任务。所有 ADE 只使用根目录 `.env`；凭据不得写入代码、文档、fixture、日志、提交或聊天输出。

**状态：** T39 已由 Codex 于 2026-09-12 08:25 在 `main` 领取并于 `61d8fee` 完成；起始提交为 `fcfcc55`，工作区保留用户已有未跟踪文件。

**交接说明：** T30 接管时原执行者因额度耗尽中断，项目所有者明确批准 Codex 接管；T30–T38 已在 `main` 串行完成并推送。T39 的真实故障曾复现：global 请求先返回结构化比赛，随后模型调用 match-only `get_match_intelligence`，后端按设计返回 `invalid_request`；根因是工具目录未按 global scope 裁剪，且没有多工具依赖/非法调用的编排协议。实现后又通过真实 Qwen 门禁发现未知 `format` 时模型会复述 `BO3`，已增加完整正文质量校验与安全重写/降级。依据阿里云 Function Calling 与 OpenAI 兼容接口官方文档：并行仅用于无依赖调用，依赖调用串行，工具目录实行最小权限。所有 ADE 只使用根目录 `.env`；API-Tennis/LLM 凭据不得写入代码、文档、fixture、日志、提交或聊天输出。

**旧交接（T29）：** 接手 T29 前完整阅读 [P2 设计规格 §14](./docs/superpowers/specs/2026-09-09-tennixai-p2-live-match-intelligence-design.md) 和 [P2 实施计划](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t29-render-full-pbp-and-available-match-statistics)。所有 ADE 只使用根目录 `.env`；API-Tennis 凭据变量为 `TENNIX_API_TENNIS_API_KEY`，不得写入代码、文档、fixture、日志、提交或聊天输出。T28 起 MatchPage 经 `useMatchStream` 消费 `/api/matches/{id}` + `/stream`（snapshot 含 points/statistics/quality/state_version）；SSE 测试用进程内 uvicorn（ASGITransport 缓冲）；用户已追加要求：P2 收尾时用真实浏览器按业务流程逐项人工验收直到无 bug。

**旧交接（T27）：** 接手 T28 前完整阅读 [P2 设计规格 §9–§11](./docs/superpowers/specs/2026-09-09-tennixai-p2-live-match-intelligence-design.md) 和 [P2 实施计划](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t28-expose-match-snapshots-and-versioned-sse-to-the-browser)。所有 ADE 只使用根目录 `.env`；API-Tennis 凭据变量为 `TENNIX_API_TENNIS_API_KEY`，不得写入代码、文档、fixture、日志、提交或聊天输出。T27 起实时链路为：leases（`tnx:lease:*`/`tnx:demand*`）→ worker（REST 先行 + WS 增量 + reducer + save_reduction + publisher）→ Redis（`tnx:hot:*` + `tnx:match:*` pub/sub）；SSE 尚未接线（T28）。vendor WS 为数组批次帧，adapter 客户端过滤。用户已追加要求：P2 收尾时用真实浏览器按业务流程逐项人工验收直到无 bug。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-12 | T44 完成：canonical 排名模型、API-Tennis standings adapter 与真实 standings smoke | `4e882b9` |
| 2026-09-12 | T43 完成：v0 球员页工程收口（全目录搜索、固定文案、内部 matchId 链接、分场地胜负、样例日期）与四张双视口视觉基线冻结 | `42c7a36` |
| 2026-09-12 | T41 完成：首页与详情页共享回答标签，移除 Home 生产内部来源 footer，补齐完整流式/Home 双视口回归 | `5c3d469` |
| 2026-09-12 | T39 完成：作用域感知编排、综合事实质量门与 CommonMark/GFM 渲染 | `61d8fee` |
| 2026-09-11 | T38 完成：保留 `World` 国家语义，首页显示国旗、详情页显示国旗与国家代码 | `ddaf24b` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
