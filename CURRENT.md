# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08

**当前任务：** T02 — Establish the FastAPI Foundation

**任务状态：** `ready`

**当前执行者 / ADE：** `unassigned`

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `unassigned`（领取任务时记录当时的 HEAD）

**最后验证的产品提交：** `c035f5a`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T01 已完成：Home 与 Match 三态在桌面/移动视口的 10 张视觉基线已入 Git（最终版 `c035f5a`），visual suite 可重复通过。
- 历史提醒：首版基线 `d13d6dd` 混入 Next dev overlay 指示器/徽章（出现时机随机），交接后复跑失败（8/10、0/10），done 标记曾于 `c37ad36` 回退；最终版在 spec 中隐藏 `nextjs-portal` 宿主元素后重建，连续复跑通过。
- 仓库仍是 v0 Next.js 原型前端；FastAPI 后端尚未开始，T02 是后端入口。
- 当前唯一主任务是 T02：建立 FastAPI 基础（typed settings、健康检查、请求 ID、app 工厂与 pytest 骨架），不接 provider、不写业务路由、不碰前端代理。
- T02 已满足领取条件，但尚未分配执行者；领取后直接在 `main` 推进。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成的 agent 提示文件）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

建立 FastAPI 基础：读取 `TENNIX_*` 环境变量的 typed `Settings`（fake/live 模式凭据校验）、`AppError` 基类、`GET /api/v1/health`、`X-Request-ID` 中间件、`create_app()` 工厂，以及 uv/pytest 骨架。按测试优先顺序：先写失败的 health 测试，再实现。

### 为什么现在做

后续 provider、service、REST 与 chat 全部依赖统一 app 工厂与配置入口；T01 已冻结视觉基线，可以安全启动后端而不影响前端。

### 实施依据

- [P1 实施计划 — Task 2](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-2-establish-the-fastapi-foundation)

### 预计变更范围

- `backend/pyproject.toml`、`backend/uv.lock`、`backend/.env.example`、`frontend/.env.example`
- `backend/app/__init__.py`、`backend/app/config.py`、`backend/app/errors.py`、`backend/app/api/__init__.py`、`backend/app/api/routes.py`、`backend/app/main.py`
- `backend/tests/test_health.py`
- `.gitignore`

### 完成门

- `uv run pytest tests/test_health.py -v` 通过：health 返回 200 与 `{"status":"ok","service":"tennix-api"}`，`X-Request-ID` 原样透传。
- `uv run python -c "from app.config import Settings; print(Settings(_env_file=None).llm_model)"` 输出恰为 `qwen3.8-max-0902`，且不打印任何凭据。
- 不实现 provider、service、业务 REST 路由或前端代理（属 T03–T09）。
- `ROADMAP.md` 的 T02 写入完成提交和验证证据；T03 变为 `ready`。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 2 的测试优先顺序实施，不扩大到 T03。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `c035f5a` | `pnpm test:e2e:update` 10/10 重建基线 → 连续两次 plain `pnpm test:e2e` 各 10/10；`pnpm build` exit 0；10 张 PNG 逐张视觉审阅（无 dev overlay 噪声） | T01 验收通过：基线可重复；桌面/移动最终基线已入 Git |
| 2026-09-08 | `f6a0e9e` 后 | 交接后复跑 `pnpm test:e2e` 两次 | 8/10、0/10 failed；diff 唯一差异为 dev overlay 指示器/徽章；done 曾回退（`c37ad36`），修复后重验于 `c035f5a` |
| 2026-09-08 | `c7fb737` | `git status --short --branch`、文档路径与计划标题检查 | 产品基线存在；`main` 已同步 `origin/main`；T01 尚未实施 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T01 已由 Claude Code 于 2026-09-08 完成并交接（最终提交 `c035f5a`）；T02 可领取。

**交接说明：** 视觉基线位于 `frontend/e2e/__screenshots__/{desktop,mobile}/`，原型页面是视觉真源；spec 通过隐藏 `nextjs-portal` 宿主元素排除 dev-only overlay。后续任何前端改动先跑 `pnpm test:e2e`，逐张审阅 diff 后才能决定是否更新基线；不得仅为让命令通过而更新基线。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | 排除 dev overlay 并重建最终视觉基线，T01 完成交接 | `c035f5a` |
| 2026-09-08 | 回退过早的 T01 done 标记，重开修复基线可重复性 | `c37ad36` |
| 2026-09-08 | 首版视觉基线入 Git（含 dev overlay 噪声，后被替换） | `d13d6dd` |
| 2026-09-08 | 领取 T01 并置为 in_progress | `b43dba0` |
| 2026-09-08 | 建立 P1 15 项详细实施计划 | `c7fb737` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
