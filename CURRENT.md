# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-17 01:08 CST

**当前任务：** T68 — Connect Home Market Pulse and the `/markets` Discovery Workspace

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `808b87e`

**领取提交：** 本次提交（T67 关闭 + T68 领取记录）

**当前动作：** T67 已以 `808b87e` 交付：全部 P3 DTO 与 SSE 判别器的 runtime 解码（`P3DecodeError` 显式失败，未知 enum 不强制转换、decimal 保持字符串、缺失数据保持 null）、五个 REST 客户端方法与两个流解析器（不可解码帧转显式 `malformed` 事件不断流）、七个薄代理路由（force-dynamic、只导出 GET、query/status/SSE headers/Last-Event-ID 透传、upstream body 原样传递）、`useMarketStream`（ready snapshot-first 重基线；market sequence / decision observation_version 独立 cursor；只应用连续递增；gap 保留最后可信视图 + degraded + onGap 只重取该资源；FINAL resolution 冻结市场；heartbeat 超时 45s 与流错误重连并携带自身 Last-Event-ID）与 `useDecisionStream`（REST 权威 snapshot-first、404 诚实 null、version+1 delta 触发 REST 重取、gap/malformed 只重取 decision、组合 harness 证明永不触碰 `useMatchStream` cursor）。生产 transport 零 `p3-preview-data` import。现按 [P3 实施计划 T68](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t68-connect-home-market-pulse-and-the-markets-discovery-workspace) 以 TDD 实施 Home Market Pulse（≤3 行）与 `/markets` 三视图（Opportunities/All Markets/Paper Ledger）。

## 当前已验证状态

- T67 验收（全部实际运行）：焦点 71 passed（p3-types 27 + use-market-stream 12 + use-decision-stream 13 + p3-proxies 19）；前端全量 313 passed（P2 `use-match-stream`/`backend-proxy` 回归不变）；`pnpm typecheck` 干净。
- T66 验收保持：REST/SSE/Chat 契约 36 passed；确定性 backend 854 passed/76 deselected；infrastructure 45 passed（含 P3QueryService 对真实 PostgreSQL 证明与 paper-mode 装配 smoke：marker→`paper_delta` 端到端）。
- 前端流不变量已冻结：P2 sports 与 P3 decision cursor 相互独立；任一流 gap 只重取自身资源；最后可信视图带时间戳保留、新动作消失；重复/过期事件忽略；重连各自携带 Last-Event-ID。
- T57–T66 保持关闭；T56 视觉真源保持（52 张基线，不得批量接受 diff，T68/T69 页面须按 v0 原型几何实现）；P2 保持 `done`；真实下单明确延期。诚实缺口不变：T61 真实历史数据未接入、artifact 键对齐与 `match_info` 真实来源留待 T70/T71。
- 模型未晋升时生产必须 `NO BET`；不得伪造 `BUY`。前端只渲染服务端提供的 action/reason，绝不在 React 中计算 probability/edge/成交/结算。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-17 | `808b87e` | T67 完成：typed P3 transport、runtime 解码、七个薄代理、双独立 stream hooks；前端 313 passed |
| 2026-09-17 | `25e74d4`/`3ef0cd3` | T66 追加：paper publish 装配修复（marker→`paper_delta`）与 paper-mode 装配 smoke（真实 PostgreSQL+Redis） |
| 2026-09-17 | `78b2b16`/`13ade66` | T66 追加：P3QueryService 对真实 PostgreSQL 的 integration 证明与 lifecycle 累积历史修正 |
| 2026-09-16 | `f689045` | T66 关闭 + Claude 领取 T67 |
| 2026-09-16 | `be17eea` | T66 完成：只读 P3 REST、双独立 SSE、Chat 工具与真实 P3QueryService；P2 stream 契约不变 |

## 下一步

1. 完成 T68 的 TDD 实施与验收：`components/markets/{markets-page,markets-tabs,market-filters,opportunity-row,market-row,paper-row,markets-state}.tsx` + `app/markets/page.tsx`；Home Pulse 选择契约（1 行最紧急未结持仓预留 + live BUY → upcoming BUY → 最强 WAIT，上限 3 行，无轨迹/账本细节）；`/markets` 三视图（Opportunities 只含 model-covered BUY/WAIT；All Markets 含全部 mapped moneyline；Paper Ledger 只来自 ledger 不从浏览器重建）；Challenger/ITF 行展示市场数据且无负面标签；任何行不得出现 BUY/SELL 按钮；降级矩阵（loading 骨架、诚实空态、列表级传输失败、行级 stale/gap、market-only、book 不完整、closed/resolved——最后可信值带时间戳保留、新动作消失）；整行内部导航。
2. T68 验收命令：`pnpm test -- components/markets/markets-page.test.tsx components/home-intelligence.test.tsx components/home-page.test.tsx`；Playwright `e2e/p3-markets.spec.ts`（直达/各 tab/filter、Home→Markets、Home/Markets→Match、刷新重连、390×844 无横向溢出、键盘 tab、44px 移动目标）；`pnpm typecheck` + `pnpm build` + 前端全量。
3. T68 关闭后按同一流程领取 T69（Match workbench），顺序执行至 T71。
