# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 14:08 CST

**当前任务：** T10 — Define Chat Models, Historical Guard, and Business Tools

**任务状态：** `ready`

**当前执行者 / ADE：** `unassigned`

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `unassigned`（领取任务时记录当时的 HEAD）

**最后验证的产品提交：** `e6d59ca`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T09 已完成（`e6d59ca`）：前端薄代理——`proxyBackend()`（SSE body 原样透传、query/status/content-type/cache-control/retry-after/x-request-id 保留、authorization/cookie 不转发、失败→502/未配置→500 internal_error）+ 四个 route（`/api/players/search`、`/api/matches`、`/api/matches/[matchId]`、`/api/chat/stream`，全部 nodejs + force-dynamic）；vitest 8/8、typecheck、build、视觉基线 10/10 全过。frontend 现已有 `test`/`typecheck` scripts 与 vitest 配置。
- T08（`039d144`）：确定性 REST + 错误信封 + `create_app(settings, *, provider, chat_orchestrator)`。T07（`000ca1a`）：TennisService。T06（`6605ecb`）：AsyncTTLCache。T05（`16a0688`）：LiveTennisProvider。T04（`20735bd`）：Protocol+Fake。T03（`5ed8a18`）：canonical models。
- 当前唯一主任务是 T10：定义 chat 契约——`app/chat/models.py`（ChatScope/ChatMessage/ChatRequest/ChatContext/StructuredToolResult + 三个工具 Args 模型）、`app/chat/tools.py`（`BusinessTools.catalog()/execute()`，恰好三个工具，Pydantic 校验，ValidationError→invalid_request，match scope 强制使用 context.match_id）、`is_historical_query()` 确定性守卫（昨天/昨日/上一场/最近一场/历史/yesterday/last match/previous match/history）。测试优先写 `tests/test_chat_tools.py`。不实现模型客户端、orchestrator 或 SSE（T11）。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

按计划 Task 10 实现 chat 模型与业务工具：catalog 顺序恰为 `find_player_matches`、`get_live_matches`、`get_match`，`time_scope` enum 恰为 `["today","tonight","next"]`，schema 来自 Args 模型的 `model_json_schema()`；`execute()` 按计划分派到 `TennisService`，返回含 domain models 的 `StructuredToolResult`；match scope 忽略模型提供的 `match_id`，global scope `get_match` 无 `match_id` 抛 invalid_request 422；未知工具 invalid_request；`is_historical_query()` 大小写不敏感覆盖九个短语。

### 为什么现在做

T11 的 tool loop 与 T15 验收集都直接消费 `BusinessTools`；历史查询守卫必须在 chat 层确定性拒绝，绝不调用 provider 或模型。

### 实施依据

- [P1 实施计划 — Task 10](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-10-define-chat-models-historical-guard-and-business-tools)

### 预计变更范围

- `backend/app/chat/__init__.py`、`backend/app/chat/models.py`、`backend/app/chat/tools.py`
- `backend/tests/test_chat_tools.py`

### 完成门

- `uv run pytest tests/test_chat_tools.py tests/test_service.py -v` 通过：恰好三个工具、enum schema、match scope 注入、历史查询零 provider/模型调用、malformed args→invalid_request。
- 不实现 client/orchestrator/SSE/前端（T11+）。
- `ROADMAP.md` 的 T10 写入完成提交和验证证据；T11 变为 `ready`。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 10 的测试优先顺序实施，不扩大到 T11。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `e6d59ca` | `pnpm test -- lib/server/backend-proxy.test.ts` 8/8；`pnpm typecheck` 通过；`pnpm build` exit 0；`pnpm test:e2e --grep prototype` 10/10 | T09 验收通过 |
| 2026-09-08 | `039d144` | `uv run pytest tests/test_api.py -v` 16/16；全套确定性 suite 75/75 | T08 验收通过 |
| 2026-09-08 | `000ca1a` | `uv run pytest tests/test_service.py tests/test_cache.py tests/test_provider_contract.py -v` 35/35；全套确定性 suite 59/59 | T07 验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T09 已由 Claude Code（Codex Goal）于 2026-09-08 完成并交接（提交 `e6d59ca`）；T10 可领取。

**交接说明：** 后端 chat 契约以计划 Task 10 的 Pydantic 模型为准；`BusinessTools` 构造注入 `TennisService`（测试可用 T07 的 CountingProvider 模式或 FakeTennisProvider+真实 service）。`StructuredToolResult.matches` 存 domain `Match` 对象（非序列化 payload）。历史守卫的固定文案是 `P1 暂不支持历史比赛结果查询。`（T11 orchestrator 使用）。前端 `/api/chat/stream` 代理已就绪，等待 T11 后端 SSE。视觉基线纪律不变：前端改动先跑 `pnpm test:e2e`，逐张审阅 diff。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | T09 完成：Next.js 薄代理与 vitest 骨架 | `e6d59ca` |
| 2026-09-08 | 领取 T09 并置为 in_progress | `22115c3` |
| 2026-09-08 | T08 完成：确定性 REST API 与错误信封 | `039d144` |
| 2026-09-08 | 领取 T08 并置为 in_progress | `3ce1b86` |
| 2026-09-08 | T07 完成：TennisService 与时间语义 | `000ca1a` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
