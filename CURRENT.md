# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-16 19:07 CST

**当前任务：** T57 — Add Canonical P3 Domain, Protocols, and Safe Configuration

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `5df1fe0`

**领取提交：** 本次提交（T57 领取记录）

**当前动作：** 已核对 `git fetch origin`、`git status --short --branch`、`git branch --show-current`、`git log -1 --oneline`：本地与 `origin/main` 同步在 `5df1fe0`，工作区只有四个受保护未跟踪项。按 [P3 实施计划 T57](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t57-add-canonical-p3-domain-protocols-and-safe-configuration) 以 TDD 实施 P3 canonical domain、`MarketDataProvider`/`PredictionService` 等 protocol 边界与安全配置；不接网络、SQL、模型训练或 UI。

## 当前已验证状态

- T55 已完成，设计基线为 `d7cc25e`：421 行 [P3 设计规格](./docs/superpowers/specs/2026-09-16-tennixai-p3-market-decision-support-design.md)、847 行 [T56–T71 实施计划](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md)、320 行 v0 Prompt。
- T56 已关闭（`f29a789`）：26 个 P3 状态 × desktop/mobile 的 52 张视觉基线入库并逐张人工核验；`prototype|visual` 复跑 34 passed / 4 skipped（skipped 均为 replay-off 时按设计跳过的 P2 Replay 用例）；`pnpm test` 242/242、typecheck、build 通过；P1/P2 基线零改动。
- 当前仓库只有 P3 preview 页面、固定状态数据和验证用例，仍没有 P3 provider、schema、prediction、decision、paper ledger 或真实交易代码。P2（含 T54）保持 `done`；真实下单仍明确延期。
- 模型未通过许可/覆盖审计、walk-forward、校准和 shadow 晋升门时，生产必须诚实输出 `NO BET`；不得为了演示制造 `BUY`。

## T57 范围与边界

- 只创建 `backend/app/markets/{__init__,models,providers}.py`、`backend/app/prediction/{__init__,models}.py`、`backend/app/decision/{__init__,models}.py`、`backend/app/paper/{__init__,models}.py`，并修改 `backend/app/config.py` 与根目录 `.env.example`；测试为 `backend/tests/test_p3_domain.py` 与 `backend/tests/test_config.py`。
- 配置只允许：公开 Gamma/CLOB/WS base URL、`p3_mode=disabled|shadow|paper`、固定 `$10` stake、模型 artifact 目录、有界 market 订阅数与 freshness 上限；不得引入任何 wallet/private key/trading credential 设置。
- 先写失败测试（naive datetime、负 size、乱序/重复 book level、概率越界、非互补模型概率、公共模型禁外部 ID、非法 lifecycle transition、`DecisionObservation` 必须携带版本化输入），确认失败后再做最小实现。
- 验收命令：`uv run pytest tests/test_p3_domain.py tests/test_config.py tests/test_p2_domain.py tests/test_domain.py -v`，另跑全量确定性回归。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。`frontend/AGENTS.md` 与 `frontend/CLAUDE.md` 已由 v0 以与原本未跟踪内容完全相同的 blob 纳入 `9c868bf`，现为受版本控制的前端指令。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-16 | （本提交） | Claude 领取 T57：写入执行者、起始 SHA `5df1fe0` 与范围边界 |
| 2026-09-16 | `5df1fe0` | T56 最终视觉证据记录（`docs: record T56 final visual evidence`） |
| 2026-09-16 | `f29a789` | T56 关闭工件：52 张已审阅 P3 视觉基线入库；完整视觉回归通过 |
| 2026-09-16 | `0f18f7b` | 修复 P3 visual project 之间的 desktop/mobile 覆盖 |
| 2026-09-16 | `9c868bf` | 用户确认并推送 v0 候选原型；显式交接 Codex 执行 T56 冻结验收 |

## 下一步

1. 完成 T57 的 TDD 实施与验收命令，更新三份总控，提交并推送 `origin/main`。
2. T57 关闭后按同一流程领取 T58（可逆 P3 schema 与幂等 ledger repositories），顺序执行至 T71，不得并行领取。
