# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-09 17:46 CST

**当前任务：** T21 — Extend the Canonical Domain and Provider Contracts

**任务状态：** `in_progress`

**当前执行者 / ADE：** Claude Code / Claude Code

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**最近完成任务提交：** `969c7ec`

**最后验证的产品提交：** `fdb0131`

**T21 起始提交：** `f574b1a`

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
- T20 已完成且未实现 P2 产品代码；下一任务是 T21 canonical domain/provider contracts，必须按启动入口另行领取。
- M01 已把本地配置统一迁移到根目录 `.env`；FastAPI、Next.js、Playwright 和真实测试均从该入口读取，Next 进程只接收 `TENNIX_BACKEND_URL`，不接收后端凭据。该迁移不改变 P2 范围、任务顺序或产品架构，T21 仍是下一任务。
- 已知非 T17 限制：LiveTennisAPI 的 `/players?search` 当前不能把中文显示名“郑钦文”直接映射到 `Qinwen Zheng`；canonical English name 查询已通过，中文别名/名称归一化需另立任务批准。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；保留原样。

## 当前任务

### T21 — Extend the Canonical Domain and Provider Contracts

- **状态：** `in_progress`
- **执行者 / ADE：** Claude Code / Claude Code
- **分支：** `main`
- **起始提交：** `f574b1a`
- **领取时间：** 2026-09-09 17:46 CST
- **范围：** 按 [P2 实施计划 T21](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t21-extend-the-canonical-domain-and-provider-contracts)：新增 P2 canonical enums 与模型（CircuitTier/Gender/Discipline/ConnectionStatus/CapabilityStatus/PointEvent/MatchStatistic/MomentumObservation/DataQuality/HeadToHead/MatchSnapshot/ProviderLiveEnvelope），identity 契约改为 async，扩展查询 provider 与 live-feed 协议，并保持 P1 provider 回归门通过。
- **阻塞：** 无。

## 最近完成任务

### M01 — Unify Root Environment Entry

- **状态：** `done`
- **执行者 / ADE：** Codex
- **分支：** `main`
- **起始提交：** `aece736`
- **领取时间：** 2026-09-09 17:22 CST
- **完成提交：** `969c7ec`
- **范围：** 把 backend、frontend 和真实测试使用的本地配置统一到仓库根目录 `.env`；迁移现有值但不提交凭据，并同步唯一 `.env.example`、启动入口、运行文档和 P2 计划中的配置路径。
- **完成事实：** 原 `backend/.env` 与 `frontend/.env.local` 已无损合并到权限 `0600`、受 Git 忽略的根目录 `.env`，旧本地文件及两个子目录模板已移除；根目录 `.env.example` 是唯一安全模板。FastAPI 使用绝对根路径；Next 只提取 server-only backend URL；Playwright 将完整配置仅传给 FastAPI 子进程；真实 pytest 门通过 `Settings` 读取根文件。
- **验证门：** TDD 回归先 2 failed 后 2 passed；backend 确定性 128 passed/6 deselected；frontend 72/72、typecheck、build；Playwright 最终 34 passed/4 skipped，视觉基线未更新；路径、`0600` 权限、Git ignore、API-Tennis key 格式、Next 最小权限和 tracked 64 位敏感模式扫描均通过。
- **阻塞：** 无。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-09 | `969c7ec` | root-env TDD 2/2；backend 128 passed；frontend 72/72 + typecheck/build；Playwright 34 passed/4 skipped；路径/权限/ignore/最小权限/敏感模式检查 | M01 完成；根目录 `.env` 成为唯一配置入口，T21 仍 ready |
| 2026-09-09 | `b7921c0` | P2 规格/计划覆盖审查；12 个任务和 60 个步骤结构核对；占位符/敏感模式扫描无命中；本地链接存在；whitespace 与 diff check 通过 | T20 完成；P2.0 关闭，T21 ready |
| 2026-09-09 | `fdb0131` | Home 单元 72/72；typecheck/build；长 Markdown 结构化卡片视口回归桌面/移动 12/12；完整 Playwright 34 passed/4 skipped，视觉基线通过 | T19 完成；回答完成后结构化比赛卡片保持可见 |
| 2026-09-09 | `5572960` | TDD 先行测试验证两处原文显示失败；修复后 frontend 71/71 + typecheck + build；隔离服务 Playwright 10/10；真实浏览器 `strong=10`、`ul=1`、无 `**` | T18 完成；Home/Match 问答 Markdown 展示通过 |
| 2026-09-08 | `69c8238` | backend 确定性 126 passed；frontend 69/69 + typecheck + build；隔离 fake 服务的 Playwright 32 passed/4 skipped；真实 REST upcoming 50 场与 Qinwen Zheng 指定球员查询；真实浏览器 Home→Match→上下文问答 | T17 完成；P1 当前实现门通过 |
| 2026-09-08 | `5dcaa6a` | backend 确定性 124 passed；frontend 66/66 + typecheck + build + E2E 32 passed/4 skipped；provider_live 1/1；llm_live 4/4；end_to_end_live 1/1；真实浏览器 end-to-end 2/2；手动 Djokovic SSE 完整结束 | T16 与 P1 真实运行时验收通过 |
| 2026-09-08 | `98075ef` | backend 确定性 suite 117 passed；frontend 66/66 + typecheck + build + e2e 32 passed/4 skipped；验收矩阵 10/10；llm_live 4/4 + 浏览器 2/2（真实 Qwen）；provider/end-to-end live 如实 skip；泄漏检查业务零命中；Final Gate 八条核对 | T15 与 P1 整体验收通过 |
| 2026-09-08 | `d76821b` | match-page 13/13、全套 66/66；visual 10/10（match 基线零变化） | T14 验收通过 |
| 2026-09-08 | `4a29050` | Home 13/13、全套 53/53；visual 10/10（home 基线经审阅更新） | T13 验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** M01 已由 Codex 于 2026-09-09 在 `main` 完成，实现提交 `969c7ec`；T21 已于 2026-09-09 17:46 CST 由 Claude Code 在 `main` 领取，起始提交 `f574b1a`。

**交接说明：** 接手 T21 前完整阅读 [P2 设计规格](./docs/superpowers/specs/2026-09-09-tennixai-p2-live-match-intelligence-design.md) 和 [P2 实施计划](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md#t21-extend-the-canonical-domain-and-provider-contracts)。所有 ADE 只使用根目录 `.env`；API-Tennis 凭据变量为 `TENNIX_API_TENNIS_API_KEY`，不得写入代码、文档、fixture、日志、提交或聊天输出。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-09 | 领取 T21：扩展 canonical domain 与 provider contracts | `f574b1a` 起始 |
| 2026-09-09 | M01 完成：backend/frontend/Playwright/真实测试统一使用根目录 `.env` | `969c7ec` |
| 2026-09-09 | 领取 M01：本地配置统一迁移到根目录 `.env` | `aece736` 起始 |
| 2026-09-09 | T20 完成：P2 设计规格、T21–T32 实施计划与三份总控落盘 | `b7921c0` |
| 2026-09-09 | 领取 T20：冻结 P2 Live Match Intelligence 设计与实施路线 | `17f4d89` 起始 |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
