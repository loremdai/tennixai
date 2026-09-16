# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-16 17:43 CST

**当前任务：** T56 — Generate, Import, and Freeze the P3 v0 Prototype

**任务状态：** `in_progress`

**执行者 / ADE：** Codex / Codex Desktop（由 v0 显式交接）

**分支：** `main`

**任务起始提交：** `0dab24c`

**领取提交：** `1f625b2`（v0）；本次交接提交：`3afec75`

**产品提交：** `3ce0cbf`、`0e5e06f`、`9c868bf`（用户确认并推送的 v0 候选基线）、`4ad724d`（T56 验证 checkpoint）

**关闭提交：** —

**当前动作：** 用户已确认 v0 原型并推送 `9c868bf`，现显式交接给 Codex。`0f18f7b` 已修复 P3 visual harness 的跨 project 视口覆盖问题；用户随后在普通终端重建 52 张 PNG，并用 `pnpm exec playwright test --grep 'P3 visual'` 复跑成功（`.last-run.json` 为 `passed`）。26 个场景的 desktop（1440px）与 mobile（390px）基线已逐张人工核验。T56 只剩既有 P1/P2 浏览器视觉回归；通过后仅暂存这 52 张 P3 PNG、更新总控并关闭任务，才可将 T57 设为 `ready`。

## 当前已验证状态

- T55 已完成，设计基线为 `d7cc25e`：421 行 [P3 设计规格](./docs/superpowers/specs/2026-09-16-tennixai-p3-market-decision-support-design.md)、847 行 [T56–T71 实施计划](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md)、320 行 v0 Prompt，以及同步更新的 SOTA 研究记录。
- 用户已授权剩余设计项全部采用推荐方案；P3 的 exact mapping、独立模型与晋升门、one-shot FOK paper lifecycle、provider-final settlement、独立 sports/decision SSE、三层页面和完整状态矩阵均已冻结。
- T55 验证：本地 Markdown 链接全部存在；占位符与 64 位密钥值模式零命中，交易凭据词只出现在禁止性边界中；`git diff --cached --check` 通过。T55 是设计任务，没有运行或声称产品测试。
- 当前仓库只有 P3 preview 页面、固定状态数据和验证用例，仍没有 P3 provider、schema、prediction、decision、paper ledger 或真实交易代码。P2（含 T54）保持 `done`；真实下单仍明确延期。
- T56 checkpoint `4ad724d` 已验证：前端 `pnpm test` 242/242、`pnpm typecheck`、`pnpm build`、12 个决策状态 SSR 与代表性 Home/Markets/Match 双视口人工检查通过；修正了 P3 Match 状态/布局、Home 重复市场区块、stale 状态覆盖和 fixture URL 一致性。
- 视觉门的环境阻塞已由用户在普通终端绕开。原先 plain run 6/6 失败的根因是 `p3.visual.spec.ts` 在 desktop/mobile 两个 project 内均显式跑两次 `setViewportSize` 并复用快照名，后一次 mobile 捕获覆盖前一次 desktop 捕获。`0f18f7b` 改为完全交由 Playwright project 配置管理视口，每个 project 每场景只捕获一次；`pnpm typecheck`、`pnpm exec playwright test --list --grep 'P3 visual'`（6 项）和 `pnpm test`（242/242）通过。修复后用户重建 52 张候选基线并复跑 `pnpm exec playwright test --grep 'P3 visual'` 成功（`.last-run.json`=`passed`）；全部 desktop 图为 1440px、mobile 图为 390px，且已逐张人工核验。P1/P2 视觉回归仍待执行，故 T56 仍为 `in_progress`。
- 模型未通过许可/覆盖审计、walk-forward、校准和 shadow 晋升门时，生产必须诚实输出 `NO BET`；不得为了演示制造 `BUY`。

## T56 输入门与边界

- 用户已确认并推送 v0 候选原型 `9c868bf`；T56 的外部输入门已满足，当前只剩仓库内冻结与验收门。
- 导入时只整理已批准的 v0 前端资产、确定性 preview data、state switcher 和 26 个代表视觉基线；不接 P3 后端或真实 API。
- 原型必须覆盖 Home 4、Markets 8、Match 14 个指定 desktop/mobile 视觉基线；每张 expected/actual/diff 都需逐张审阅，不能批量接受未知变化。
- 现有 P1/P2 页面和视觉真源必须保持；不覆盖 package manifest、shadcn primitives 或任务外改动。
- T56 的完整 files、TDD、命令和提交门只见 [P3 实施计划 T56](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t56-generate-import-and-freeze-the-p3-v0-prototype)。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。`frontend/AGENTS.md` 与 `frontend/CLAUDE.md` 已由 v0 以与原本未跟踪内容完全相同的 blob 纳入 `9c868bf`，现为受版本控制的前端指令。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-16 | `4ad724d` | T56 验证 checkpoint：修正 preview routing、Match 顺序、Home 单一 Pulse、stale 语义与 fixture 链接；确定性门通过，视觉基线受 Chromium 启动权限阻塞 |
| 2026-09-16 | `9c868bf` | 用户确认并推送 v0 候选原型；显式交接 Codex 执行 T56 冻结验收 |
| 2026-09-16 | `d7cc25e` | T55 完成：P3 规格、T56–T71 计划、v0 Prompt 与最终研究结论冻结；没有产品代码 |
| 2026-09-16 | `0b140c4` | T55 中间节点：完整 `DecisionSummary` 与 one-shot paper 状态序列冻结 |
| 2026-09-15 | `b6539e4` | T55 领取：从 `7409806` 开始 P3 design freeze |

## 下一步

1. 在可正常启动 Playwright Chromium 的环境中重跑 `pnpm test:e2e --grep "prototype|visual"`，确认既有 P1/P2 视觉基线无回归；只接受本任务的 P3 新基线。
2. 只暂存已人工核验的 52 张 P3 PNG，完成全量门后运行确定性回归/构建检查，并更新总控的完成提交与实际证据。
3. 关闭 T56 后才可将 T57 改为 `ready`；在此之前不得进入 T57。
