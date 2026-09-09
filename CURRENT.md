# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-10 00:50 CST

**当前任务：** T32 — Add Replay E2E, Fault Recovery, Runbook, and Final P2 Gate

**任务状态：** `in_progress`

**当前执行者 / ADE：** Codex / Codex

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**最近完成任务提交：** `128518f`

**最后验证的产品提交：** `128518f`

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
- 本地运行与 opt-in 真实门命令见 [docs/runbooks/p1-local.md](./docs/runbooks/p1-local.md)。
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
- 当前唯一任务是 T32（Replay E2E、故障恢复、runbook 与 Final P2 Gate），必须按启动入口继续；T31 已完成。
- 已知非 T17 限制：LiveTennisAPI 的 `/players?search` 当前不能把中文显示名“郑钦文”直接映射到 `Qinwen Zheng`；canonical English name 查询已通过，中文别名/名称归一化需另立任务批准。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；保留原样。

## 当前任务

### T32 — Add Replay E2E, Fault Recovery, Runbook, and Final P2 Gate

- **状态：** `in_progress`
- **执行者 / ADE：** Codex / Codex
- **分支：** `main`
- **起始提交：** `128518f`
- **领取时间：** 2026-09-10 00:50 CST
- **前置完成：** T31 已以 `128518f` 完成并通过确定性验证；本次领取从该产品提交开始，未创建分支。
- **范围：** 按 [P2 实施计划 T32](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t32-add-replay-e2e-fault-recovery-runbook-and-final-p2-gate)：deterministic replay、重启/纠错/断线恢复、双视口功能/视觉验收、真实 smoke、runbook 与 Final P2 Gate；不引入预测、odds、market 或交易能力。
- **阻塞：** 无。

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

**状态：** T30 已由 Codex 于 2026-09-10 在 `main` 完成，实现提交 `8c9e161`；T31 已从该提交领取，`in_progress`。

**交接说明：** T30 接管时原执行者因额度耗尽中断，项目所有者明确批准 Codex 接管；接管 HEAD 为 `577af46`，基线为移除异常 `NO_PROXY/no_proxy` 后的 18 collected、12 passed、6 failed。T30 已按 [P2 设计规格 §15](./docs/superpowers/specs/2026-09-09-tennixai-p2-live-match-intelligence-design.md#15-recent-control-index-v1) 与 [P2 实施计划 T30](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t30-calibrate-and-implement-recent-control-index-v1) 完成；当前 T31 按 [P2 实施计划](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t31-add-p2-intelligence-tools-and-versioned-chat-answers) 继续。所有 ADE 只使用根目录 `.env`；API-Tennis 凭据变量为 `TENNIX_API_TENNIS_API_KEY`，不得写入代码、文档、fixture、日志、提交或聊天输出；用户要求 P2 收尾时用真实浏览器按业务流程逐项人工验收直到无 bug。

**旧交接（T29）：** 接手 T29 前完整阅读 [P2 设计规格 §14](./docs/superpowers/specs/2026-09-09-tennixai-p2-live-match-intelligence-design.md) 和 [P2 实施计划](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t29-render-full-pbp-and-available-match-statistics)。所有 ADE 只使用根目录 `.env`；API-Tennis 凭据变量为 `TENNIX_API_TENNIS_API_KEY`，不得写入代码、文档、fixture、日志、提交或聊天输出。T28 起 MatchPage 经 `useMatchStream` 消费 `/api/matches/{id}` + `/stream`（snapshot 含 points/statistics/quality/state_version）；SSE 测试用进程内 uvicorn（ASGITransport 缓冲）；用户已追加要求：P2 收尾时用真实浏览器按业务流程逐项人工验收直到无 bug。

**旧交接（T27）：** 接手 T28 前完整阅读 [P2 设计规格 §9–§11](./docs/superpowers/specs/2026-09-09-tennixai-p2-live-match-intelligence-design.md) 和 [P2 实施计划](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t28-expose-match-snapshots-and-versioned-sse-to-the-browser)。所有 ADE 只使用根目录 `.env`；API-Tennis 凭据变量为 `TENNIX_API_TENNIS_API_KEY`，不得写入代码、文档、fixture、日志、提交或聊天输出。T27 起实时链路为：leases（`tnx:lease:*`/`tnx:demand*`）→ worker（REST 先行 + WS 增量 + reducer + save_reduction + publisher）→ Redis（`tnx:hot:*` + `tnx:match:*` pub/sub）；SSE 尚未接线（T28）。vendor WS 为数组批次帧，adapter 客户端过滤。用户已追加要求：P2 收尾时用真实浏览器按业务流程逐项人工验收直到无 bug。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-10 | 领取 T31：P2 Intelligence tools 与版本化 Chat | `8c9e161` 起始 |
| 2026-09-10 | T30 完成：Recent Control v1 校准、reducer/persistence 与控制图 | `8c9e161` |
| 2026-09-10 | T30 接管记录 | `60fa62e` |
| 2026-09-09 | T29 完成：完整 PBP 与 22 项统计渲染 | `ecd916b` |
| 2026-09-09 | 修复 T27 遗漏提交：mapping helpers 与 FeedDisconnected | `6c1b448` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
