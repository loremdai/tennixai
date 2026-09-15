# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-15 11:24 CST

**当前任务：** T55 — Freeze P3 Market & Decision Support Design and Prototype Brief

**任务状态：** `in_progress`

**执行者 / ADE：** Codex / Codex Desktop

**分支：** `main`

**任务起始提交：** `7409806`

**领取提交：** `b6539e4`

**设计提交：** —

**产品提交：** —（T55 只授权设计，不授权实现）

**关闭提交：** —

**当前动作：** 继续 P3 架构级设计讨论。已确认赛前与赛中使用同一概率轨迹、第一版只做单场比赛胜者市场，并以“当前买入并持有至结算”隔离验证预测与入场质量；下一步确认市场映射、模型评估、decision/abstention、paper ledger、实时数据流、页面信息架构、v0 原型范围和验收路线。设计获批前不写实现代码。

**当前状态：** P2（含 T54）保持已关闭；P3.0 仅进入 design freeze。P4 已确定为 P1–P3 框架完成后的统一打磨阶段，可基于证据优化模型、阈值、仓位管理、体验和性能；当前没有 P3 provider、schema、prediction、decision、paper ledger、页面或交易能力，自动下单仍属独立延期阶段。

## 上一任务 T54 完成证据（2026-09-13）

- 确定性后端：`543 passed / 51 deselected`；infrastructure `22 passed / 572 deselected`。
- 前端：`pnpm test` 228 passed；`pnpm typecheck` 干净；`pnpm build` 编译成功。
- 全量 Playwright（fake）：`62 passed / 34 skipped / 0 failed`（exit 0）；新增 `home-history-answer.png` 桌面/移动两张基线逐张审阅通过，既有基线零变化（git 仅新增）。
- 确定性 home-history e2e：功能 4 + 视觉 2（双视口），连续复跑稳定。
- 真实 API-Tennis：`api_tennis_live` 2 passed。
- 真实 LLM（确定性 provider）：`llm_live` 19 passed，含 5 项 T54 内容断言（last/recent/season scope、多球员双 data event、与同次 service probe 逐 ID 相等）。
- 真实 API+LLM 同运行后端：`player_directory_e2e_live` 4 passed（probe-vs-Chat 不变量：内部身份、scope、finished 倒序、赛季记录；一次 supplier 同步抖动的诚实 skip 复跑全过）。
- 真实浏览器（api_tennis + 真实 LLM）：`player-directory-live.spec.ts` 20 passed，5 个历史场景内容级断言（section 数/双语标题/scope 徽章/内部链接/空态文案/SSE done/无 error 帧/无控制台错误/无 payload 泄漏）。
- 边界：`git diff --check` 干净；diff 无供应商字段/凭据；产品代码无 P3 术语；工作区仅 5 项受保护未跟踪项。
- 顺带修复 T50 遗留契约错位：Chat `player_resolution` SSE 为嵌套域形状，Home 候选链接曾以 undefined id 渲染（React key 警告 + `/players/undefined`）；现按内部 ID 渲染并有单测与 live 复验。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-15 | `b6539e4` | T55 领取：P3.0 进入 design freeze，仅授权设计讨论与规格，不授权实现 |
| 2026-09-13 | `86ea404` | T54 关闭：P2.6/P2 重新 done，P3 恢复 ready for design（未开始） |
| 2026-09-13 | `8d1233f` | Task 6 真实内容门 + 修复 T50 候选链接契约错位 |
| 2026-09-13 | `4b23f1b` | Task 5 Home 历史分组渲染与两张专用视觉基线 |
| 2026-09-13 | `edb2b89` / `8818304` | Task 4 dataItems 聚合 / Task 3 typed player_history |

## 下一步

继续 T55 的单问题设计讨论；经用户逐段批准后写入 P3 设计规格并提交，随后由用户审阅。规格获批前不得编写实施计划、修改 v0 原型或实现 P3 功能。
