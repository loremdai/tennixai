# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-13 17:53 CST

**当前任务：** T54 — Close Home Historical Player Queries

**任务状态：** `in_progress`

**执行者 / ADE：** Codex / Codex

**分支：** `main`

**任务起始提交：** `5d8e3f2`

**领取提交：** `259235c`

**当前动作：** 已落盘 [T54 设计规格](./docs/superpowers/specs/2026-09-13-tennixai-home-historical-player-query-closure-design.md)；当前只写设计，不修改产品代码。设计经用户确认后再编写实施计划和 Goal Prompt。

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
| 2026-09-13 | `259235c` | 领取 T54，锁定 `main` 与起始提交 `5d8e3f2` |
| 2026-09-13 | `5d8e3f2` | 记录 T53 最终验证；随后真实首页查询暴露 T54 验收缺口 |
| 2026-09-13 | `348110c` | T53 修复 Home 断言、配置重复和旧视觉基线 |
| 2026-09-13 | `7bbb541` | T52 真实服务与 P2.6 数据门证据入库 |
| 2026-09-13 | `501f229` | T51 球员页面接入真实结构化 API |

## 下一步

完成并提交 T54 设计规格，自审后交用户确认；未经确认不得写实施计划或修改产品代码。
