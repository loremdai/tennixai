# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-22 16:07 CST

**当前任务：** T84 — Add Active-Link Market Overview Projection

**任务状态：** `in_progress`

**执行者 / ADE：** Claude Code（Opus 5）

**分支：** `main`

**起始提交：** `89de518`

**当前动作：** 用户已于 2026-09-22 书面确认 [P4.3 规格](./docs/superpowers/specs/2026-09-22-tennixai-p4-market-data-truthfulness-and-coverage-design.md)，T83 以设计冻结关闭。本轮先写 T84–T89 详细实施计划并自审，再按顺序执行：T84 以 `market_match_links.status='active'` 为唯一 market→match 查询真相，恢复 link 导航/tier/phase 并消除 Markets 查询 N+1。

## T84 范围与硬边界

- `market_match_links.status='active'` 是 market→match 的唯一查询真相；不回填、不依赖冗余 `markets.match_id` 制造第二份真相。
- link、match facts、latest quote 与 prediction/decision 一次批量加载；禁止每行 N+1 SQL 或 Redis 调用。
- 只有 active link 才产生内部 Match Page 导航；无 link 行保留 canonical 市场信息，但不得出现错误导航。
- 本轮只做 read model 与查询投影：不引入 snapshot 采集、WebSocket roster 扩容、模型晋升、decision/paper 语义变化。

## 受保护的既有未跟踪文件

不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-22 | 本提交 | 用户书面确认 P4.3 规格后，T83 以设计冻结关闭；T84 已领取：Claude Code（Opus 5）、`main`、起始 `89de518` |
| 2026-09-22 | `89de518` | T83 规格草案与三份总控记录已推送；规格已获用户书面确认，可写实施计划与产品代码 |
| 2026-09-22 | `8ffba5e` | T83 规格草案、P4.3 路线和三份总控已推送；当时仍在等待用户书面审阅 |
| 2026-09-22 | `cccf604` | T83 已领取：Codex、`main`、起始 `f1840b7`；只做 P4.3 双通道市场数据设计冻结 |
| 2026-09-18 | `2cea490` | T82 关闭：启动器直接运行已安装 Next；普通 up/API/frontend/down 真实门通过；三份总控同步 |

## 下一步

1. 写完并自审 T84–T89 详细实施计划，提交并推送。
2. 按 T84→T89 顺序逐项实现、验证、提交并推送；每个任务的领取、节点、完成与交接更新三份总控。
3. T89 完成确定性/integration/frontend/E2E、有界真实本地 coverage gate、runbook 与总控收口后，本文件不再有 active 任务。
4. P4.3 完成后单独排期模型晋升证据链；自动下单继续 `deferred`。