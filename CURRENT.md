# TennixAI 当前任务与交接

> 这是给项目参与者快速接手的状态摘要。阶段计划与长期证据见 [ROADMAP.md](./ROADMAP.md)，产品稳定约束见 [PROJECT.md](./PROJECT.md)。

**最后更新：** 2026-09-23 20:23 CST

**当前任务：** T91 — Diagnose and Restore Polymarket Quote Refresh

**任务状态：** `in_progress`（实现与验收完成；最终提交、推送和状态关闭待完成）

**执行者 / ADE：** Codex；**分支：** `main`
**起始提交：** `5ee62ed`

## 当前进展

完成了 Gamma 完整目录、市场安全退役、未映射/双打真实报价展示、REST 快照轮转、独立只读行情 WebSocket、报价变化 SSE，以及 `/markets` 分页和 Load more。用户选定的边界保持：所有活跃网球胜者市场展示供应商真实名称/报价；未严格映射的场次不进入模型、机会或 Paper。机会页在模型未晋升时仍诚实为空。

最终实现与验收证据见 [T91 实施计划](docs/superpowers/plans/2026-09-23-tennixai-polymarket-quote-refresh-implementation.md)。剩余工作仅为最终 diff 检查、提交并推送，再将 T91 标记为 `done`。

## 已验证结果

- 后端确定性测试：`1223 passed, 122 deselected`；隔离 PostgreSQL 集成测试：`19 passed`。
- 前端：Vitest `410 passed`；TypeScript、生产 build 通过。
- Playwright：功能 `92 passed / 40 gated skips`；视觉 `34 passed / 4 gated skips`；批准的视觉截图无变化。
- Gamma/CLOB 无凭据只读核验成功；样本的两个 outcome 均返回真实报价。未输出供应商标识或原始 payload。
- 官方 WebSocket 文档确认 `best_bid_ask`、`custom_feature_enabled` 与 10 秒应用心跳：[Polymarket Realtime Data](https://docs.polymarket.com/market-data/realtime-data)。
- Ruff lint 与 `git diff --check` 通过。3 个历史文件在 `origin/main` 上已有 Ruff formatter 差异；未做大范围无关重排。

## 环境与保护

- 完整项目应用未启动；Playwright 临时服务已退出，3100/8000 端口关闭。
- 本任务创建的隔离数据库 `tennix_t91_test` 已删除。PostgreSQL/Redis 容器早于本任务创建，保留运行。
- `.env` 未改。不得修改、删除或提交用户原有未跟踪内容：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 下一步

完成 T91 提交与推送后，等待用户安排下一项工作。模型晋升证据链需要单独设计和授权；自动下单继续 `deferred`。
