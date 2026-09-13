# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-13 20:42 CST

**当前任务：** T54 — Close Home Historical Player Queries

**任务状态：** `done`

**执行者 / ADE：** Claude Code / Claude Code ADE（用户显式交接，接替 Codex）

**分支：** `main`

**任务起始提交：** `5d8e3f2`

**领取提交：** `259235c`（Codex）；ADE 接手领取 `8e0b706`（接手起始提交 `559fdf7`，2026-09-13 18:12 CST）

**设计提交：** `831459b`

**产品提交：** `7a66e6a`（Task 1 能力路由）、`eef5724`（Task 2 五赛季语义）、`8818304`（Task 3 typed player_history）、`edb2b89`（Task 4 dataItems 聚合）、`4b23f1b`（Task 5 Home 分组渲染+双基线）、`8d1233f`（Task 6 真实内容门+候选链接修复）

**当前动作：** T54 已按 [实施计划](./docs/superpowers/plans/2026-09-13-tennixai-home-historical-player-query-closure.md) Task 1–7 全部完成并关闭；P2.6 与 P2 重新关闭，P3 恢复 `planned / ready for design`，未开始任何 P3 设计。

**当前状态：** Home 历史球员问答闭环：确定性能力路由（`app/chat/history.py`）、last/recent 五赛季按需语义与 profile-only 赛季战绩、typed `player_history` Chat/SSE、前端 `dataItems` 多结果聚合、Home 分组历史展示与两张专用视觉基线、真实 API-Tennis + 真实 Qwen + 真实浏览器内容级验收全部通过。

## T54 完成证据（2026-09-13）

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
| 2026-09-13 | 本提交 | T54 关闭：P2.6/P2 重新 done，P3 恢复 ready for design（未开始） |
| 2026-09-13 | `8d1233f` | Task 6 真实内容门 + 修复 T50 候选链接契约错位 |
| 2026-09-13 | `4b23f1b` | Task 5 Home 历史分组渲染与两张专用视觉基线 |
| 2026-09-13 | `edb2b89` / `8818304` | Task 4 dataItems 聚合 / Task 3 typed player_history |
| 2026-09-13 | `eef5724` / `7a66e6a` / `8e0b706` | Task 2 五赛季语义 / Task 1 能力路由 / ADE 接手领取 |

## 下一步

无进行中任务。P3（Market & Decision Support）已恢复 `planned / ready for design`，但必须经用户显式授权后才能领取设计任务；领取前按根目录入口重新核对 Git 与总控状态。
