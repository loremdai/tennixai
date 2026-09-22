# TennixAI 当前任务与交接

> 本文件只保留当前交接和最近必要记录；长期历史以 `ROADMAP.md` 与 Git 历史为准。

**最后更新：** 2026-09-22 15:50 CST

**当前任务：** T83 — Freeze Market Data Truthfulness & Coverage Design

**任务状态：** `in_progress`（仅设计冻结；没有产品实现授权）

**执行者 / ADE：** Codex

**分支：** `main`

**起始提交：** `f1840b7`

**当前动作：** [P4.3 设计规格](./docs/superpowers/specs/2026-09-22-tennixai-p4-market-data-truthfulness-and-coverage-design.md)已写入并完成自审；正在整理交给另一 ADE 的 Goal Prompt。当前任务只修改文档和三份总控；不启动服务、不改业务代码、不调用真实 LLM/API。规格仍等待用户书面审阅，之后才能写实施计划或开始 T84。

## T83 范围与硬边界

- 修复已验证的 read-model 脱节：`market_match_links` 的有效映射必须成为 Markets 查询的权威来源，不能继续只读历史 `markets.match_id`。
- 将“全部市场”的广覆盖报价与“模型/决策实时链路”分离：前者用有界公开 batch snapshot，后者只跟踪严格映射、合格的主巡单打市场。
- 页面必须如实区分实时报价、快照报价、无挂单、暂不可用和过期报价；`机会`在模型未晋升时应显示原因明确的空态，不能伪造 BUY/WAIT。
- 不改变 P3 的 paper-only、只读 Polymarket、无钱包/签名/下单、未晋升模型不得产生 BUY/SELL、严格 mapping、14 天 raw 保留和批准视觉真相边界。
- 不在 T83 编写、重构或运行产品代码；T84–T89 的实现必须等待本规格、详细计划与用户交接确认。

## 已验证的设计输入

- 当前公开市场查询有 181 个市场、162 个 active `market_match_links`，但 `MarketRow.match_id` 为 null，导致已映射市场在 API/UI 侧看起来未映射。
- 当前只有少量市场有 `book_change` observation；其余市场没有广覆盖 quote，因此页面显示 `—`。这不是“没有市场”，而是现有实时订阅只覆盖决策追踪子集。
- 当前模型为 `not_promoted`，没有 prediction/decision；因此 Opportunities 的空数组符合既有安全设计，但空态没有把原因讲清。
- 运行诊断还记录了 market WebSocket normal-close/keepalive 异常与 queue overflow；在扩大实时订阅前必须纳入稳定性和恢复验证。

## 受保护的既有未跟踪文件

不得修改、删除或提交：`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-22 | 待本次提交 | T83 已领取：Codex、`main`、起始 `f1840b7`；只做 P4.3 双通道市场数据设计冻结 |
| 2026-09-18 | `2cea490` | T82 关闭：启动器直接运行已安装 Next；普通 up/API/frontend/down 真实门通过；三份总控同步 |
| 2026-09-18 | `7b0bf13` | T81 关闭：功能并行/视觉串行两条 E2E lane；默认 Playwright 连续两次 110/44/0，PNG 零 diff |
| 2026-09-18 | `2270049` | P4.1 关闭：T80 `done`，真实 init/verify/浏览器/重启持久性门完成 |

## 下一步

1. 向用户交付规格链接及 ≤4000 字符的 Goal Prompt，等待用户书面审阅和确认。
2. 用户审阅规格后，下一执行者领取 T84，先写详细实现计划，再按 T84–T89 的顺序执行和验证。
3. P4.3 完成后再单独排期模型晋升证据链；自动下单继续 `deferred`。
