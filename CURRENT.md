# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 14:23 CST

**当前任务：** T12 — Add Typed Frontend API, SSE Parsing, and View Models

**任务状态：** `in_progress`

**当前执行者 / ADE：** Claude Code（Codex Goal：完成 P1 T02–T15，顺序执行，不进 P2）

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `1d547ec`

**最后验证的产品提交：** `174866a`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T11 已完成（`174866a`）：`app/chat/client.py`（`ChatModel` protocol、`FakeChatModel` 脚本回合+运行时启发式、`OpenAICompatibleChatModel` AsyncOpenAI→llm_unavailable）、`app/chat/orchestrator.py`（历史守卫零调用、status→data→text_delta→done、两轮上限、数据优先 fallback `比赛数据已找到，但 AI 说明暂时不可用。`）、`POST /api/v1/chat/stream` SSE（no-cache no-transform、X-Accel-Buffering: no）；fake llm 模式下 `create_app` 默认装配 orchestrator。
- T10（`9d988ed`）：chat 契约 + BusinessTools + is_historical_query（历史拒绝文案 `P1 暂不支持历史比赛结果查询。`）。T09（`e6d59ca`）：前端薄代理。T08（`039d144`）：REST + 错误信封。更早：T07 service、T06 cache、T05 LiveTennisProvider、T04 Fake、T03 models、T02 FastAPI 基础、T01 视觉基线。
- 当前唯一主任务是 T12：前端 typed API——`lib/api/types.ts`（snake_case DTO + ChatEvent 判别联合）、`lib/api/client.ts`（getPlayers/getMatches/getMatch 只解 `data`、parseSse 处理跨 chunk 分裂帧、streamChat POST + AbortSignal、ApiError）、`lib/view-models.ts`（toHomeMatch/toMatchViewModel：Asia/Macau 本地化、null→`暂未提供`、scheduled→upcoming、cancelled/postponed/unknown→unavailable、freshness label）、`hooks/use-chat-stream.ts`（idle|loading|streaming|success|error、12 条消息历史、AbortController、绝不从 prose 派生卡片）。测试优先：client.test.ts、view-models.test.ts、use-chat-stream.test.tsx。不改动 Home/Match 组件（T13/T14）。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

按计划 Task 12 实现：DTO 类型与后端字段一一对应（无 provider ID 字段可表达）；`parseSse` 用单个 TextDecoder 流式解码、保留不完整 buffer、按 `/\r?\n\r?\n/` 分帧、合并重复 data: 行、忽略注释/空行；非 2xx 先抛 `ApiError`（code/details）再解析；view-model 映射用 `Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Macau' })`，`/matches/${encodeURIComponent(id)}` 链接，initials 而非合成国旗 URL；`useChatStream` 精确接口（state/send/cancel/reset），新请求 abort 旧请求，卸载 abort 且不再 setState。

### 为什么现在做

T13 Home 与 T14 Match Page 都只消费这些 typed API 与 view models；SSE 解析的跨 chunk 分裂与 abort 行为必须先有确定性测试。

### 实施依据

- [P1 实施计划 — Task 12](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-12-add-typed-frontend-api-sse-parsing-and-view-models)

### 预计变更范围

- `frontend/lib/api/types.ts`、`frontend/lib/api/client.ts`、`frontend/lib/api/client.test.ts`
- `frontend/lib/view-models.ts`、`frontend/lib/view-models.test.ts`
- `frontend/hooks/use-chat-stream.ts`、`frontend/hooks/use-chat-stream.test.tsx`

### 完成门

- `pnpm test -- lib/api/client.test.ts lib/view-models.test.ts hooks/use-chat-stream.test.tsx` 通过（含分裂帧、abort、stale 标签、`暂未提供`、比分 player-major 行映射）。
- `pnpm typecheck` 通过。
- 不改动 Home/Match 组件与视觉基线（T13/T14）；无自动轮询/timer。
- `ROADMAP.md` 的 T12 写入完成提交和验证证据；T13 变为 `ready`。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 12 的测试优先顺序实施，不扩大到 T13。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `174866a` | `uv run pytest tests/test_chat_orchestrator.py tests/test_chat_api.py -v` 17/17；全套确定性 suite 107/107 | T11 验收通过（无真实 LLM 调用） |
| 2026-09-08 | `9d988ed` | `uv run pytest tests/test_chat_tools.py tests/test_service.py -v` 34/34；全套确定性 suite 90/90 | T10 验收通过 |
| 2026-09-08 | `e6d59ca` | `pnpm test -- lib/server/backend-proxy.test.ts` 8/8；`pnpm typecheck`；`pnpm build` exit 0；`pnpm test:e2e --grep prototype` 10/10 | T09 验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T11 已由 Claude Code（Codex Goal）于 2026-09-08 完成并交接（提交 `174866a`）；T12 可领取。

**交接说明：** 后端 SSE 协议已冻结（`backend/tests/test_chat_api.py` 为准）：事件 `status|data|text_delta|done|error`；`data` payload 为 `{kind: matches|match|unsupported, matches: MatchDto[]}`；`error` payload 为 `{code,message,details}`；帧以恰好两个 `\n` 结束；REST DTO 字段名 snake_case（`scheduled_at`、`sets_won`、`player1_games`、`server_player_id`、`freshness.{provider,source_updated_at,observed_at,is_stale,age_seconds}`）；REST 信封 `{data: ...}`，错误信封 `{error:{...},request_id}`。前端调用一律走同源 `/api/*`（T09 代理已就绪），不得直连 FastAPI。hook 测试用 `@testing-library/react` + jsdom（vitest 默认环境已是 jsdom；server-only 测试用 `// @vitest-environment node` docblock）。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | T11 完成：OpenAI-compatible tool loop 与 SSE 路由 | `174866a` |
| 2026-09-08 | 领取 T11 并置为 in_progress | `3e34314` |
| 2026-09-08 | T10 完成：chat 契约、历史守卫与三个业务工具 | `9d988ed` |
| 2026-09-08 | 领取 T10 并置为 in_progress | `9bd26c1` |
| 2026-09-08 | T09 完成：Next.js 薄代理与 vitest 骨架 | `e6d59ca` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
