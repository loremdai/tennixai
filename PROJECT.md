# TennixAI 项目概况

> 本文件回答“这个项目是什么、为什么做、哪些原则不能被破坏”。
> 全局进度见 [ROADMAP.md](./ROADMAP.md)，唯一当前任务见 [CURRENT.md](./CURRENT.md)。

**最后更新：** 2026-09-09 16:28 CST

**产品阶段：** P1 — 比赛信息查询助手（已完成，2026-09-08）；P2 — Live Match Intelligence（设计冻结进行中）

**详细基线：** [产品与架构上下文](./docs/product-context.md) · [产品路线设计](./docs/superpowers/specs/2026-09-08-tennixai-product-roadmap-design.md) · [P1 实施计划](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md) · [T16 真实运行时硬化计划](./docs/superpowers/plans/2026-09-08-tennixai-t16-real-runtime-hardening.md)

## 5 分钟恢复入口

- TennixAI 不是通用网球聊天机器人，而是以结构化网球数据为核心、AI 作为交互层的数据与决策产品。
- Home 负责全局发现、搜索和赛程入口；Match Page 负责单场比赛的事实、上下文问答和后续智能能力。
- P1 已完成：fake 模式全链路确定性地跑通；真实 LiveTennisAPI provider、真实 Qwen 单项与组合门均通过；真实 live 列表现在只把有限摘要交给 LLM，完整结构化数据仍通过 SSE 交给 UI，LLM 请求有 45 秒可配置总时限，真实 Djokovic 查询的重复实名/组合名也已稳定处理。
- P1 只处理当前、即将开始和正在进行的比赛；任意历史结果查询明确返回 `unsupported`。
- P2 已明确启动设计冻结：目标是 API-Tennis 驱动的实时技术统计、PBP、近期控制指数和比赛上下文问答；设计落盘前不开始实现。
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
| P2 | Live Match Intelligence | 技术统计、PBP、Momentum、更细实时状态，多进程持久化与协调 | 历史支持需单独决策，不因接数据库而自动进入 |
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
