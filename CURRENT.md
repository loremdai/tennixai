# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-23 08:40 CST

**当前任务：** T89 — Prove Local Market Coverage and Close the Phase

**任务状态：** `in_progress`

**执行者 / ADE：** Claude Code（Opus 5）

**分支：** `main`

**起始提交：** `4f6adf1`

**当前动作：** T87 与 T88 已实际验证并关闭（提交 `4c92e2a`、`aa50350`、`56d71df`、`4f6adf1`）。正在实施 T89：`verify` 增加有界只读 `market_quote_snapshot`、runbook 更新、全链回归（确定性/integration/前端/E2E）、一次有界真实本地 coverage run（零 LLM），然后关闭 P4.3 与三份总控。

## T89 范围与硬边界

- 真实 API 验证只做一次有界运行，默认零 LLM 调用；不开启 `--with-llm`。
- 外部安静（无挂单/无 live 比赛/429）必须诚实记录为 skipped/安静窗口，绝不伪造成通过。
- `down` 必须保留数据库、容器与 paper ledger；不得删除或重置任何数据。
- 不新增模型训练/晋升、不改变 decision 门、paper lifecycle 或自动交易边界。
- 视觉基线不得用 mask、阈值、skip、retry 或盲目重录规避。

## T87 完成证据（2026-09-23，全部实际运行）

- 实现提交：`4c92e2a`（后端 DTO/服务/路由/装配）、`aa50350`（前端 typed 解码/view model/行渲染与 e2e fixture）。
- `cd backend && uv run pytest tests/integration/test_p3_query_service.py -q` → `10 passed`，含 5 条新证据：显式 quote state/source/as-of（无投影时为 `unavailable`、有投影时为 `snapshot`）、`decision_action` 只来自真实 observation、未映射行 `match_id`/`decision_action` 均为 null 且 `model_availability == not_evaluated`、未晋升模型的机会空态 reason、`markets_snapshot()` 携带 availability reason。
- `cd backend && uv run pytest tests/test_p3_api.py tests/test_market_stream_api.py tests/test_p3_chat_tools.py tests/test_market_overview_projection.py -q` → `38 passed`（Chat 工具仍消费行列表；SSE ready 帧带 availability）。
- `cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not infrastructure" -q` → `1181 passed, 12 skipped, 101 deselected`，0 failed；`-m infrastructure` → `76 passed`。
- `cd frontend && pnpm test` → `407 passed`；`pnpm typecheck` 干净；`pnpm build` exit 0；`pnpm test:e2e:functional` → `90 passed, 40 skipped, 0 failed`。
- 实施偏差（已记录）：为了让 `markets()` 的 freshness 判定在测试中确定性，`P3QueryService` 新增可选 `clock`（默认 `datetime.now(timezone.utc)`，生产行为不变）；`p3_model_availability` 与两个常量放在 import 块之后（避免 E402）。

## T88 完成证据（2026-09-23，全部实际运行）

- 实现提交：`56d71df`（机会空态模块 `opportunity-empty-state.tsx` + 接线）、`4f6adf1`（5 个双视口 e2e 场景）。
- `cd frontend && pnpm vitest run components/markets/markets-page.test.tsx` → `17 passed`（四个 reason 各自文案、未晋升空态 + 「查看全部市场」入口、无 reason 时中性文案、从空态切到全部市场、低级别行无负向标签、单边报价不掩盖另一侧）。
- `cd frontend && pnpm test` → `407 passed`（T88 新增 4 项）；`pnpm typecheck` 干净；`pnpm build` exit 0。
- `cd frontend && pnpm exec playwright test e2e/p3-markets.spec.ts` → `30 passed`（双视口：快照报价与时间、partial/no_liquidity/stale/unavailable 四态互不混淆、低级别保留真实报价且无「未覆盖」标签、仅 active link 行可导航、未晋升空态、真实 BUY 机会仍渲染）。
- 视觉门：`pnpm test:e2e:visual` → `34 passed, 4 skipped, 0 failed`（4 项为 replay-off 按设计跳过）；`git diff --exit-code -- frontend/e2e/__screenshots__` → **PNG 零 diff**（生产改动未触碰冻结原型）。
- 默认组合 lane（`pnpm test:e2e`）在 `prototype.visual home-initial`（生产 Home 页旧基线）出现既有抖动：本轮两次分别为 2 项与 3 项不同用例失败；**对照实验证明与本次改动无关**——在 HEAD 前端状态（`git stash` 我的前端改动）下同一组合 lane 同样得到 `33 passed / 1 failed`（同一 `home-initial`），而单独运行 `pnpm test:e2e:visual` 在本轮 3 次均 `34 passed`。未使用 mask/阈值/skip/retry/重录规避，按事实记录为既有不稳定项。
- 实施偏差（已记录）：计划把空态文案表放在 `opportunities-view.tsx`，但该文件是冻结的预览组件（视觉真源），故新建生产侧模块；`marketRow()` fixture 默认 `decision_action: null`（全部市场行无决策时不伪造徽章）；并新增每测试 payload 重置，避免模块级可变 fixture 在用例间泄漏。

## 受保护的既有未跟踪文件

不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-23 | 本提交 | T87、T88 关闭（证据见上）并领取 T89：Claude Code（Opus 5）、`main`、起始 `4f6adf1` |
| 2026-09-23 | `56d71df`、`4f6adf1` | T88：机会空态按真实原因解释；5 个双视口 e2e 场景 |
| 2026-09-23 | `4c92e2a`、`aa50350` | T87：后端显式 quote/model/decision 语义；前端 typed 解码与行渲染 |
| 2026-09-22 | `46ea3cc`、`3ef4234` | T86 关闭：有界 snapshot 调度、coverage 健康、流恢复加固 |
| 2026-09-22 | `f413196`、`df04f9c` | T85 关闭：批量报价、canonical 状态与 durable 投影 |

## 下一步

1. 实施并验证 T89（verify 有界检查 + runbook + 全链回归 + 一次有界真实本地 coverage run）。
2. 关闭 P4.3：更新 `ROADMAP.md`（T89 `done`、P4.3 阶段 `done`）、`PROJECT.md`（P4.3 交付事实）与本文件（无 active 任务）。
3. P4.3 完成后单独排期模型晋升证据链；自动下单继续 `deferred`。