# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 14:14 CST

**当前任务：** T11 — Add the OpenAI-Compatible Tool Loop and SSE Route

**任务状态：** `ready`

**当前执行者 / ADE：** `unassigned`

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `unassigned`（领取任务时记录当时的 HEAD）

**最后验证的产品提交：** `9d988ed`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T10 已完成（`9d988ed`）：`app/chat/models.py`（ChatScope/ChatMessage/ChatRequest/ChatContext/StructuredToolResult + 三个 Args 模型）、`app/chat/tools.py`（`BusinessTools.catalog()/execute()` 恰好三工具；`catalog()` 内联 `$defs` 使 time_scope enum 直接可见；match scope 强制 context.match_id；ValidationError→invalid_request 422 + `{"tool": name}`）、`is_historical_query()` 覆盖九个 P1 短语。
- T09（`e6d59ca`）：前端薄代理四路由 + `proxyBackend`（SSE 透传）。T08（`039d144`）：REST + `create_app(settings, *, provider, chat_orchestrator)`（orchestrator 已可注入存到 `app.state.chat_orchestrator`，尚无消费者）。T07（`000ca1a`）TennisService；T06（`6605ecb`）cache；T05（`16a0688`）LiveTennisProvider；T04（`20735bd`）Fake；T03（`5ed8a18`）models。
- 当前唯一主任务是 T11：实现 `app/chat/client.py`（`ChatModel` protocol、`FakeChatModel` 脚本化回合 + 运行时默认启发式、`OpenAICompatibleChatModel`（AsyncOpenAI，choose/stream_text，失败→llm_unavailable））、`app/chat/orchestrator.py`（历史守卫→data+固定文案+done 零调用；status→choose→execute→data→最多两轮→stream_text→done；LLM 失败但有 data→固定 fallback text_delta+error(llm_unavailable)；provider 失败→仅 status,error）、扩展 `app/chat/models.py`（ToolCall/ModelTurn/ChatEventType/ChatEvent.to_sse）、`POST /api/v1/chat/stream` SSE 路由（text/event-stream、no-cache no-transform、X-Accel-Buffering: no、AppError→error 事件）。测试优先：`tests/test_chat_orchestrator.py` + `tests/test_chat_api.py`。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

按计划 Task 11 实现有界 tool loop 与 SSE：事件顺序 status→data→text_delta→done；SSE 帧以恰好两个换行结束；第三轮工具请求→invalid_request；Match scope 上下文进 system message；系统消息声明“事实必须来自工具、禁止外部 ID、不可用字段必须承认”；数据优先 fallback（`比赛数据已找到，但 AI 说明暂时不可用。`）。fake LLM 模式下 `create_app` 装配 `ChatOrchestrator(BusinessTools(service), FakeChatModel())`；openai_compatible 模式装配 `OpenAICompatibleChatModel(api_key, base_url, model)`。

### 为什么现在做

P1.5 exit gate：chat 与 REST 同一事实、卡片不依赖 prose、LLM 失败仍留结构化结果、provider 失败不产生虚构事实。T12–T14 前端消费该 SSE 协议。

### 实施依据

- [P1 实施计划 — Task 11](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-11-add-the-openai-compatible-tool-loop-and-sse-route)

### 预计变更范围

- `backend/app/chat/client.py`、`backend/app/chat/orchestrator.py`、`backend/app/chat/models.py`
- `backend/app/api/schemas.py`、`backend/app/api/routes.py`、`backend/app/main.py`
- `backend/tests/test_chat_orchestrator.py`、`backend/tests/test_chat_api.py`

### 完成门

- `uv run pytest -m "not llm_live and not provider_live and not end_to_end_live" -v` 全部通过：事件顺序、两轮上限、fallback 文案、无 data 的 provider 失败、历史守卫零调用、SSE 帧格式、`/api/v1/chat/stream` 端到端（fake 模式）。
- 不调用真实 LLM（真实调用属 T15 opt-in gate）。
- `ROADMAP.md` 的 T11 写入完成提交和验证证据；T12 变为 `ready`。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 11 的测试优先顺序实施，不扩大到 T12。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `9d988ed` | `uv run pytest tests/test_chat_tools.py tests/test_service.py -v` 34/34；全套确定性 suite 90/90 | T10 验收通过 |
| 2026-09-08 | `e6d59ca` | `pnpm test -- lib/server/backend-proxy.test.ts` 8/8；`pnpm typecheck`；`pnpm build` exit 0；`pnpm test:e2e --grep prototype` 10/10 | T09 验收通过 |
| 2026-09-08 | `039d144` | `uv run pytest tests/test_api.py -v` 16/16；全套确定性 suite 75/75 | T08 验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T10 已由 Claude Code（Codex Goal）于 2026-09-08 完成并交接（提交 `9d988ed`）；T11 可领取。

**交接说明：** `BusinessTools.execute(name, arguments, context)` 已冻结（T10 测试为准）。orchestrator 需要的固定文案：历史拒绝 `P1 暂不支持历史比赛结果查询。`；LLM 失败 fallback `比赛数据已找到，但 AI 说明暂时不可用。`。`create_app` 已支持 `chat_orchestrator=` 注入并存到 `app.state.chat_orchestrator`；fake llm 模式下应在工厂内默认装配 orchestrator，注入者优先。SSE 事件的 data payload 用 `result.model_dump(mode="json")`。前端 `/api/chat/stream` 代理已就绪并透传 body。真实 Qwen 凭据只从 `TENNIX_LLM_*` 环境变量读取，绝不写入代码或提交。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | T10 完成：chat 契约、历史守卫与三个业务工具 | `9d988ed` |
| 2026-09-08 | 领取 T10 并置为 in_progress | `9bd26c1` |
| 2026-09-08 | T09 完成：Next.js 薄代理与 vitest 骨架 | `e6d59ca` |
| 2026-09-08 | 领取 T09 并置为 in_progress | `22115c3` |
| 2026-09-08 | T08 完成：确定性 REST API 与错误信封 | `039d144` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
