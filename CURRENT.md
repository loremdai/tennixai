# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 15:53 CST

**当前任务：** 无（P1 已全部完成；等待用户决定是否启动 P2 设计）

**任务状态：** `idle`

**当前执行者 / ADE：** `unassigned`

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `n/a`

**最后验证的产品提交：** `98075ef`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- P1（T01–T15）已于 2026-09-08 全部完成并推送：fake 模式全链路（LiveTennisAPI adapter 边界 → canonical models → TennisService → REST/SSE chat → Next 薄代理 → Home/Match UI）确定性地跑通；真实 Qwen 经 opt-in 门验证（后端 4/4、浏览器 2/2）；LiveTennisAPI live 门因仓库外无 key 如实 skip。
- 最终验证（干净工作区）：backend `pytest -m "not llm_live and not provider_live and not end_to_end_live"` 117 passed；frontend `pnpm test` 66/66、`pnpm typecheck` 通过、`pnpm build` exit 0、`pnpm test:e2e` 32 passed + 4 skipped（live specs）；连续两次全 E2E 32/32 稳定。
- 视觉：prototype 10 张基线（home 4 张经 T13/T15 审阅更新，match 6 张自 T01 起零变化）+ p1.visual 12 张新基线（逐张审阅入库）。
- Final P1 Completion Gate 八条已人工核对（凭据仅服务端、无自动轮询、无超范围实现、结构化事实来源、供应商/LLM 失败降级、预览与生产路由分离、双视口视觉一致、泄漏检查业务代码零命中）。
- 本地运行与 opt-in 真实门命令见 [docs/runbooks/p1-local.md](./docs/runbooks/p1-local.md)。
- P2（Live Match Intelligence）保持 `planned`：需要 PostgreSQL/Redis/API-Tennis 等另行批准的设计；是否启动由用户决定。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；保留原样。

## 当前任务

无。P1 没有剩余实现任务。若用户决定启动 P2，应先做 P2 设计（含 API-Tennis 能力验证、存储 schema 与回滚策略、轮询配额模型），再建立新的任务登记表。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `98075ef` | backend 确定性 suite 117 passed；frontend 66/66 + typecheck + build + e2e 32 passed/4 skipped；验收矩阵 10/10；llm_live 4/4 + 浏览器 2/2（真实 Qwen）；provider/end-to-end live 如实 skip；泄漏检查业务零命中；Final Gate 八条核对 | T15 与 P1 整体验收通过 |
| 2026-09-08 | `d76821b` | match-page 13/13、全套 66/66；visual 10/10（match 基线零变化） | T14 验收通过 |
| 2026-09-08 | `4a29050` | Home 13/13、全套 53/53；visual 10/10（home 基线经审阅更新） | T13 验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** P1 已由 Claude Code（Codex Goal）于 2026-09-08 完成（最终提交 `98075ef`）。没有活动实现任务；下一步行动等待用户决定（是否启动 P2 设计）。

**交接说明：** 全链路以 fake 模式为默认确定性门；真实 LLM 凭据从环境变量注入（本次使用 DEUCE 项目的 key/baseurl，仅经 env，未入库）；LiveTennisAPI key 尚未配置，`provider_live`/`end_to_end_live` 与浏览器 end-to-end 门处于 skip 状态——拿到 key 后按 runbook 第 3 节复跑即可。已知小瑕疵记录：dev StrictMode 下 initial question 会先发一次被 abort 的请求再重发（生产单次）；视觉 spec 需 `window.scrollTo(0,0)` 与隐藏 `nextjs-portal` 保证 sticky 元素与 dev overlay 不干扰基线。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
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
