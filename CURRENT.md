# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-23 14:53 CST

**当前任务：** T91 — Diagnose and Restore Polymarket Quote Refresh

**任务状态：** `in_progress`

**执行者 / ADE：** Codex

**分支：** `main`

**起始提交：** `5ee62ed`

**当前动作：** 快照错误健康误报已由 `4ba96f7` 修复（失败/429 会保留 coverage 并标记 `degraded`）。网络不是完全不可达，但连接间歇不稳。更关键的根因已查明：当前 Gamma 有 61 个活跃网球胜者市场，其中 49 个是双打组合、12 个是单打；provider 仅接收两个 outcome 都能解析成单一内部球员 ID 的市场，所以只保留 2 场，49 场双打及 10 场单打因 `UNRESOLVED_PLAYER` 跳过。对当前 12 场单打直接查 CLOB，24/24 个 token 均返回订单簿、22 个有挂单；数据实际存在，主要是应用的球员身份模型阻止报价进入展示。另有本地 185 个旧 active 候选中仅 2 个 token 对仍在当前 Gamma 目录；370 个旧 token 的成功批量查询只回 15 本，runtime coverage 为 `fresh_snapshot=2 / no_liquidity=5 / unavailable=178`。因此修复需要让全部当前网球胜者市场能以独立 outcome 名称/顺序展示真实报价，同时仅在严格解析并映射的单打上启用模型；还要在完整成功的 Gamma 刷新后把消失市场移出当前候选集、但保留历史记录。机会页为空另因 `model_status=not_promoted`，不属于报价刷新。

## T91 已确认事实

- 较早 OpenSSL 检查曾观察到 Polymarket 主机证书链异常（`CN=rpz10-landing`）；本轮 curl 又报告 `TLS=0`，之后同一主机出现 `SSL_ERROR_SYSCALL`。证书/连接结果在不同尝试间不一致，不能据单次检查断言固定的沙盒封锁。真实 API-Tennis REST gate `1 passed`，认证和赛程读取成功；API-Tennis 免费试用未过期。
- 用户终端报告 `https://clob.polymarket.com/time` 为 `HTTP=200 TLS=0`；本执行环境对同端点也曾成功，但随后 curl 出现 `SSL_ERROR_SYSCALL`、HTTPX 连续三次 `ConnectError`，证明连通性间歇不稳定，不能称为完全不可达。
- 重新从 Gamma 读取当前网球胜者市场：61 个活跃市场中 provider 成功解析 2 个，59 个因球员名未命中 canonical directory 而记为 `UNRESOLVED_PLAYER`。本地数据库仍有 185 个 open/scheduled 快照候选，但仅 2 个 token 对与当前 Gamma 目录一致，显示旧市场仍留在有效候选集合。
- 将当前 Gamma 61 场按 outcome 名称形态核验：49 场为双打组合、12 场为单打；现有 `MarketOutcome` 必须绑定两个独立 player ID，provider 因此无法表示未识别单打选手或双打组合。12 场单打中 resolver 仅能完整解析 2 场。另对这 12 场直接请求 CLOB：HTTP 200、24/24 订单簿返回、22 本有挂单；因此真实单打报价存在，瓶颈是进入应用的身份/展示模型而非报价源无数据。
- 对本地 370 个候选 token 的一次成功 CLOB 批量核验返回 15 本：2 场两侧均有挂单、5 场两侧均为空簿、178 场未返回任一侧订单簿；runtime 同期 coverage 为 `fresh_snapshot=2 / no_liquidity=5 / unavailable=178`。Polymarket 官方文档说明 `/books` 应对每个请求 token 返回一本订单簿，因此大量缺失不能解释为“只有空挂单”；需核实 token/市场是否已过期或不再有效。见[官方订单簿文档](https://docs.polymarket.com/market-data/prices-order-books)。
- 较早 HTTPX 连接失败与宿主 `NO_PROXY` 的 `::1` 曾触发的 `Invalid port: ':1'` 已由 T90 分别排查/修复客户端代理继承；本轮仍看到 CLOB 偶发连接失败，须继续验证是否为网络路径波动。此前一个失败窗口曾有 `candidate=185 / attempted=0 / batch_failures=4 / stale=185`，快照健康正确为降级；本轮另一次成功窗口已拿到 `attempted=185`，`fresh_snapshot=2 / no_liquidity=5 / unavailable=178`。简略 `tennix-live status` 的 `polymarket=ok` 是独立流健康项，不代表报价覆盖充分。
- 原运行时曾把 4 个快照批次全失败报告成 `market_snapshot=ok`；`4ba96f7` 已改成按批次失败/429 报 `degraded`，并保留完整 coverage 聚合。
- 机会页仍会因独立的 `model_status=not_promoted` 保持无 `BUY/WAIT`，模型晋升不在 T91 范围内；报价可用性与机会生成必须分开验收。

## T89 完成证据（2026-09-23，全部实际运行）

- 提交：`c1c8297`（关闭 T87/T88 并领取 T89）、`7f9201f`（`verify` 有界批量报价检查）、`25e81b1`（runbook 双车道/七状态/配置/coverage 健康）、`6484ec6`（未变化热簿只镜像一次，配合既有 `decide_quote_write` 幂等规则）、`ce4a495`（机会空态按部署真实模型状态解释）、`0145752`（T89/阶段收口）。
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
| 2026-09-23 | `10ff93e` | 记录当时 Polymarket TLS 失败；本轮复测补充为连接间歇，并确认报价缺失主要来自市场/outcome 身份模型与旧候选未退役 |
| 2026-09-23 | `ca91580` | 领取 T91：Codex / `main` / 起始 `5ee62ed`；确认 Polymarket 主机 TLS 拦截与快照健康误报 |
| 2026-09-23 | `4ba96f7` | 快照批次失败或限流时正确报告 `degraded`；1202 后端确定性用例通过 |
| 2026-09-23 | `b3ef97d` | T90 修复 HTTP/WS 客户端隐式继承宿主代理环境；确定性后端 1200 passed，根 `.env` 未改 |
| 2026-09-23 | `a61dcd2` | 领取 T90 |

## 下一步

1. 由用户排期下一个主任务：模型晋升证据链（champion/校准/policy 的 audit、walk-forward、shadow 与 untouched test 证据）——必须单独设计并单独授权，P4.3 未触碰模型。
2. 自动下单保持 `deferred`，需独立法律、风控、安全与执行设计。
3. 可选清理项（非阻塞）：上述既有抖动与 `keep_alive` 未取回异常，如需处理应各自立任务并带自己的证据。
