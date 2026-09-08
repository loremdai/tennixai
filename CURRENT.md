# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 18:30 CST

**当前任务：** T16 — Harden the Real Live Runtime

**任务状态：** `in_progress`

**当前执行者 / ADE：** Codex（当前 ADE）

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `93601bd`

**最后验证的产品提交：** `98075ef`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- P1 核心实现（T01–T15）已完成并推送：fake 模式全链路确定性地跑通，真实 Qwen 单项门验证（后端 4/4、浏览器 2/2）；T16 正在补齐真实 LiveTennisAPI + LLM 组合链路的运行时边界。
- T16 已确认的事实：真实 LiveTennisAPI 可返回 50 场 live matches；provider_live 通过；两套持久/备用 LLM 配置的 llm_live 均通过；完整 live chat 因把约 50 KB 全量 tool 结果交给 LLM 且无总时限而长时间不结束；`Djokovic` 因重复实名与组合名返回 `ambiguous_player`。
- 最终验证（干净工作区）：backend `pytest -m "not llm_live and not provider_live and not end_to_end_live"` 117 passed；frontend `pnpm test` 66/66、`pnpm typecheck` 通过、`pnpm build` exit 0、`pnpm test:e2e` 32 passed + 4 skipped（live specs）；连续两次全 E2E 32/32 稳定。
- 视觉：prototype 10 张基线（home 4 张经 T13/T15 审阅更新，match 6 张自 T01 起零变化）+ p1.visual 12 张新基线（逐张审阅入库）。
- Final P1 Completion Gate 八条已人工核对（凭据仅服务端、无自动轮询、无超范围实现、结构化事实来源、供应商/LLM 失败降级、预览与生产路由分离、双视口视觉一致、泄漏检查业务代码零命中）。
- 本地运行与 opt-in 真实门命令见 [docs/runbooks/p1-local.md](./docs/runbooks/p1-local.md)。
- P2（Live Match Intelligence）保持 `planned`：需要 PostgreSQL/Redis/API-Tennis 等另行批准的设计；是否启动由用户决定。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；保留原样。

## 当前任务

T16 只处理真实运行时硬化，不扩大到 P2：

- 按 [T16 实施计划](./docs/superpowers/plans/2026-09-08-tennixai-t16-real-runtime-hardening.md) 先写失败测试，再实现 LLM 上下文裁剪、可配置总时限与球员消歧。
- 保留完整 `data` SSE 结构化结果，压缩范围只作用于发给 LLM 的 tool message。
- 完成后复跑确定性 suite、真实 provider/LLM/组合门和浏览器真实门；按实际结果更新三份总控。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `98075ef` | backend 确定性 suite 117 passed；frontend 66/66 + typecheck + build + e2e 32 passed/4 skipped；验收矩阵 10/10；llm_live 4/4 + 浏览器 2/2（真实 Qwen）；provider/end-to-end live 如实 skip；泄漏检查业务零命中；Final Gate 八条核对 | T15 与 P1 整体验收通过 |
| 2026-09-08 | `d76821b` | match-page 13/13、全套 66/66；visual 10/10（match 基线零变化） | T14 验收通过 |
| 2026-09-08 | `4a29050` | Home 13/13、全套 53/53；visual 10/10（home 基线经审阅更新） | T13 验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** P1 核心实现由 Claude Code（Codex Goal）于 2026-09-08 完成（基线提交 `98075ef`）；Codex 于 2026-09-08 从 `93601bd` 领取 T16，当前在 `main` 进行真实运行时硬化。

**交接说明：** T16 的本地持久配置位于被忽略的 `backend/.env` 与 `frontend/.env.local`，未入库；当前配置下真实 provider 与单项 LLM 均可用。组合门尚未通过，修复前不得把 P1 标记为整体 done。已知视觉/StrictMode 说明保留在 T15 证据中。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无，T16 正在执行。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | 领取 T16：真实 live chat 上下文/超时/球员消歧硬化 | `93601bd`（起始） |
| 2026-09-08 | T15 完成：验收矩阵、浏览器 E2E、live 门、runbook；P1 关闭 | `98075ef` |
| 2026-09-08 | 领取 T15 并置为 in_progress | `8019ddb` |
| 2026-09-08 | T14 完成：内部 ID Match Page 与上下文 Chat，preview 像素稳定 | `d76821b` |
| 2026-09-08 | 领取 T14 并置为 in_progress | `5ad237e` |
| 2026-09-08 | T13 完成：Home 接真实结构化数据 + 审阅后基线更新 | `4a29050` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
