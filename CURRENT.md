# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 15:33 CST

**当前任务：** T15 — Complete Browser E2E, Live Gates, and the P1 Runbook

**任务状态：** `in_progress`

**当前执行者 / ADE：** Claude Code（Codex Goal：完成 P1 T02–T15，顺序执行，不进 P2）

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `190a948`

**最后验证的产品提交：** `d76821b`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T14 已完成（`d76821b`）：生产路由 `/matches/[matchId]`（内部 ID、getMatch 一次加载+刷新、match scope chat、stats/momentum 永远 P2 不可用、404/错误态）；`/match?status=` 隔离为 preview（`match-preview-data.ts` + `buildPreviewMatch`）；6 张 match 视觉基线逐像素零变化（4 轮 diff 审阅后达成）。
- T13（`4a29050`）：Home 接真数据（4 张 home 基线经审阅更新）。T12（`bd79e84`）：typed API/SSE/view-models/hook。T11（`174866a`）：后端 SSE chat + tool loop。T10（`9d988ed`）：业务工具+历史守卫。T09（`e6d59ca`）：薄代理。T08（`039d144`）：REST。T02–T07 后端基础全完成。
- 当前唯一主任务是 T15（P1.6 收尾）：`backend/tests/test_p1_acceptance.py`（验收矩阵参数化 + RecordingBusinessTools harness + 历史行零调用）、`frontend/e2e/p1-flow.spec.ts`（Home 提问→卡片→打开比赛→上下文问答→刷新 + provider 错误 + 历史 unsupported）、`frontend/e2e/p1.visual.spec.ts`（Home initial/result/error + 生产 Match upcoming/live/P2-unavailable + preview finished，双视口）、opt-in live 套件（backend `tests/live/test_llm_live.py`、`test_provider_live.py`、`test_end_to_end_live.py`；frontend `llm-live.spec.ts`、`end-to-end-live.spec.ts`）、playwright webServer 扩展 `TENNIX_E2E_REAL_*` 环境变量、`docs/runbooks/p1-local.md`、供应商字段泄漏检查（`git grep -nE 'event_key|event_first_player|score\[0\]\[1\]' -- ':!docs'` 业务代码零命中）、Final P1 Completion Gate 人工核对、干净工作区重跑全确定性门。
- 真实 LLM 凭据：用户已授权使用 `/Users/daibin/Documents/Coding/DEUCE-Decision Engine for Uncertain Court Environments/.env` 的 apikey/baseurl（只通过环境变量注入进程，绝不写入仓库/日志/提交）。LiveTennisAPI key 若有同文件或 backend/.env 提供则跑 provider_live，否则如实 skip/unavailable。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

按计划 Task 15 完成 P1 验收层与 runbook：确定性验收（10 个验收问题：9 个 supported 走 tool 路径断言 executed_tool/data/terminal，历史行 unsupported 零调用）；浏览器功能 E2E（fake 后端）；新视觉基线（p1.visual.spec，逐张审阅后入库）；opt-in 真实 LLM/provider/end-to-end 套件（缺凭据则 pytest.skip 并记录）；playwright.config webServer 支持 `TENNIX_E2E_REAL_PROVIDER/REAL_LLM` 标志；runbook 含全部本地命令与模式含义；泄漏检查与 Final Gate 核对记录进 ROADMAP/CURRENT。

### 为什么现在做

P1.6 exit gate：默认全绿 + live gates 在凭据/配额允许时通过 + 无范围膨胀；这是 P1 关闭前的最后一道门。

### 实施依据

- [P1 实施计划 — Task 15](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-15-complete-browser-e2e-live-gates-and-the-p1-runbook)

### 预计变更范围

- `frontend/playwright.config.ts`、`frontend/e2e/p1-flow.spec.ts`、`frontend/e2e/p1.visual.spec.ts`、`frontend/e2e/llm-live.spec.ts`、`frontend/e2e/end-to-end-live.spec.ts`
- `backend/tests/live/test_llm_live.py`、`backend/tests/live/test_provider_live.py`、`backend/tests/live/test_end_to_end_live.py`、`backend/tests/test_p1_acceptance.py`
- `docs/runbooks/p1-local.md`
- （如新基线经审阅）`frontend/e2e/__screenshots__/**`

### 完成门

- 干净工作区重跑：`cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live"` 全过；`cd frontend && pnpm test && pnpm typecheck && pnpm build && pnpm test:e2e` 全过（含新 p1-flow/p1.visual）。
- live gates：凭据可用则跑并记录 pass；不可用则 skip 并记录原因（不伪造）。
- 泄漏检查零业务命中；Final Gate 条目逐条人工核对并记录。
- `ROADMAP.md` T15 done + P1 完成标记；`CURRENT.md` 无活动任务、等待用户决定 P2；P2 保持 planned。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 15 顺序实施：先确定性验收与 E2E，再 live gates 与 runbook，最后 Final Gate 与总控收尾。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `d76821b` | `pnpm test -- components/match-page.test.tsx` 13/13、全套 66/66；typecheck、build 通过；`pnpm test:e2e --grep prototype` 10/10（match 基线零变化） | T14 验收通过 |
| 2026-09-08 | `4a29050` | Home 13/13、全套 53/53；typecheck、build；visual 10/10（home 基线经审阅更新） | T13 验收通过 |
| 2026-09-08 | `bd79e84` | `pnpm test` 40/40；typecheck；build | T12 验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T14 已由 Claude Code（Codex Goal）于 2026-09-08 完成并交接（提交 `d76821b`）；T15 可领取。

**交接说明：** 后端 `create_app` 在 fake llm 模式默认装配 orchestrator；openai_compatible 模式从 `TENNIX_LLM_API_KEY/BASE_URL` 装配 `OpenAICompatibleChatModel`（settings 校验已强制凭据）。playwright webServer 已含 fake 后端（FIXED_NOW=2026-09-08T10:00:00Z）；T15 需按 `TENNIX_E2E_REAL_PROVIDER/REAL_LLM` 扩展 env（real provider 时不加 FIXED_NOW）。前端 E2E 选择器参考：Home 输入 label `继续向 Tennix 提问`、hero 输入 `向 Tennix 询问网球问题`、Match 输入 `向 Tennix 询问本场比赛`、刷新按钮 `刷新比赛数据`、卡片链接 `打开比赛：X 对阵 Y`。fake 数据：live=Sinner vs Ruud（mat_* 内部 ID）、upcoming=Sinner vs Alcaraz 20:30 澳门时间。新视觉基线必须逐张审阅后入库。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | T14 完成：内部 ID Match Page 与上下文 Chat，preview 像素稳定 | `d76821b` |
| 2026-09-08 | 领取 T14 并置为 in_progress | `5ad237e` |
| 2026-09-08 | T13 完成：Home 接真实结构化数据 + 审阅后基线更新 | `4a29050` |
| 2026-09-08 | 领取 T13 并置为 in_progress | `dc221e6` |
| 2026-09-08 | T12 完成：typed frontend API、SSE 解析与 view models | `bd79e84` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
