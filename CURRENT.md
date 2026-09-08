# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 13:28 CST

**当前任务：** T03 — Define Canonical Models and In-Memory Identity

**任务状态：** `in_progress`

**当前执行者 / ADE：** Claude Code（Codex Goal：完成 P1 T02–T15，顺序执行，不进 P2）

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `989692e`

**最后验证的产品提交：** `8b15efe`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T02 已完成（`8b15efe`）：`backend/` FastAPI 基础已建立——typed `Settings`（`TENNIX_*`，fake/live 凭据校验）、`AppError`、`GET /api/v1/health`、`X-Request-ID` 中间件、`create_app()` 工厂、uv/pytest 骨架与 `.env.example`（前后端各一份，均无真实凭据）。
- T01 已完成：Home 与 Match 三态在桌面/移动视口的 10 张视觉基线已入 Git（最终版 `c035f5a`），visual suite 可重复通过。
- 历史提醒：首版基线 `d13d6dd` 混入 Next dev overlay 指示器/徽章（出现时机随机），交接后复跑失败（8/10、0/10），done 标记曾于 `c37ad36` 回退；最终版在 spec 中隐藏 `nextjs-portal` 宿主元素后重建，连续复跑通过。
- 当前唯一主任务是 T03：定义七个 canonical models（`Player`、`Tournament`、`Match`、`MatchScore`、`SetScore`、`LiveMatchState`、`DataFreshness`、`MatchStatus`）与 `MemoryIdentityRepository`；不实现 provider、service 或路由。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成的 agent 提示文件）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

建立 canonical 领域模型与进程内 identity：`backend/app/domain.py`（UTC 校验、frozen models、lifecycle 枚举）与 `backend/app/identity.py`（`mat_`/`ply_`/`trn_` 内部 ID，可逆映射，供应商外部 ID 不出现在内部 ID 中）。测试优先：先写 `tests/test_domain.py`、`tests/test_identity.py` 失败测试，再实现。

### 为什么现在做

T04 provider contract、T05 LiveTennisAPI adapter 与 T07 service 全部消费这七个模型与 identity repository；先冻结模型语义可避免供应商字段泄漏进公共 DTO。

### 实施依据

- [P1 实施计划 — Task 3](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-3-define-canonical-models-and-in-memory-identity)

### 预计变更范围

- `backend/app/domain.py`、`backend/app/identity.py`
- `backend/tests/test_domain.py`、`backend/tests/test_identity.py`

### 完成门

- `uv run pytest tests/test_domain.py tests/test_identity.py -v` 通过：naive datetime 被拒绝；内部 ID 稳定、可逆、含前缀且不含外部 ID。
- 不实现 provider、cache、service、路由或前端（属 T04+）。
- `ROADMAP.md` 的 T03 写入完成提交和验证证据；T04 变为 `ready`。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 3 的测试优先顺序实施，不扩大到 T04。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `8b15efe` | `uv run pytest tests/test_health.py -v`（1/1 passed，health 200 + `X-Request-ID` 透传）；`uv run python -c "from app.config import Settings; print(Settings(_env_file=None).llm_model)"` 输出 `qwen3.8-max-0902` | T02 验收通过 |
| 2026-09-08 | `c035f5a` | `pnpm test:e2e:update` 10/10 重建基线 → 连续两次 plain `pnpm test:e2e` 各 10/10；`pnpm build` exit 0；10 张 PNG 逐张视觉审阅（无 dev overlay 噪声） | T01 验收通过：基线可重复；桌面/移动最终基线已入 Git |
| 2026-09-08 | `f6a0e9e` 后 | 交接后复跑 `pnpm test:e2e` 两次 | 8/10、0/10 failed；diff 唯一差异为 dev overlay 指示器/徽章；done 曾回退（`c37ad36`），修复后重验于 `c035f5a` |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T02 已由 Claude Code（Codex Goal）于 2026-09-08 完成并交接（提交 `8b15efe`）；T03 可领取。

**交接说明：** 后端骨架位于 `backend/`，测试命令一律 `cd backend && uv run pytest ...`。`create_app()` 目前只接受 `Settings`；T08 才会扩展 `provider=`/`chat_orchestrator=` 注入参数，T03 不得提前扩展工厂。`.env.example` 均为安全占位，无真实凭据。前端视觉基线与代理规则不变：任何前端改动先跑 `pnpm test:e2e`，逐张审阅 diff 后才能决定是否更新基线。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | T02 完成：FastAPI 基础（settings/errors/health/request-ID/app 工厂/pytest 骨架） | `8b15efe` |
| 2026-09-08 | 领取 T02 并置为 in_progress | `3686444` |
| 2026-09-08 | 排除 dev overlay 并重建最终视觉基线，T01 完成交接 | `c035f5a` |
| 2026-09-08 | 回退过早的 T01 done 标记，重开修复基线可重复性 | `c37ad36` |
| 2026-09-08 | 首版视觉基线入 Git（含 dev overlay 噪声，后被替换） | `d13d6dd` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
