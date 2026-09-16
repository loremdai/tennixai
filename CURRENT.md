# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-17 00:02 CST

**当前任务：** T67 — Add Typed Frontend Transport, Thin Proxies, and Independent Stream Hooks

**任务状态：** `in_progress`

**执行者 / ADE：** Claude (Fable 5) / Claude Code（用户已明确授权按顺序连续执行 T57–T71，无需逐项再次确认）

**分支：** `main`

**任务起始提交：** `be17eea`

**领取提交：** 本次提交（T66 关闭 + T67 领取记录）

**当前动作：** T66 已以 `be17eea` 交付：七个只读 P3 REST 端点（opportunities/markets/paper positions/pulse/match decision + markets/decision 双独立 SSE）、两个只读 Chat 工具（bounded canonical fact packet、match_id 只取自冻结上下文）、真实 `P3QueryService`（PostgreSQL ledger 权威 + Redis hot book 仅补 best bid/ask，缺失降级 None 不补零）并装配进 `main.py`（`app.state.p3_queries/p3_redis`、`BusinessTools(p3_queries=…)`）；p3 disabled 时全部 typed 503 `p3_disabled`、Chat 目录过滤 P3 工具；SSE 契约用真实 uvicorn server 测试（ASGITransport 缓冲流），decision stream 携带自身 version cursor、重连 snapshot-first、gap 只重取 decision、严格过滤他场事件；P2 `/matches/{id}/stream` 字节级回归不变；公共 body/header/error 零 provider/wallet/token 片段。现按 [P3 实施计划 T67](./docs/superpowers/plans/2026-09-16-tennixai-p3-implementation.md#t67-add-typed-frontend-transport-thin-proxies-and-independent-stream-hooks) 以 TDD 实施前端 typed transport、Next 薄代理与独立 stream hooks。

## 当前已验证状态

- T66 验收（全部实际运行）：焦点 36 passed（REST 契约 12 + market stream 3 + decision stream 7 + chat tools 6 + P2 stream 回归 8）；确定性 backend 849 passed/73 deselected；infrastructure 42 passed；新文件 ruff check+format 干净（`app/service.py`、`app/api/routes.py` 的 format diff 为 HEAD 已存在的任务前债务，经 `git show HEAD` 基线对照确认）。
- P3 API 不变量已冻结：内部 ID only；`markets/stream` 与 `decision/stream` 各自独立 cursor（frame id = market sequence / observation version）；ready 帧 snapshot-first；decision gap 只重取 decision 状态；Chat 工具只读、bounded、不可创建 intent/改 policy/覆盖 structured action；p3 disabled → typed 503。
- T57–T65 保持关闭；T56 视觉真源保持（52 张基线，不得批量接受 diff）；P2 保持 `done`；真实下单明确延期。诚实缺口不变：T61 真实历史数据未接入、artifact 键对齐与 `match_info` 真实来源留待 T70/T71 集成验证。
- 模型未晋升时生产必须 `NO BET`；不得伪造 `BUY`。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-16 | `be17eea` | T66 完成：只读 P3 REST、双独立 SSE、Chat 工具与真实 P3QueryService；P2 stream 契约不变 |
| 2026-09-16 | `aa2349d` | T65 关闭 + Claude 领取 T66 |
| 2026-09-16 | `8cc3c26` | T65 完成：双流决策编排、durable tracking demand、P3 指标与本地延迟门；P3.3 关闭 |
| 2026-09-16 | `d5ae409` | T64 完成：one-shot FOK paper lifecycle、provider-final settlement、并发/崩溃恢复 |
| 2026-09-16 | `6012fcc` | T63 完成：可执行 quote、versioned policy、决策引擎全 hard-gate 表 |

## 下一步

1. 完成 T67 的 TDD 实施与验收：`frontend/lib/api/types.ts`（全部 P3 DTO runtime 解码、未知 enum 显式失败不强制转换）、`client.ts` 方法、`useMarketStream`/`useDecisionStream`（snapshot-first、只应用 version+1、重复/过期忽略、gap/malformed 保留最后可信视图并标记 degraded 只重取自身、重连携带各自 last event ID、`useDecisionStream` 永不改动 `useMatchStream` cursor）、Next 薄代理路由（保留 query/status/SSE headers/cancellation、拒绝非 GET、零缓存零业务状态）；样例数据只留在 `p3-preview-data.ts`，生产 transport 不得 import。
2. T67 验收命令：`cd frontend && pnpm test -- lib/api/p3-types.test.ts hooks/use-market-stream.test.tsx hooks/use-decision-stream.test.tsx app/api/p3-proxies.test.ts`，随后 typecheck + 既有 match-stream 回归 + 全部前端测试。
3. T67 关闭后按同一流程领取 T68（Home Pulse + `/markets` 三视图），顺序执行至 T71。
