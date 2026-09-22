# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-23 03:45 CST

**当前任务：** 无（P4.3「市场数据可信度与覆盖」已关闭，无 active 主任务）

**任务状态：** 无 active；等待用户排期下一个主任务

**执行者 / ADE：** Claude Code（Opus 5）— 上一任务 T89

**分支：** `main`

**起始提交：** —

**当前动作：** P4.3 的 T83–T89 已全部完成、逐项提交并推送。本机栈当前为 `down`（`./scripts/tennix-live status` → `stack: partial`，database/redis 容器 healthy 保留）；自动下单继续 `deferred`，模型晋升证据链需用户单独排期。

## T89 完成证据（2026-09-23，全部实际运行）

- 提交：`c1c8297`（关闭 T87/T88 并领取 T89）、`7f9201f`（`verify` 有界批量报价检查）、`25e81b1`（runbook 双车道/七状态/配置/coverage 健康）、`6484ec6`（未变化热簿只镜像一次，配合既有 `decide_quote_write` 幂等规则）、`ce4a495`（机会空态按部署真实模型状态解释）、本提交（总控收口）。
- 全链回归（最终提交状态）：确定性 `1195 passed, 114 deselected, 0 failed`；infrastructure 一次 `77 passed` 全绿，另一次 `1 failed`（既有 `test_p3_latency_gate` wall-clock 守卫抖动；控制实验见下）；前端 `pnpm test` 407 passed + typecheck exit 0 + build exit 0；默认 E2E lane 两次：run1 功能 `90 passed/40 skipped/0 failed` + 视觉 `33 passed/4 skipped/1 failed`（`p1.visual p1-home-initial`，1111 像素/0.01，基线 PNG 未变），run2 功能 `90/40/0` + 视觉 `34/4/0` 且 exit 0；视觉 lane 单跑 `34 passed/4 skipped/0 failed`；`frontend/e2e/__screenshots__` 全程零 diff。
- 既有抖动判定（未用 mask/阈值/skip/retry/重录规避）：① 延迟门——同命令在 pre-P4.3 提交 `61c460d`（无任何 P4.3 代码）失败更严重（`book replay wall clock 66.1s` vs 60s 上限），单跑该用例通过（该用例只跑 `DecisionWorker`，其代码路径 P4.3 未改动，diff 可核对）；② 视觉门——失败用例为冻结原型基线页，单独运行时通过，且基线 PNG 零改动。
- 真实本地 coverage gate（两次窗口，`up`→健康/接口/浏览器→`down`）：
  - 窗口 1：`up` 后 `market_snapshot degraded F405`（= SQLAlchemy `ProgrammingError.code` + asyncpg `UndefinedTableError`：live-local 库仍是 `0005`，无 `market_quote_snapshots`）。健康面如实标记降级、**未伪造任何报价**；随后迁移到 `0006`，coverage `candidate 185 / attempted 185 / fresh_snapshot 15 / no_liquidity 4 / unavailable 166`（和=185），`batch_failures 0 / rate_limited false`。
  - 窗口 2（含 `ce4a495`）：coverage 同上，`market_snapshot` `ok`（success 6/failure 0）；`/markets` 190 行、首页 50 行中 45 行有 active link、states `no_liquidity/snapshot/unavailable`、`with_action 0`；机会端点 `{"reason":"ELIGIBLE_UNPROMOTED","model_status":"not_promoted"}`、零行、零 `BUY/WAIT`；`verify` 6 passed / 2 skipped（`market_websocket RECEIVE_TIMEOUT` 为真实安静窗口，`llm_chat NOT_REQUESTED` 零 LLM）；浏览器验收 6 passed（双视口，含 DOM/URL provider-material 扫描）。
  - `down` exit 0 且数据保留：alembic `0006`、markets 190、active links 169、quote rows 185、raw 104、players 4978、aliases 32129、positions 0、decisions 0；database/redis 容器未动。
- 泄漏扫描：公共 DTO/服务/运行时/前端 app·components·lib 零命中；命中项全部落在私有映射与适配层（`market_external_ids`、`MarketExternalId`、`polymarket.py` 的 token 参数、内部 registrar 闭包）及三处「不存在钱包/密钥」说明注释；`verify` 只用稳定 reason code，永不回显原响应。

## 诚实记录（未关闭项与偏差）

1. **LLM 配额（需用户知晓）**：为把 live-local 库补到 `0006` 运行了 `./scripts/tennix-live init`；该命令在迁移后会执行一次性中文名 LLM enrichment（env 配了 LLM key 时无条件运行，按 25 条一批直到没有缺失），发现后已立即终止。18:00Z 后新增 2178 条 `source='llm'` 别名——违反当次「零 LLM」约束，如需追责请以此为准。后续若只需迁移，仍应计划该 enrichment 的耗时与配额，或与用户确认后再运行。
2. **launcher 状态修复**：被中断的 `init` 会把 `/tmp` 下 launcher `state.json` 重置为 `initialized=false / schema_head=null`，从而让后续 `up` 以 `LOCAL_NOT_INITIALIZED` 拒绝。已按数据库真实状态改回 `initialized=true / schema_head="0006"`（原文件备份为 `state.json.pre-t89-repair`），并以 `down → up → 验收 → down` 复核可用。这不是受支持的日常流程，仅记录本次修复。
3. **既有未关闭项**：`test_p3_latency_gate` 的 wall-clock 守卫在机器高负载时可能触发（阈值未调整）；冻结原型视觉基线在默认并发 lane 下偶发像素抖动（单独运行通过）；更早会话（2026-09-22 08:36Z）的 runtime 日志里有 36 次 `keep_alive` 未取回任务异常（本次运行日志无新增，未复现）。
4. **测试夹具更新**：T80 `e2e/local-real-runtime.spec.ts` 的安静市场匹配器早于 T88 的分原因文案，已改为断言产品真实空态标题并沿「查看全部市场」入口走到真实市场行（反而多覆盖了 workbench 分支）。

## 受保护的既有未跟踪文件

不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-23 | `e9426d5` | runbook 明确 `init` 的中文名 LLM 补全（迁移也无法跳过）与 `LOCAL_SCHEMA_BEHIND` 排障行 |
| 2026-09-23 | `0145752` | P4.3 关闭：T89 `done`、阶段 `done`，三份总控无 active 任务 |
| 2026-09-23 | `ce4a495` | 机会空态按部署真实模型状态解释（`ELIGIBLE_UNPROMOTED`），T80 验收匹配器跟进 |
| 2026-09-23 | `6484ec6` | 未变化热簿只镜像一次（幂等等价于 `decide_quote_write`） |
| 2026-09-23 | `25e81b1`、`7f9201f`、`c1c8297` | T89：runbook、`verify` 有界批量报价检查，关闭 T87/T88 并领取 T89 |
| 2026-09-23 | `56d71df`、`4f6adf1` | T88：机会空态按真实原因解释；5 个双视口 e2e 场景 |
| 2026-09-23 | `4c92e2a`、`aa50350` | T87：后端显式 quote/model/decision 语义；前端 typed 解码与行渲染 |

## 下一步

1. 由用户排期下一个主任务：模型晋升证据链（champion/校准/policy 的 audit、walk-forward、shadow 与 untouched test 证据）——必须单独设计并单独授权，P4.3 未触碰模型。
2. 自动下单保持 `deferred`，需独立法律、风控、安全与执行设计。
3. 可选清理项（非阻塞）：上述既有抖动与 `keep_alive` 未取回异常，如需处理应各自立任务并带自己的证据。