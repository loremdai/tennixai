# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-16 19:28 CST

**当前任务：** T58 — Add Reversible P3 Persistence and Idempotent Ledger Repositories

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `507b0ac`

**领取提交：** 本次提交（T58 领取记录）

**当前动作：** T57 已以 `e7da341`（代码）与 `507b0ac`（关闭）交付并推送。现按 [P3 实施计划 T58](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t58-add-reversible-p3-persistence-and-idempotent-ledger-repositories) 以 TDD 实施可逆 P3 schema（migration `0004`）与幂等 ledger repositories；验收门为 upgrade→downgrade→upgrade 往返、20 路并发幂等收敛、事务回滚、重启恢复与 raw cleanup 不删 canonical evidence，需要本地 PostgreSQL healthy。

## 当前已验证状态

- T57 验收命令 `uv run pytest tests/test_p3_domain.py tests/test_config.py tests/test_p2_domain.py tests/test_domain.py -v` 实际通过 80 passed；全量确定性 backend `622 passed, 29 deselected`；新增/触碰文件 `ruff check` 零告警、format 干净（31 个既有 ruff 债务经 stash 基线对照确认属任务前旧债，未触碰）。
- 域不变量已冻结：naive datetime、负/零 size、乱序或重复 book level、概率越界、非互补模型概率、公共模型 `extra=forbid` 拒绝 provider ID（condition/token ID 只存在于私有 `MarketExternalId`）、`DecisionObservation` 缺版本化输入即拒、stale/gap 覆盖层撤销新 `BUY/SELL`、非法 lifecycle transition（含 retry/re-entry/self-transition）、FINAL resolution 双 outcome payout 恰和为 1（含 50–50 = 0.5/0.5）且须 `confirmed_at`、intent `NO_FILL` 必带 typed reason、track 与 exit_kind 一致性。
- 配置安全门：`p3_mode` 仅 `disabled|shadow|paper`（默认 disabled）、固定 stake 默认恰 `$10`、公开 Gamma/CLOB/WS URL、有界订阅（1..100）与 freshness 上限；`Settings.model_fields` 扫描证明不存在 wallet/private-key/seed/signer/funder/trading credential 字段；`.env.example` 非注释行零凭据词。
- T56 保持关闭（`f29a789`，52 张基线）；P2（含 T54）保持 `done`；当前仓库仍没有 P3 provider 实现、schema、prediction 引擎、decision 引擎、paper ledger 服务或真实交易代码；真实下单明确延期。
- 模型未通过许可/覆盖审计、walk-forward、校准和 shadow 晋升门时，生产必须诚实输出 `NO BET`；不得为了演示制造 `BUY`。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。`frontend/AGENTS.md` 与 `frontend/CLAUDE.md` 已由 v0 以与原本未跟踪内容完全相同的 blob 纳入 `9c868bf`，现为受版本控制的前端指令。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-16 | `e7da341` | T57 完成：P3 canonical domain、只读 provider protocol、安全配置与 59 项新测试；全量确定性 622 passed |
| 2026-09-16 | `63e0ff8` | Claude 领取 T57：写入执行者、起始 SHA `5df1fe0` 与范围边界 |
| 2026-09-16 | `5df1fe0` | T56 最终视觉证据记录 |
| 2026-09-16 | `f29a789` | T56 关闭工件：52 张已审阅 P3 视觉基线入库 |
| 2026-09-16 | `9c868bf` | 用户确认并推送 v0 候选原型 |

## 下一步

1. 完成 T58 的 TDD 实施与验收门（migration 往返、并发幂等、回滚、重启恢复、raw cleanup），更新三份总控，提交并推送 `origin/main`。
2. T58 关闭后按同一流程领取 T59（只读 Polymarket adapter 与精确 mapping），顺序执行至 T71，不得并行领取。
