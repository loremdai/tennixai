# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-13 18:12 CST

**当前任务：** T54 — Close Home Historical Player Queries

**任务状态：** `in_progress`

**执行者 / ADE：** Claude Code / Claude Code ADE（用户显式交接，接替 Codex）

**分支：** `main`

**任务起始提交：** `5d8e3f2`

**领取提交：** `259235c`（Codex）；本次 ADE 接手领取提交见本提交（接手起始提交 `559fdf7`，2026-09-13 18:12 CST）

**设计提交：** `831459b`

**当前动作：** 用户已把 T54 显式交接给当前 Claude Code ADE。接手后按 [T54 实施计划](./docs/superpowers/plans/2026-09-13-tennixai-home-historical-player-query-closure.md) 从 Task 1 起严格 TDD 执行 Task 1–7，每个任务独立提交并推送 `origin/main`。

**当前状态：** 真实首页查询已证明 P2.6 的多语言 PlayerResolver 可用，但历史意图、最近一场/近期/赛季语义、多球员结构化结果和内容级真实验收未闭环。P3 保持 `planned`，T54 完成前不进入 P3 设计。

## 已验证问题事实

- “上一次”和“赛果”未命中历史意图守卫，导致 `get_player_results` 不进入模型工具目录。
- API-Tennis 当前真实数据中，郑钦文最近 30 天有 8 场已结束比赛；页面却回答无近期结果，证明问题位于 Chat 路由而非供应商数据或名称解析。
- Sinner 2026 赛季有历史赛果，但最近一场超出 Chat 固定 30 天窗口；“上一场”不能等同于“最近 30 天”。
- 后端可连续发送多条 SSE `data`，前端 `useChatStream` 当前只保留最后一条，多球员结果会相互覆盖。
- 现有真实 LLM/浏览器门只检查非空文字、无 error 和 `done`，没有断言回答包含正确结构化历史事实。

## T54 已批准边界

- 采用方案 A：补齐意图、历史查询语义、typed structured result、多球员 SSE 聚合、Home 展示和内容级真实验收。
- 复用 PlayerResolver、API-Tennis 按需赛果、现有五赛季窗口与缓存。
- 不新增数据库迁移、历史镜像、RAG、运行时翻译、双打或任何 P3 能力。
- T53 保留为当时已完成的历史事实；T54 完成后重新关闭 P2.6 并恢复 P3 readiness。

## 未跟踪文件保护

以下既有未跟踪文件/目录不得修改、删除或提交：`.codex/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-13 | 本提交 | 用户显式交接：T54 执行者由 Codex 改为 Claude Code ADE，接手起始提交 `559fdf7`，开始按计划执行 Task 1–7 |
| 2026-09-13 | `831459b` | 冻结并推送用户确认的 T54 方案 A 设计规格 |
| 2026-09-13 | `259235c` | 领取 T54，锁定 `main` 与起始提交 `5d8e3f2` |
| 2026-09-13 | `5d8e3f2` | 记录 T53 最终验证；随后真实首页查询暴露 T54 验收缺口 |
| 2026-09-13 | `348110c` | T53 修复 Home 断言、配置重复和旧视觉基线 |

## 下一步

接手 ADE（Claude Code）从 Task 1 起逐项执行 [T54 实施计划](./docs/superpowers/plans/2026-09-13-tennixai-home-historical-player-query-closure.md)：确定性能力路由 → 五赛季 last/recent 与 profile-only 赛季战绩 → typed `player_history` Chat/SSE → 前端 `dataItems` 聚合 → Home 历史分组展示与两张专用视觉基线 → 真实 API/LLM/浏览器内容级验收 → 全量关闭门与总控更新。T54 全部门通过前不得开始 P3。
