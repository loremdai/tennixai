# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 14:57 CST

**当前任务：** T14 — Add the Internal-ID Match Page and Contextual Chat

**任务状态：** `ready`

**当前执行者 / ADE：** `unassigned`

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `unassigned`（领取任务时记录当时的 HEAD）

**最后验证的产品提交：** `4a29050`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T13 已完成（`4a29050`）：Home 全链路接真数据——`useChatStream('global')` + slate（live/upcoming 各一次调用、显式刷新、无轮询）；卡片只来自 `chat.state.data.matches.map(toHomeMatch)`；RecentResults/FollowedPlayers 占位文案；footer 新文案；playwright webServer 已含 fake 后端（`TENNIX_FIXED_NOW=2026-09-08T10:00:00Z`）。4 张 home 视觉基线经逐张 diff 审阅后更新（真数据替换 mock + 占位文案），6 张 match 基线零变化。
- T12（`bd79e84`）：typed API/SSE/view-models/useChatStream。T11（`174866a`）：后端 SSE chat。T10（`9d988ed`）：业务工具+历史守卫。T09（`e6d59ca`）：薄代理。T08（`039d144`）：REST。后端 T02–T07 全完成。
- 当前唯一主任务是 T14：生产路由 `/matches/[matchId]`（内部 ID、`getMatch` 一次加载+显式刷新、`useChatStream('match', matchId)` 上下文问答、stats/momentum 永远 `P2 数据暂不可用` FutureModule）；`/match?status=` 隔离为视觉预览（`match-preview-data.ts` + `buildPreviewMatch(status)`，仅 preview=true 可渲染样例统计/动量）；match 组件改为 props 驱动（MatchHero/MatchMain/MatchSidebar 接收 `MatchViewModel`）。测试优先写 `components/match-page.test.tsx`。视觉门：`pnpm test:e2e --grep prototype` 的 `/match?status=` 截图必须像素级稳定（预览路径数据未变）。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成，Next 16 文档提示）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

按计划 Task 14：新建 `app/matches/[matchId]/page.tsx`（await params，渲染 `<MatchPage matchId={matchId} />`）；`MatchPage` 双入口 props（`{ matchId }` 或 `{ previewMatch }`）；生产路径：mount 加载一次 + 刷新动作再加载；chat 始终 `scope=match` + 当前内部 ID（用户 prompt 不含上下文）；`data` 事件只更新结构化结果/高亮，`text_delta` 更新 prose；404 状态、provider 错误重试；stats/points/momentum 生产路由一律 FutureModule `P2 数据暂不可用`；`/match?status=` 走 `buildPreviewMatch(status)` + preview=true 保留原原型视觉。从 `match-data.ts` 移出全部静态样例到 `match-preview-data.ts`。

### 为什么现在做

P1 成功标准：Home 卡片 → 内部 ID Match Page → 上下文问答闭环；生产路径不得出现虚构比分/胜者/P2 统计。

### 实施依据

- [P1 实施计划 — Task 14](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-14-add-the-internal-id-match-page-and-contextual-chat)

### 预计变更范围

- `frontend/app/matches/[matchId]/page.tsx`、`frontend/components/match/match-preview-data.ts`
- `frontend/app/match/page.tsx`、`frontend/components/match-page.tsx`、`frontend/components/match/{match-data,match-hero,match-main,match-sidebar}.tsx`
- `frontend/components/match-page.test.tsx`

### 完成门

- `pnpm test -- components/match-page.test.tsx`、`pnpm typecheck`、`pnpm build` 通过。
- `pnpm test:e2e --grep prototype` 10/10 且 `/match?status=` 截图像素稳定（预览未变）；如 home/match 基线需更新必须逐张审阅。
- 生产分支零硬编码胜者/比分/赛事/时间/发球句；preview 与生产隔离有测试。
- `ROADMAP.md` 的 T14 写入完成提交和验证证据；T15 变为 `ready`。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 14 的测试优先顺序实施，不扩大到 T15。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `4a29050` | `pnpm test -- components/home-page.test.tsx` 13/13、全套 53/53；`pnpm typecheck`；`pnpm build` exit 0；`pnpm test:e2e --grep prototype` 10/10（home 基线经审阅更新，match 零变化） | T13 验收通过 |
| 2026-09-08 | `bd79e84` | `pnpm test` 40/40；`pnpm typecheck`；`pnpm build` exit 0 | T12 验收通过 |
| 2026-09-08 | `174866a` | chat orchestrator/API 17/17；全套确定性 suite 107/107 | T11 验收通过（无真实 LLM） |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T13 已由 Claude Code（Codex Goal）于 2026-09-08 完成并交接（提交 `4a29050`）；T14 可领取。

**交接说明：** 后端 `/api/matches/{match_id}` 与 `/api/chat/stream`（match scope）已就绪并经测试；前端 `getMatch`/`useChatStream`/`toMatchViewModel` 已就绪（T12）。Match 组件现状从 `match-data.ts` 读静态样例（players/matchMeta/liveScore/finishedScore/matchStats/momentumData/recentPoints）——T14 将它们整体移入 `match-preview-data.ts` 并加 `buildPreviewMatch(status)`；`match-data.ts` 只留共享 labels/enums。`/match?status=live` 等三态的视觉基线当前通过，预览路径改造后必须保持像素稳定。生产路由 stats/momentum 用 `future-module.tsx` 的 FutureModule。chat 高亮：MatchHighlight 来自 data 事件（server→'server'、score→'score' 等），text 只进 prose。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | T13 完成：Home 接真实结构化数据 + 审阅后基线更新 | `4a29050` |
| 2026-09-08 | 领取 T13 并置为 in_progress | `dc221e6` |
| 2026-09-08 | T12 完成：typed frontend API、SSE 解析与 view models | `bd79e84` |
| 2026-09-08 | 领取 T12 并置为 in_progress | `e7fd969` |
| 2026-09-08 | T11 完成：OpenAI-compatible tool loop 与 SSE 路由 | `174866a` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
