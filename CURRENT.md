# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-09 09:14 CST

**当前任务：** T18 — Render Markdown in Conversational Answers

**任务状态：** `in_progress`

**当前执行者 / ADE：** Codex

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `2fdd983`

**最后验证的产品提交：** `69c8238`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- P1/T16 已于 2026-09-08 完成并推送：fake 模式全链路确定性地跑通；真实 LiveTennisAPI provider、真实 Qwen 单项与组合 chat、Next 同源代理浏览器门均通过。
- T17 已于 2026-09-08 完成并推送：upcoming 改用当前 `/matches?status=upcoming` canonical 映射，指定球员使用供应商过滤，Home 的 live/upcoming 支持单侧失败降级，429 保留重试提示；实现提交为 `69c8238`。
- T16 已确认的事实：真实 provider 可返回 50 场 live matches；完整 `data` SSE 仍保留全部 canonical matches；LLM 只接收最多 12 条摘要并有持久化的 45 秒总时限；真实 Djokovic 查询不再因重复实名/组合名报歧义，空赛程会诚实返回并以 `done` 结束。
- 最终验证：backend `pytest -m "not llm_live and not provider_live and not end_to_end_live"` 126 passed；frontend `pnpm test` 69/69、`pnpm typecheck`、`pnpm build` 通过；隔离 fake 服务下完整 Playwright `32 passed + 4 skipped`。
- 真实 key 验收：REST 全局 upcoming 返回 50 场；以 `Qinwen Zheng` 查询返回 Rybakina vs Zheng 的 US Open WTA 1/4 决赛；浏览器完成 Home → 结构化比赛卡片 → Match Page → 上下文问答，返回 2026-09-09 23:00 澳门时间。
- 视觉：prototype 10 张基线（home 4 张经 T13/T15 审阅更新，match 6 张自 T01 起零变化）+ p1.visual 12 张新基线（逐张审阅入库）。
- Final P1 Completion Gate 八条已人工核对（凭据仅服务端、无自动轮询、无超范围实现、结构化事实来源、供应商/LLM 失败降级、预览与生产路由分离、双视口视觉一致、泄漏检查业务代码零命中）；T16/T17 额外通过真实 provider、LLM、组合及浏览器门。
- 本地运行与 opt-in 真实门命令见 [docs/runbooks/p1-local.md](./docs/runbooks/p1-local.md)。
- P2（Live Match Intelligence）保持 `planned`：需要 PostgreSQL/Redis/API-Tennis 等另行批准的设计；当前没有领取中的任务。
- 已知非 T17 限制：LiveTennisAPI 的 `/players?search` 当前不能把中文显示名“郑钦文”直接映射到 `Qinwen Zheng`；canonical English name 查询已通过，中文别名/名称归一化需另立任务批准。
- T18 于 2026-09-09 09:14 领取：修复全局/比赛问答中的 Markdown 原文显示，并用回归测试与浏览器验收确认粗体、列表和段落呈现；不改变结构化比赛卡片与原型布局。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；保留原样。

## 当前任务

执行边界：只修复问答 prose 的 Markdown 渲染与安全输出，覆盖全局助手和比赛上下文助手；保留结构化比赛卡片的现有数据边界，不引入新的 Markdown 依赖或 P2 能力。

完成门：找到并证明原文显示的责任组件；添加最小回归测试；真实浏览器中确认 `**粗体**`、无序列表和普通段落正确渲染且不显示 Markdown 标记；确定性前端测试、typecheck、build 和相关 Playwright 流程通过；完成后更新三份总控并推送。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `69c8238` | backend 确定性 126 passed；frontend 69/69 + typecheck + build；隔离 fake 服务的 Playwright 32 passed/4 skipped；真实 REST upcoming 50 场与 Qinwen Zheng 指定球员查询；真实浏览器 Home→Match→上下文问答 | T17 完成；P1 当前实现门通过 |
| 2026-09-08 | `5dcaa6a` | backend 确定性 124 passed；frontend 66/66 + typecheck + build + E2E 32 passed/4 skipped；provider_live 1/1；llm_live 4/4；end_to_end_live 1/1；真实浏览器 end-to-end 2/2；手动 Djokovic SSE 完整结束 | T16 与 P1 真实运行时验收通过 |
| 2026-09-08 | `98075ef` | backend 确定性 suite 117 passed；frontend 66/66 + typecheck + build + e2e 32 passed/4 skipped；验收矩阵 10/10；llm_live 4/4 + 浏览器 2/2（真实 Qwen）；provider/end-to-end live 如实 skip；泄漏检查业务零命中；Final Gate 八条核对 | T15 与 P1 整体验收通过 |
| 2026-09-08 | `d76821b` | match-page 13/13、全套 66/66；visual 10/10（match 基线零变化） | T14 验收通过 |
| 2026-09-08 | `4a29050` | Home 13/13、全套 53/53；visual 10/10（home 基线经审阅更新） | T13 验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T18 已由 Codex 于 2026-09-09 在 `main` 领取，起始提交 `2fdd983`；正在定位问答 Markdown 原文显示问题。

**交接说明：** 本地持久配置位于被忽略的 `backend/.env` 与 `frontend/.env.local`，未入库；`backend/.env` 含 `TENNIX_LLM_TIMEOUT_SECONDS=45` 与当前可用的 LiveTennisAPI key。T17 已完成真实 provider、真实 LLM 与浏览器验收；服务可按 [docs/runbooks/p1-local.md](./docs/runbooks/p1-local.md) 启动。已知视觉/StrictMode 说明保留在 T15 证据中。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-09 | 领取 T18：问答 Markdown 原文显示修复 | `2fdd983` 起始 |
| 2026-09-08 | T17 完成：真实 upcoming provider、指定球员过滤、局部失败与 429 友好降级 | `69c8238` |
| 2026-09-08 | 领取并规划 T17 | `ef85ea3` / `da27574` |
| 2026-09-08 | T16 完成：真实 live chat 上下文/超时/球员消歧硬化 | `5dcaa6a` |
| 2026-09-08 | T15 完成：验收矩阵、浏览器 E2E、live 门、runbook；P1 关闭 | `98075ef` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
