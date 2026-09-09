# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-09 19:01 CST

**当前任务：** 无（T22 已完成；T23 已 ready，尚未领取）

**任务状态：** `idle`

**当前执行者 / ADE：** —

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**最近完成任务提交：** `20dac5f`

**最后验证的产品提交：** `20dac5f`

**T23 起始提交：** 待领取时填写

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
- 下一任务是 T23（API-Tennis REST adapter），必须按启动入口另行领取；真实 REST smoke 需要根目录 `.env` 中的 `TENNIX_API_TENNIS_API_KEY`。
- 已知非 T17 限制：LiveTennisAPI 的 `/players?search` 当前不能把中文显示名“郑钦文”直接映射到 `Qinwen Zheng`；canonical English name 查询已通过，中文别名/名称归一化需另立任务批准。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；保留原样。

## 当前任务

无。T22 已完成；T23（Implement the API-Tennis REST Adapter）已 ready，接手前须按启动入口另行领取。

## 最近完成任务

### T22 — Add PostgreSQL, Redis, Migrations, and Durable Identity

- **状态：** `done`
- **执行者 / ADE：** Claude Code / Claude Code
- **分支：** `main`
- **起始提交：** `181f04e`（领取记录 `2007e3e`）
- **领取时间：** 2026-09-09 18:13 CST
- **完成提交：** `20dac5f`
- **范围：** 按 [P2 实施计划 T22](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t22-add-postgresql-redis-migrations-and-durable-identity)：compose 基础设施、持久化依赖与 markers、typed settings、P2 core schema migration、async `Database` 与 identity/snapshot/raw-event repositories。
- **完成事实：** TDD 先行：`test_persistence_models.py`（17 项）与 `tests/integration/test_postgres_repositories.py`（7 项）先失败（ModuleNotFoundError）后实现。schema 覆盖规格 §7.2 全部 13 张表；external id 表 `(provider, external_id)` 与 `(internal_id, provider)` 双唯一；identity `get_or_create` 使用 insert-on-conflict + 读重试事务（并发 20 路收敛为同一 ID），实体占位行先显式 flush 再插映射以满足 FK；`purge_raw_events` 只按 `raw_provider_events.observed_at < before` 删除；`raw_retention_cutoff` 拒绝 <1 天。跨表 `save_reduction` 事务按计划留待 T26。compose 无任何供应商/LLM 凭据；alembic URL 经 `Settings` 从根目录 `.env` 读取。
- **验证门：** `uv run pytest tests/test_persistence_models.py` 17 passed；`docker compose up -d --wait postgres redis` healthy；`uv run alembic upgrade head` → `-m infrastructure` integration 7 passed → `alembic downgrade base` → `alembic upgrade head` 全部 exit 0；全套确定性 `uv run pytest -m "not llm_live and not provider_live and not end_to_end_live"` 174 passed/6 deselected（DB 在位时 infrastructure 随套件运行并通过）；redis PONG、pg_isready 通过；`git diff --check` 与敏感模式扫描无命中。
- **阻塞：** 无。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-09 | `20dac5f` | TDD：persistence 单元 17 项 + integration 7 项先失败后通过；compose postgres/redis healthy；alembic upgrade→downgrade base→upgrade exit 0；全套确定性 174 passed/6 deselected；redis PONG、pg_isready；敏感模式/whitespace 扫描无命中 | T22 完成；P2 持久化地基就绪，T23 ready |
| 2026-09-09 | `5b479fc` | TDD：test_p2_domain 13 项与 async identity 先失败后通过；领域/兼容门 55 passed；全套确定性 150 passed/6 deselected（P1 验收矩阵 10/10）；`git diff --check` 通过 | T21 完成；P2 canonical domain 与 provider contracts 就绪，T22 ready |
| 2026-09-09 | `969c7ec` | root-env TDD 2/2；backend 128 passed；frontend 72/72 + typecheck/build；Playwright 34 passed/4 skipped；路径/权限/ignore/最小权限/敏感模式检查 | M01 完成；根目录 `.env` 成为唯一配置入口，T21 仍 ready |
| 2026-09-09 | `b7921c0` | P2 规格/计划覆盖审查；12 个任务和 60 个步骤结构核对；占位符/敏感模式扫描无命中；本地链接存在；whitespace 与 diff check 通过 | T20 完成；P2.0 关闭，T21 ready |
| 2026-09-09 | `fdb0131` | Home 单元 72/72；typecheck/build；长 Markdown 结构化卡片视口回归桌面/移动 12/12；完整 Playwright 34 passed/4 skipped，视觉基线通过 | T19 完成；回答完成后结构化比赛卡片保持可见 |
| 2026-09-09 | `5572960` | TDD 先行测试验证两处原文显示失败；修复后 frontend 71/71 + typecheck + build；隔离服务 Playwright 10/10；真实浏览器 `strong=10`、`ul=1`、无 `**` | T18 完成；Home/Match 问答 Markdown 展示通过 |
| 2026-09-08 | `69c8238` | backend 确定性 126 passed；frontend 69/69 + typecheck + build；隔离 fake 服务的 Playwright 32 passed/4 skipped；真实 REST upcoming 50 场与 Qinwen Zheng 指定球员查询；真实浏览器 Home→Match→上下文问答 | T17 完成；P1 当前实现门通过 |
| 2026-09-08 | `5dcaa6a` | backend 确定性 124 passed；frontend 66/66 + typecheck + build + E2E 32 passed/4 skipped；provider_live 1/1；llm_live 4/4；end_to_end_live 1/1；真实浏览器 end-to-end 2/2；手动 Djokovic SSE 完整结束 | T16 与 P1 真实运行时验收通过 |
| 2026-09-08 | `98075ef` | backend 确定性 suite 117 passed；frontend 66/66 + typecheck + build + e2e 32 passed/4 skipped；验收矩阵 10/10；llm_live 4/4 + 浏览器 2/2（真实 Qwen）；provider/end-to-end live 如实 skip；泄漏检查业务零命中；Final Gate 八条核对 | T15 与 P1 整体验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T22 已由 Claude Code 于 2026-09-09 在 `main` 完成，实现提交 `20dac5f`；当前无领取中的任务，T23 保持 ready。

**交接说明：** 接手 T23 前完整阅读 [P2 设计规格](./docs/superpowers/specs/2026-09-09-tennixai-p2-live-match-intelligence-design.md) 和 [P2 实施计划](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t23-implement-the-api-tennis-rest-adapter)。所有 ADE 只使用根目录 `.env`；API-Tennis 凭据变量为 `TENNIX_API_TENNIS_API_KEY`，不得写入代码、文档、fixture、日志、提交或聊天输出。T22 起本地基础设施为 compose 的 `tennix-postgres`/`tennix-redis`（colima）；identity 持久化实现为 `PostgresIdentityRepository`（`app/persistence/repositories.py`），`MemoryIdentityRepository` 仅用于单元测试；integration 测试以 `infrastructure` marker 运行且在环境缺失时如实 skip。用户已追加要求：P2 收尾时用真实浏览器按业务流程逐项人工验收直到无 bug。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-09 | T22 完成：compose、Alembic、P2 schema 与 durable identity repositories | `20dac5f` |
| 2026-09-09 | 领取 T22：PostgreSQL、Redis、migrations 与 durable identity | `181f04e` 起始 |
| 2026-09-09 | T21 完成：P2 canonical domain、async identity 与 provider contracts | `5b479fc` |
| 2026-09-09 | 领取 T21：扩展 canonical domain 与 provider contracts | `f574b1a` 起始 |
| 2026-09-09 | M01 完成：backend/frontend/Playwright/真实测试统一使用根目录 `.env` | `969c7ec` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
