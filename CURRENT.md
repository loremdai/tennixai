# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 14:34 CST

**当前任务：** T13 — Connect Home to Real Structured Data Without Redesigning It

**任务状态：** `in_progress`

**当前执行者 / ADE：** Claude Code（Codex Goal：完成 P1 T02–T15，顺序执行，不进 P2）

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `f2d46ac`

**最后验证的产品提交：** `bd79e84`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T12 已完成（`bd79e84`）：`lib/api/types.ts`（snake_case DTO + ChatEvent 判别联合）、`lib/api/client.ts`（getPlayers/getMatches/getMatch 解 `data` 信封、ApiError、parseSse 分裂帧/CRLF/多字节安全、streamChat+AbortSignal）、`lib/view-models.ts`（toHomeMatch/toMatchViewModel：澳门时间、`暂未提供`、stale→`数据较旧 · N 秒未刷新`、initials 无国旗 URL）、`hooks/use-chat-stream.ts`（idle|loading|streaming|success|error、12 条历史、abort/cancel/reset）。前端 vitest 40/40、typecheck、build 全过。
- T11（`174866a`）：后端 SSE chat（fake 模式默认装配）。T10（`9d988ed`）：业务工具+历史守卫。T09（`e6d59ca`）：薄代理。T08（`039d144`）：REST。更早 T02–T07 后端基础/模型/provider/cache/service 全部完成。
- 当前唯一主任务是 T13：Home 接真数据、不重设计——保留 `HomePage`/`HomeHero`/`HomeAssistant` DOM 层级与 Tailwind 类；`answerHomeQuestion` 换成 `useChatStream('global')`；卡片只来自 `chat.state.data.matches.map(toHomeMatch)`；slate 用 `getMatches('live')`+`getMatches('upcoming')` 一次性加载与显式刷新回调（绝不加 timer/轮询）；`RecentResultsCard` 显示 `P1 暂不支持历史赛果`；`FollowedPlayersSection` 显示 `关注功能将在后续阶段接入`（无虚构状态）；HomeAssistant status-label map 增加 `unavailable`→`状态待确认`；footer 改为 `数据由 Tennix 服务提供 · 时间为澳门本地时间`。测试优先写 `components/home-page.test.tsx`（只 mock `lib/api/client`）。视觉基线：`pnpm test:e2e --grep prototype` diff 必须是已审阅的数据文案变化且布局几何不变，逐张审阅后才能更新基线。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成，内容为 Next 16 文档提示）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

按计划 Task 13 将 Home 从 mock 路由切换到真实结构化数据：initial question（`?q=`）恰好触发一次；初始 slate 各调用 live/upcoming 一次且无 timer；刷新按钮触发新一对调用；loading 期间禁止重复提交；历史问题渲染 unsupported 且无卡片；stale 徽章可见；空列表保留 section 外壳与事实性中文空文案；API 失败渲染 typed 重试文案；home-data.ts 保留 `homeExampleQueries` 与阶段营销标签，删除 `answerHomeQuestion`、假比赛数组、假 recent results、假 followed-player 状态数据（生产路径）。

### 为什么现在做

P1.4 exit gate：Home → Match 真实链路 + 内部 ID + 视觉回归受控；T14 Match Page 依赖 Home 卡片 href `/matches/{id}`。

### 实施依据

- [P1 实施计划 — Task 13](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-13-connect-home-to-real-structured-data-without-redesigning-it)

### 预计变更范围

- `frontend/components/home-page.tsx`、`frontend/components/home/home-assistant.tsx`、`frontend/components/home/home-data.ts`、`frontend/components/home/home-match-sections.tsx`、`frontend/components/home/home-player-sections.tsx`、`frontend/app/page.tsx`
- `frontend/components/home-page.test.tsx`
- （如基线经审阅确认）`frontend/e2e/__screenshots__/**`

### 完成门

- `pnpm test -- components/home-page.test.tsx` 通过；`pnpm typecheck` 通过。
- `pnpm test:e2e --grep prototype`：通过，或 diff 仅为已审阅的数据文案变化且布局几何不变；更新基线必须逐张审阅并记录理由。
- 生产 Home 路径无 setInterval/setTimeout 轮询、无 mock 路由残留。
- `ROADMAP.md` 的 T13 写入完成提交和验证证据；T14 变为 `ready`。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 13 的测试优先顺序实施，不扩大到 T14。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `bd79e84` | `pnpm test` 40/40；`pnpm typecheck` 通过；`pnpm build` exit 0 | T12 验收通过 |
| 2026-09-08 | `174866a` | `uv run pytest tests/test_chat_orchestrator.py tests/test_chat_api.py -v` 17/17；全套确定性 suite 107/107 | T11 验收通过（无真实 LLM 调用） |
| 2026-09-08 | `9d988ed` | `uv run pytest tests/test_chat_tools.py tests/test_service.py -v` 34/34；全套确定性 suite 90/90 | T10 验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T12 已由 Claude Code（Codex Goal）于 2026-09-08 完成并交接（提交 `bd79e84`）；T13 可领取。

**交接说明：** T13 只 mock `frontend/lib/api/client.ts`（`vi.mock`），断言行为不测实现细节。既有 Home 组件从 `home-data.ts` 导入假数据：`featuredMatch`、`liveMatches`、`upcomingMatches`、`followedPlayers`、`recentResults`、`answerHomeQuestion`。HomeMatchResult 类型与 `toHomeMatch` 输出的 HomeMatchViewModel 字段相近但不同（location/currentSet/elapsed/actionLabel 不在 view model 中）——组件 props 改为消费 HomeMatchViewModel，删除或改造 HomeMatchResult。视觉真源是 10 张基线：布局几何（间距、字体、颜色、栅格）必须不变，仅数据文案允许变化且需逐张审阅。`?q=` initial question 由 `app/page.tsx` 读取 searchParams 传入。fake 后端 `TENNIX_FIXED_NOW=2026-09-08T10:00:00Z` 时 Home 数据为 Sinner vs Alcaraz（scheduled 20:30 澳门）与 Sinner vs Ruud（live）。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | T12 完成：typed frontend API、SSE 解析与 view models | `bd79e84` |
| 2026-09-08 | 领取 T12 并置为 in_progress | `e7fd969` |
| 2026-09-08 | T11 完成：OpenAI-compatible tool loop 与 SSE 路由 | `174866a` |
| 2026-09-08 | 领取 T11 并置为 in_progress | `3e34314` |
| 2026-09-08 | T10 完成：chat 契约、历史守卫与三个业务工具 | `9d988ed` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
