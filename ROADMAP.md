# TennixAI 项目总路书

> 本文件回答“项目要经过哪些阶段、现在整体走到哪里、每项完成有什么证据”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，唯一当前任务见 [CURRENT.md](./CURRENT.md)。

**最后更新：** 2026-09-08

**总体状态：** `in_progress`

**当前里程碑：** P1 — 比赛信息查询助手

**当前阶段：** P1.1 — Foundation

## 状态说明

| 状态 | 含义 |
|---|---|
| `planned` | 已进入路线，但尚未达到可领取条件 |
| `ready` | 前置条件已满足，可以成为唯一当前任务 |
| `in_progress` | 正由 `CURRENT.md` 记录的唯一执行者推进 |
| `blocked` | 已开始但被明确条件阻塞 |
| `done` | 验收实际通过，且附有提交和证据 |
| `deferred` | 经明确决策推迟，不属于当前执行序列 |

同一时间最多一个任务可以标记为 `in_progress`。只有验收命令实际通过后才能标记 `done`。

## 总体路线

| 里程碑 | 状态 | 目标 | 进入/完成条件 |
|---|---|---|---|
| P1 — Match Information Assistant | `in_progress` | 跑通真实结构化比赛查询、卡片、Match Page 与上下文 Chat | 完成 P1.0–P1.6 和 P1 验收矩阵 |
| P2 — Live Match Intelligence | `planned` | 技术统计、PBP、Momentum、持久化和多进程实时协调 | P1 全部门通过；API-Tennis 能力与迁移设计另行批准 |
| P3 — Market & Decision Support | `planned` | 市场状态、预测、edge、confidence 和 paper trading | P2 数据可信；映射、模型评估和风控设计另行批准 |
| Optional — Automated Execution | `deferred` | 在满足法律、风控、安全和可审计条件后考虑自动下单 | 不属于 P3 默认范围，必须单独批准 |

## P1 阶段状态

| 阶段 | 状态 | 核心交付 | Exit gate / 当前缺口 |
|---|---|---|---|
| P1.0 — Design freeze | `done` | 架构路线、原型状态清单、桌面/移动视觉基线 | 已完成：10 张基线入 Git（最终版 `c035f5a`，排除 dev overlay），重建后连续复跑 10/10，build exit 0 |
| P1.1 — Foundation | `in_progress` | FastAPI、配置、健康检查、测试骨架、Next.js 薄代理 | T02 已完成（`8b15efe`）；剩余 T09 薄代理与 SSE smoke |
| P1.2 — Domain and provider | `in_progress` | canonical models、provider protocol、fake/live adapters、进程内 identity | T03 已完成（`5ed8a18`）；剩余 T04 fake provider、T05 live adapter、T06 cache |
| P1.3 — Service and REST | `planned` | TennisService、时间语义、缓存、确定性 REST | 不经 LLM 也能回答所有受支持 P1 事实问题，边界错误有确定性测试 |
| P1.4 — Real frontend data | `planned` | typed client、Home、动态 Match Page、加载/错误/刷新状态 | Home → Match 真实链路通过，内部 ID 正确，视觉回归受控 |
| P1.5 — Conversational path | `planned` | 三个业务工具、Qwen tool loop、SSE、全局与比赛 Chat | Chat 与 REST 使用同一事实；LLM/供应商失败不产生虚构结果 |
| P1.6 — Acceptance and hardening | `planned` | 验收集、真实服务 opt-in 测试、Playwright、runbook | 全部确定性门通过；可用 live gates 通过；无 P1 范围膨胀 |

详细阶段设计见 [产品路线设计 §12](./docs/superpowers/specs/2026-09-08-tennixai-product-roadmap-design.md#12-p1-execution-roadmap)。

## P1 任务登记表

任务按实施顺序排列。详细步骤只存在于 [P1 实施计划](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md)，此处只维护状态和完成证据。

| ID | 主要阶段 | 任务 | 状态 | 完成提交 | 验收证据 |
|---|---|---|---|---|---|
| T01 | P1.0 | Freeze the Existing Prototype Visually | `done` | `c035f5a` | 10 张桌面/移动基线入 Git（排除 dev overlay）；重建后 `--update-snapshots` 10/10 + 连续两次 plain 复跑 10/10；`pnpm build` exit 0；10 张 PNG 逐张审阅；历史：首版 `d13d6dd`、回退重开 `c37ad36`（2026-09-08） |
| T02 | P1.1 | Establish the FastAPI Foundation | `done` | `8b15efe` | `uv run pytest tests/test_health.py -v` 1/1 通过（health 200 `{"status":"ok","service":"tennix-api"}`、`X-Request-ID` 原样透传）；`uv run python -c "from app.config import Settings; print(Settings(_env_file=None).llm_model)"` 输出恰为 `qwen3.8-max-0902`，无凭据打印；uv.lock 已入库（2026-09-08） |
| T03 | P1.2 | Define Canonical Models and In-Memory Identity | `done` | `5ed8a18` | `uv run pytest tests/test_domain.py tests/test_identity.py -v` 10/10 通过（naive datetime 拒绝、frozen/extra=forbid、内部 ID 稳定可逆且不含外部 ID、三前缀 mat_/ply_/trn_）；全套确定性 suite 11/11 通过（2026-09-08） |
| T04 | P1.2 | Add the Provider Contract and Deterministic Fake | `ready` | — | — |
| T05 | P1.2 | Implement the LiveTennisAPI Adapter | `planned` | — | — |
| T06 | P1.2/P1.3 | Add the Bounded Async TTL Cache | `planned` | — | — |
| T07 | P1.3 | Implement TennisService and Time Semantics | `planned` | — | — |
| T08 | P1.3 | Expose Deterministic REST APIs | `planned` | — | — |
| T09 | P1.1/P1.4 | Add Thin Next.js Route Handler Proxies | `planned` | — | — |
| T10 | P1.5 | Define Chat Models, Historical Guard, and Business Tools | `planned` | — | — |
| T11 | P1.5 | Add the OpenAI-Compatible Tool Loop and SSE Route | `planned` | — | — |
| T12 | P1.4/P1.5 | Add Typed Frontend API, SSE Parsing, and View Models | `planned` | — | — |
| T13 | P1.4 | Connect Home to Real Structured Data Without Redesigning It | `planned` | — | — |
| T14 | P1.4/P1.5 | Add the Internal-ID Match Page and Contextual Chat | `planned` | — | — |
| T15 | P1.6 | Complete Browser E2E, Live Gates, and the P1 Runbook | `planned` | — | — |

## P1 验收矩阵

| 用户问题 | 预期结果 |
|---|---|
| 今晚 Sinner 几点打？ | 解析球员与澳门本地时间，返回结构化比赛卡片 |
| Alcaraz 今天有比赛吗？ | 确定性 yes/no 或消歧，并附 canonical data |
| Djokovic 下一场对谁？ | 返回最早的非终态比赛和对手 |
| 这是什么赛事？ | 当前比赛赛事或明确 unavailable |
| 第几轮？ | 当前比赛轮次或明确 unavailable |
| 什么场地？ | 当前比赛场地或明确 unavailable |
| 比赛开始了吗？ | canonical lifecycle status |
| 现在比分多少？ | canonical score 与 freshness |
| 谁在发球？ | canonical server 或明确 unavailable |
| 昨天 Sinner 赢了吗？ | typed `unsupported`，不得猜测 |

## 长期边界与升级触发

- PostgreSQL：P2 在需要跨重启身份、观察历史和稳定映射时设计并引入。
- Redis：P2 在需要多 worker 共享缓存、配额、polling lock 和事件分发时引入。
- 自动轮询：P2 基于比赛生命周期和供应商配额单独设计。
- 历史结果：只有确认数据 entitlement 与保存策略后才进入，不因接数据库自动获得。
- 自动交易：不属于 P3 默认范围，必须经过独立法律、风控、安全和执行设计。

## 更新纪律

- 阶段、任务、顺序、验收门或延期决策改变时更新本文件。
- 标记 `done` 时必须同时写入完成提交与实际验证证据。
- 任务的执行者、工作分支、当前动作和阻塞只写入 `CURRENT.md`。
- 完整变更历史由 Git 保存；本文件不追加逐日流水账。
