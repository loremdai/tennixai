# TennixAI 项目概况

> 本文件回答“这个项目是什么、为什么做、哪些原则不能被破坏”。
> 全局进度见 [ROADMAP.md](./ROADMAP.md)，唯一当前任务见 [CURRENT.md](./CURRENT.md)。

**最后更新：** 2026-09-09 17:55 CST

**产品阶段：** P1 — 比赛信息查询助手（已完成，2026-09-08）；P2 — Live Match Intelligence（实施中，P2.1 进行中）

**详细基线：** [产品与架构上下文](./docs/product-context.md) · [产品路线设计](./docs/superpowers/specs/2026-09-08-tennixai-product-roadmap-design.md) · [P1 实施计划](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md) · [P2 设计规格](./docs/superpowers/specs/2026-09-09-tennixai-p2-live-match-intelligence-design.md) · [P2 实施计划](./docs/superpowers/plans/2026-09-09-tennixai-p2-implementation.md)

## 5 分钟恢复入口

- TennixAI 不是通用网球聊天机器人，而是以结构化网球数据为核心、AI 作为交互层的数据与决策产品。
- Home 负责全局发现、搜索和赛程入口；Match Page 负责单场比赛的事实、上下文问答和后续智能能力。
- P1 已完成：fake 模式全链路确定性地跑通；真实 LiveTennisAPI provider、真实 Qwen 单项与组合门均通过；真实 live 列表现在只把有限摘要交给 LLM，完整结构化数据仍通过 SSE 交给 UI，LLM 请求有 45 秒可配置总时限，真实 Djokovic 查询的重复实名/组合名也已稳定处理。
- P1 只处理当前、即将开始和正在进行的比赛；P2 将增加 API-Tennis 按需的昨天/近期结果与 H2H，但不建设完整历史镜像。
- P2 设计已冻结：API-Tennis WebSocket 是实时主路径，PostgreSQL 保存长期 canonical 事实，Redis 负责租约、热状态和 pub/sub，FastAPI 通过版本化 SSE 服务浏览器。
- Home 默认展示 ATP + WTA、全部性别、单打，并允许赛事级别、性别、单双打叠加筛选；赛事按 ATP/WTA → Challenger → ITF → other 排序。
- Match Page 将提供完整 PBP、尽可能多的可信技术统计、近期控制指数和带 `state_version/as_of` 的上下文问答。
- P2 仍严格排除 odds、预测、Polymarket、交易、认证和云部署；完成目标是本地完整运行与少量好友私人测试。
- 不要从本文件猜当前做到哪里；以 [ROADMAP.md](./ROADMAP.md) 和 [CURRENT.md](./CURRENT.md) 为准。

## 产品定位

```text
Tennis Data / Intelligence Product
                +
     Conversational Interface
```

LLM 负责理解意图、选择业务工具和组织表达，不是网球事实来源。比分、赛程、球员、赛事、发球方、状态和内部 ID 必须来自结构化服务结果。

### Home Page

承担 Discovery、Search、Schedule、Live Now、Following，以及未来具备数据能力后的 Recent Results。典型输出是：简短回答 + Structured Match Card + Open Match。

### Match Page

承担单场 Investigation：比分、状态、发球方、上下文问答，以及 P2/P3 才会进入的统计、PBP、走势、市场和决策支持。页面必须携带内部 `match_id`，用户无需重复比赛上下文。

## 三阶段产品路线

| 阶段 | 目标 | 主要数据能力 | 明确边界 |
|---|---|---|---|
| P1 | 比赛信息查询助手 | 今日/今晚/下一场、赛事、轮次、场地、状态、比分、发球方 | 不做任意历史结果、技术统计和自动轮询 |
| P2 | Live Match Intelligence | API-Tennis live/PBP/statistics、近期控制指数、轻量历史/H2H，多进程持久化与协调 | 不接 odds、预测、市场或交易；不镜像完整供应商历史 |
| P3 | Market & Decision Support | Polymarket 市场、预测概率、edge、confidence、paper trading | 不自动下单；自动执行必须另立阶段并单独批准 |

## 稳定架构

```text
Provider
   ↓
Canonical Domain Model
   ↓
TennisService
   ↓
Feature / Prediction / Decision
   ↓
Chat + UI
```

以下内容应保持稳定：

- canonical domain model
- service contract
- provider interface
- feature / prediction / decision semantics
- 结构化事实与 LLM 文本的边界

以下内容允许替换：数据供应商、LLM、预测模型和前端实现。业务代码不得依赖 `event_key`、`event_first_player`、`score[0][1]` 等供应商字段。

P2 的实时依赖方向进一步固定为：

```text
API-Tennis REST/WebSocket
          ↓
Provider adapters
          ↓
Canonical reducer
          ↓
PostgreSQL + Redis coordination
          ↓
FastAPI snapshot/SSE + TennisService
          ↓
Next.js structured UI + Chat
```

## P1 已批准方案

- 前端：Next.js、TypeScript、Tailwind CSS、现有 v0 原型；原型是视觉真源。
- 后端：Python、FastAPI、Pydantic、httpx。
- 前后端边界：浏览器只请求 Next.js `/api/*`；Route Handler 薄代理 FastAPI，并透传 SSE。
- 数据：LiveTennisAPI Free；进程内 identity 与 bounded TTL cache；不接 PostgreSQL/Redis。
- 时间：canonical UTC；自然语言时间按 `Asia/Macau`，`tonight` 为有效或下一段 18:00–05:59。
- Chat：OpenAI-compatible Chat Completions + Qwen `qwen3.8-max-0902`；最多两轮工具调用。
- 业务工具：仅 `find_player_matches`、`get_live_matches`、`get_match`。
- 刷新：初次加载、用户提问和手动刷新；P1 不自动轮询。
- 测试：确定性 fake provider/fake LLM 为默认；真实 provider/LLM 为 opt-in；Playwright 覆盖功能与视觉。
- 视觉视口：桌面 `1440×1000`，移动端 `390×844`。

## P2 已批准方案

- 供应商：API-Tennis 同时承担 Home/Match REST 和 per-match WebSocket；P1 provider 保留为备用 adapter。
- 进程：FastAPI 与独立 Realtime Worker，同仓库共享 domain/repository，不拆微服务。
- 持久化：PostgreSQL 保存稳定 identity、live state、PBP、统计变化、近期控制指数和 provenance；raw payload 14 天清理。
- 协调：Redis 保存 viewer lease、demand index、hot snapshot 和 pub/sub；Redis 丢失可由 PostgreSQL + REST 恢复。
- 实时协议：初始完整 snapshot + 版本化 SSE 增量；缺口、重连或 stale 时 REST 重同步。
- 订阅：只订阅被观看的比赛；同一比赛共享上游连接；隐藏标签页 60 秒释放，最后 viewer 离开后保留 60 秒 grace。
- 历史：使用 API-Tennis fixtures/H2H 按需查询，短 TTL cache，不做全量历史回填。
- 统计：支持 22 个语义明确的 canonical 指标；未知、缺失、partial 不猜测、不当作零。
- 走势：Recent Control v1 使用发球校正残差、校准参数和 EWMA；最近 20 分只是展示窗口，关键分不使用固定倍率。
- 测试：确定性 Replay 为主要实时门；真实 API-Tennis REST/WebSocket 和真实 LLM 为 opt-in smoke；Playwright 覆盖功能与双视口视觉。
- 配置：仓库根目录 `.env` 是 FastAPI、Next.js、Playwright 和真实测试的唯一本地配置入口；安全变量模板只保留根目录 `.env.example`。

## P1 成功标准

P1 完成时，用户可以从 Home 提问，得到可信结构化比赛卡片，打开内部 ID 对应的 Match Page，并继续当前比赛上下文问答。支持的问题必须由确定性 REST 和 LLM 工具路径共同验证；模型或供应商失败不得生成虚构事实。

验收问题与逐项门槛见 [ROADMAP.md](./ROADMAP.md)。

## 权威与冲突规则

| 信息类型 | 权威来源 |
|---|---|
| 产品定位、范围、优先级 | `PROJECT.md` 与 `ROADMAP.md` |
| 当前任务、执行者、分支和交接 | `CURRENT.md` |
| 运行事实、实现状态 | 代码、测试结果与 Git HEAD |
| 详细设计和实施步骤 | `docs/` 下已链接的规格与计划 |

如果总控与代码、测试或 Git HEAD 不一致，以已验证的实现事实为准并立即修正总控。`docs/` 中的详细说明不能静默覆盖根目录总控中的产品边界或优先级。

## 维护规则

仅当产品边界、架构原则、技术基线或长期成功标准变化时更新本文件。任务进度不得写在这里；阶段和任务状态写入 `ROADMAP.md`，日常执行和交接写入 `CURRENT.md`。
