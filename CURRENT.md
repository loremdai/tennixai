# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08

**当前任务：** T01 — Freeze the Existing Prototype Visually

**任务状态：** `in_progress`

**当前执行者 / ADE：** Claude Code（superpowers:executing-plans）

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `f6a0e9e`（复核重开时 HEAD；原领取 HEAD 为 `72caed3`，领取提交 `b43dba0`）

**最后验证的产品提交：** `d13d6dd`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T01 基线曾于 `d13d6dd` 提交、`f6a0e9e` 标记 done 并交接 T02；交接后复跑 `pnpm test:e2e` 两次（8/10、0/10）证明基线**不可重复**，done 标记被回退，T01 重开。
- 失败根因已定位：Next.js dev overlay 的屏幕指示器（圆形 N 按钮 / 红色 “1 issue” 徽章，出现时机随机）被拍进部分基线；它是 dev-only 工具噪声，不属于产品视觉。
- 修复方案：`next.config.mjs` 设 `devIndicators: false`（文档确认仅隐藏屏幕指示器，编译/运行错误仍上报），重建 10 张基线并连续复跑通过后再标记 done。
- 仓库仍是 v0 Next.js 原型前端；FastAPI 后端尚未开始。T02 回退为 `planned`，待 T01 真正通过后再次 ready。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成的 agent 提示文件）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

使用 Playwright 为现有原型建立可重复的桌面与移动端视觉基线，覆盖：

- Home `/`
- Match upcoming `/match?status=upcoming`
- Match live `/match?status=live`
- Match finished `/match?status=finished`
- 桌面视口 `1440×1000`
- 移动视口 `390×844`

### 为什么现在做

用户要求真实实现严格遵循 v0 设计。若先改数据流再建立基线，将无法区分原型原貌和实现过程中引入的视觉偏差。

### 实施依据

- [P1 实施计划 — Task 1](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-1-freeze-the-existing-prototype-visually)
- [产品路线设计 — P1.0](./docs/superpowers/specs/2026-09-08-tennixai-product-roadmap-design.md#p10--design-freeze)

### 预计变更范围

- `frontend/package.json`
- `frontend/pnpm-lock.yaml`
- `.gitignore`
- `frontend/playwright.config.ts`
- `frontend/e2e/prototype.visual.spec.ts`
- `frontend/e2e/__screenshots__/**`
- `frontend/next.config.mjs`（仅 `devIndicators: false`，排除 dev-only 屏幕指示器，保证基线可重复）

### 完成门

- 四个目标页面在两个批准视口下均有可审阅截图基线，且基线不含 dev overlay 指示器/徽章。
- Playwright visual test 可重复通过：重建后连续两次 plain 全量运行 10/10。
- 生成报告被忽略，截图 baselines 被 Git 跟踪。
- 不重设计页面，不接后端，不改变原型业务行为。
- `ROADMAP.md` 的 T01 写入完成提交和验证证据；T02 变为 `ready`。

## 下一步操作

1. 重建 10 张基线（`pnpm test:e2e:update`），逐张审阅确认仅移除 dev 指示器、产品视觉不变。
2. 连续两次 `pnpm test:e2e` 全量 10/10，并 `pnpm build` exit 0。
3. 提交修复与基线，更新 ROADMAP/CURRENT 的 done 证据与 T02 ready，推送 `origin/main`。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `c7fb737` | `git status --short --branch`、文档路径与计划标题检查 | 产品基线存在；`main` 已同步 `origin/main`；T01 尚未实施 |
| 2026-09-08 | `d13d6dd` | `pnpm test:e2e`（缺基线 10 failed，符合预期）→ `--update-snapshots` 10 passed → 复跑 10 passed；`pnpm build` exit 0；10 张 PNG 逐张审阅 | 基线建立并通过当轮验证 |
| 2026-09-08 | `f6a0e9e` 后 | 交接后复跑 `pnpm test:e2e` 两次 | 8/10、0/10 failed；diff 唯一差异为 dev overlay 指示器/徽章；done 标记回退，T01 重开 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T01 由 Claude Code 复核重开：`f6a0e9e` 的 done/交接标记因复跑不可重复被回退；修复（`devIndicators: false` + 重建基线）进行中，完成前 T02 保持 `planned`。

**已知本地状态：** 未跟踪文件 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`、`frontend/next-env.d.ts`，均保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | 回退 T01 done 标记，重开任务修复基线可重复性 | 本次提交 |
| 2026-09-08 | 标记 T01 done 并交接 T02（done 标记随后回退） | `f6a0e9e` |
| 2026-09-08 | 冻结原型视觉基线（首版，含 dev 指示器噪声） | `d13d6dd` |
| 2026-09-08 | 建立 P1 15 项详细实施计划 | `c7fb737` |
| 2026-09-08 | 落盘已批准的产品架构与三阶段路线 | `df9ab18` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
