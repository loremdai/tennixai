# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-16 19:55 CST

**当前任务：** T58 — Add Reversible P3 Persistence and Idempotent Ledger Repositories（已完成；T59 `ready`，尚未领取）

**任务状态：** `done`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `507b0ac`

**领取提交：** `982bfef`

**产品提交：** `02516c6`（feat: persist P3 market and paper ledger）

**当前动作：** T58 已关闭。TDD 先红（ORM 行与 repository 模块缺失、DB 停在 `0003`）后绿；migration `0004` 十二表可逆、幂等 ledger repositories、link 冻结与重启恢复全部通过实际 PostgreSQL 验证。下一步由同一执行者领取 T59（只读 Polymarket adapter 与精确 mapping）。

## 当前已验证状态

- T58 验收（全部实际运行）：schema 元数据测试 `tests/test_p3_persistence_models.py` 8 passed；`uv run pytest -m infrastructure tests/integration/test_p3_market_persistence.py tests/integration/test_p3_paper_ledger.py` 16 passed；`alembic upgrade head → downgrade 0003 → upgrade head` 往返 exit 0 且 paper ledger 复跑 8 passed；infrastructure 全套 38 passed；确定性 backend 608 passed/67 deselected；新文件 `ruff check`/`ruff format --check` 干净（models.py 既有 format 债务经 stash 基线对照确认，未触碰）。
- Ledger 不变量已由集成测试证明：20 路并发注册收敛同一 `mkt_` ID 且不含 condition ID；intent 幂等重放相等、同场同 side 第二把 `UniqueViolationError`；`record_fill` 单事务、注入 pre-commit 失败完整回滚（intent 仍 PENDING、零 fill、零 position）；position forward-only；intent 后 link 冻结；FINAL resolution 终态；重启（全新 Database 实例）恢复 pending intents 与 unsettled positions；raw purge 不删 rules/ledger。
- T57 canonical contracts（`e7da341`）保持：公共模型只有内部 ID，provider ID 仅存在于私有 `market_external_ids`；配置零 wallet/private-key 字段；`p3_mode` 默认 `disabled`。
- T56 保持关闭（`f29a789`，52 张基线）；P2（含 T54）保持 `done`；仓库尚无 Polymarket adapter、prediction 引擎、decision 引擎或 paper 服务编排；真实下单明确延期。
- 模型未通过晋升门时生产必须诚实 `NO BET`；不得伪造 `BUY`。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-16 | `02516c6` | T58 完成：migration `0004` 十二表可逆 + 幂等 market/paper repositories；integration 16 passed、往返复跑通过 |
| 2026-09-16 | `982bfef` | Claude 领取 T58（起始 `507b0ac`） |
| 2026-09-16 | `507b0ac` | T57 关闭：三份总控记录 canonical contracts 证据 |
| 2026-09-16 | `e7da341` | T57 完成：P3 canonical domain、只读 provider protocol、安全配置与 59 项新测试 |
| 2026-09-16 | `63e0ff8` | Claude 领取 T57（起始 `5df1fe0`） |

## 下一步

1. T59 已 `ready`：按 [P3 实施计划 T59](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t59-implement-the-read-only-polymarket-adapter-and-exact-match-mapping) 实施只读 Polymarket adapter（public Gamma/CLOB REST、`httpx.MockTransport` 测试、脱敏 fixture）与 PlayerResolver 精确组合 mapping；开始前先写入并推送领取记录。
2. T59 边界：绝不导入 trading SDK、绝不请求 wallet/private key；错误消息零 URL/key/provider-ID 泄漏；opt-in `polymarket_live` smoke 无活跃市场时诚实 skip。
3. 其后按顺序 T60–T71，不得并行领取。
