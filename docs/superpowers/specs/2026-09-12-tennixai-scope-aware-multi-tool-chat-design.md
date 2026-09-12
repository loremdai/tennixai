# TennixAI 作用域感知的多工具对话编排设计

**日期：** 2026-09-12
**任务：** T39 — 设计并实现作用域感知的多工具对话编排
**状态：** 已获用户在会话中批准，待书面 spec 复核后实现

## 1. 背景与问题证据

TennixAI 当前的 `ChatOrchestrator` 已经有工具循环，也把 `ModelTurn.tool_calls` 定义成列表，因此代码并非从类型层面只能执行一个工具。但 OpenAI 兼容客户端的 `choose()` 没有发送 `parallel_tool_calls`，而阿里云 Model Studio 的 OpenAI 兼容接口默认值为 `false`；在没有显式开启时，Qwen 通常只返回一个工具调用。

当前更严重的问题是工具目录的作用域不完整：`_catalog_for_request()` 只对 `match` scope 做裁剪，`global` scope 仍会看到全部工具，包括只能依赖比赛页面上下文的 `get_match_intelligence`。真实浏览器中输入“tiafoe 的比赛如何了”时，已观察到以下稳定链路：

1. 第一个工具调用成功，SSE 先返回结构化比赛数据。
2. 模型在下一轮继续调用 `get_match_intelligence`。
3. 请求仍是 global scope，没有 `match_id`，业务工具返回 `invalid_request`。
4. 前端同时保留已成功的比赛卡片和错误状态，于是用户看到“卡片有了，但查询失败”。

这不是网络或 API key 错误：backend 和 Next 代理均返回 HTTP 200，失败发生在 SSE 应用事件中。当前回归测试 `tests/test_chat_orchestrator.py` 与 `tests/test_chat_api.py` 共 25 项通过，但没有覆盖“首个工具成功后，模型第二轮选择非法 scope 工具”的真实模型行为。

设计依据：

- [阿里云 Model Studio Function Calling 官方文档](https://help.aliyun.com/en/model-studio/qwen-function-calling)规定 Function Calling 是多步交互，并明确建议无依赖工具使用并行调用、有依赖工具使用串行循环；同时建议在模型前增加工具路由层。
- [阿里云 OpenAI 兼容 Chat Completions 官方文档](https://help.aliyun.com/en/model-studio/qwen-api-via-openai-chat-completions)规定 `tools`、`tool_choice` 和 `parallel_tool_calls` 的兼容参数语义，其中 `parallel_tool_calls` 默认关闭。

## 2. 目标与非目标

### 2.1 目标

- 全局请求永远不能调用 match-only 工具。
- 同一轮中无输入依赖的多个工具可以并行执行。
- 有输入依赖的工具严格分阶段串行执行。
- 工具失败、模型误选工具和可选数据缺失不再把已成功的核心回答升级成用户可见的 `invalid_request`。
- Match scope 继续以请求开始时冻结的 `match_id`、`state_version`、`as_of` 为事实基线。
- 保持已有结构化数据优先、SSE 流式进度和最终回答降级语义。
- 对每一次工具选择、裁剪、执行、重试、降级和终止都有可脱敏的观测证据。
- 不引入额外路由大模型，不改变 API-Tennis、P2 数据能力边界，不添加 odds、prediction、market 或 trading 能力。

### 2.2 非目标

- 不把所有问题强行拆成大量工具调用。
- 不为历史数据增加新的供应商镜像或无限分页。
- 不允许模型绕过 scope 约束读取任意比赛。
- 不将模型生成的猜测当成 canonical 比赛事实。
- 不通过简单增大循环次数掩盖工具依赖、权限和终止条件问题。

## 3. 方案比较与决策

### 方案 A：最小修补

只做三处修改：global scope 隐藏 `get_match_intelligence`、发送 `parallel_tool_calls=true`、把工具轮数从 2 调大。

优点是改动小、上线快。缺点是工具依赖仍由模型隐式决定，非法工具仍可能从其他路径进入，部分失败仍可能中断整条流；它能修复当前案例，但不能形成稳定的多工具协议。

### 方案 B：作用域感知的混合编排器（采用）

增加轻量的工具能力注册表和阶段化路由：服务端先按 scope、用户意图和当前上下文裁剪工具；模型在小工具集内决定参数；执行器根据依赖关系将独立调用组成并行批次，将依赖调用放到下一阶段串行执行；非法调用转为内部重规划或可观测降级。

优点是能解决当前回归，同时保留模型对自然语言的理解能力；六个现有工具不需要额外路由模型，延迟、成本和失败面可控。缺点是需要明确工具契约、前后端部分失败语义和更多回归测试。

### 方案 C：额外路由模型 + 通用 DAG Agent

先调用 Qwen-Flash 或其他小模型生成工具 DAG，再由主模型执行和总结。

它适合工具数量很多、业务域高度异构的系统，但当前只有六个只读业务工具，会增加一次模型调用、延迟、费用和新的路由失败点。当前阶段不采用；未来工具数量显著增长时可重新评估。

## 4. 核心架构

### 4.1 组件边界

```text
ChatRequest
    ↓
ScopeResolver / SnapshotFreezer
    ↓
IntentRouter + ToolCapabilityRegistry
    ↓
PhasePlanner
    ↓
ToolBatchExecutor ──→ Canonical ToolOutcome
    ↓                         │
    └──────── model re-plan ←─┘
    ↓
FinalSynthesizer（tool_choice=none）
    ↓
SSE：data / progress / warning / text_delta / done
```

每个组件只承担一个责任：

- `ScopeResolver` 确认请求是 global 还是 match，并在 match 请求开始时冻结快照。
- `ToolCapabilityRegistry` 描述工具的作用域、阶段、依赖、并行安全性和可选性。
- `IntentRouter` 只做轻量、确定性的范围缩小，不引入第二个模型。
- `PhasePlanner` 控制工具可见集合、当前阶段、轮数和预算。
- `ToolBatchExecutor` 负责校验、去重、并发/串行执行和逐工具结果封装。
- `FinalSynthesizer` 只消费 canonical 事实，禁止继续调用工具。

### 4.2 工具能力注册表

每个工具登记以下元数据：

| 属性 | 语义 |
|---|---|
| `name` | 对外 function name |
| `allowed_scopes` | `global`、`match` 或两者 |
| `phases` | 可出现的阶段：`discovery`、`context`、`enrichment` |
| `requires` | `snapshot`、`resolved_match_id`、`player_identity` 等依赖 |
| `parallel_safe` | 是否可和同批其他调用并行 |
| `requiredness` | `core` 或 `optional` |
| `timeout_seconds` | 单工具预算 |
| `retry_policy` | 是否允许一次有限重试 |

第一版工具矩阵：

| 工具 | Global discovery | Match context | Enrichment | 依赖 | 并行 |
|---|---:|---:|---:|---|---:|
| `find_player_matches` | ✓ |  |  | 用户球员名 | 是 |
| `get_live_matches` | ✓ |  |  | 可选球员名 | 是 |
| `get_match` | ✓（需显式 match ID） |  |  | resolved match ID | 否/按阶段 |
| `get_match_intelligence` |  | ✓ |  | 冻结 snapshot | 是 |
| `get_player_results` | ✓（仅显式历史意图） |  | ✓（显式要求） | 球员身份 | 是 |
| `get_head_to_head` | ✓（仅显式交手意图） |  | ✓（显式要求） | 两位球员身份 | 是 |

`get_match_intelligence` 永远不会出现在 global 的工具目录中。`get_match` 在 global 目录中使用要求 `match_id` 的参数 schema；match scope 下仍由服务器注入当前比赛 ID，不信任模型提供的 ID。

### 4.3 阶段化工具目录

工具目录不是一次性把六个工具全部传给模型，而是由 `(scope, phase, intent, context)` 计算：

| 阶段 | Global scope | Match scope |
|---|---|---|
| `discovery` | `find_player_matches`、`get_live_matches`；明确历史意图时再加入对应历史工具 | 不使用 discovery，比赛已由页面确定 |
| `context` | 不可用 | `get_match_intelligence`，按问题允许的 topic 子集 |
| `enrichment` | 仅用户明确要求历史/H2H 时使用 | 仅用户明确要求球员背景、近期表现或交手时使用 |
| `synthesis` | 不传工具，`tool_choice=none` | 不传工具，`tool_choice=none` |

服务端在目录生成和实际执行两处都做 scope 校验，形成 defense-in-depth。目录裁剪减少模型误选；执行校验防止模型、测试替身或未来适配器绕过目录。

## 5. 编排状态机与调用协议

### 5.1 状态机

```text
RECEIVED
  → SCOPE_LOCKED
  → PLANNING
  → DISCOVERY_BATCH（global 可选）
  → CONTEXT_BATCH（match 可选）
  → ENRICHMENT_BATCH（可选）
  → SYNTHESIS
  → DONE

任意阶段的外部失败
  → PARTIAL_DEGRADED（已有核心事实）
  → SYNTHESIS

模型非法工具调用
  → REJECT_AND_REPLAN（最多一次）
  → 原阶段继续或 PARTIAL_DEGRADED
```

`REJECT_AND_REPLAN` 只处理模型选择错误，不把内部编排错误伪装成用户 422。用户请求本身为空、超长或 scope 缺少必需 `match_id` 时，仍使用现有的 `invalid_request` 语义。

### 5.2 模型调用

工具规划调用：

- `tool_choice="auto"`。
- 当前批次无依赖时发送 `parallel_tool_calls=true`。
- 当前阶段存在依赖时发送 `parallel_tool_calls=false`，由服务端完成一轮工具后再请求下一阶段。
- 每次调用只传当前阶段允许的工具，不把完整 catalog 放回模型。

最终生成调用：

- `tool_choice="none"`。
- 不再发送 `tools`，减少无意义的输入 token 和模型再次选工具的机会。
- 消息中包含原始用户问题、工具结果和不可变的 `answer_context`。

阿里云官方接口把 `parallel_tool_calls` 默认设置为关闭，并说明并行适用于无依赖任务、串行循环适用于有依赖任务；本设计直接遵循这一边界，而不是对所有工具无条件并行。

### 5.3 批次执行

同一 assistant response 返回的多个合法、无依赖 tool call 构成一个批次：

1. 按 function name、规范化参数和当前 snapshot 生成幂等签名。
2. 同一批重复签名只执行一次，重复调用复用同一个结果。
3. 使用 `asyncio.gather` 并行执行 `parallel_safe=true` 的调用。
4. 单个调用有独立 timeout，不因一个可选调用超时取消其他调用。
5. 结果按模型返回的 tool-call 顺序写回 `role=tool` 消息，保证每个 `tool_call_id` 一一对应。
6. 将核心/可选结果分别累计，决定进入下一阶段还是直接 synthesis。

有依赖的调用不在同一批次内猜测执行。例如全局请求先找到比赛，再使用返回的内部 match ID 获取详情；第一批只做 discovery，第二批才允许 `get_match`。详情页已有冻结 snapshot 时，statistics、points、momentum 和明确请求的球员背景可以在同一批次并行。

### 5.4 边界预算

第一版固定且可测试的边界：

- 最多 3 个含工具的模型规划轮次。
- 每个请求最多 8 个唯一工具调用。
- 每个并行批次最多 4 个调用。
- 每个工具独立 timeout，默认 8 秒；总请求继续受现有 45 秒上限约束。
- 非法工具最多自动重规划 1 次。
- 同一签名重复调用不消耗新的工具预算。

达到边界时，如果已有核心数据，进入 `PARTIAL_DEGRADED` 并生成回答；没有核心数据时返回可重试的 typed failure。禁止用无限轮次换取“看起来更聪明”的回答。

## 6. 结果、错误与降级语义

### 6.1 统一 ToolOutcome

每次工具执行都转成内部统一结果，再映射为模型可读的 `role=tool` 内容和前端可见事件：

```text
ToolOutcome {
  tool_name
  call_id
  status: success | partial | unavailable | failed | rejected
  requiredness: core | optional
  facts: canonical payload
  answer_context: match_id/state_version/as_of（如适用）
  reason: stable reason code（不含 key、URL、原始供应商 payload）
  retryable: boolean
  duration_ms
}
```

现有 `StructuredToolResult` 继续作为 canonical data 对外形状；`ToolOutcome` 是编排层 envelope，不向用户暴露内部供应商字段。

### 6.2 错误分类

| 错误 | 编排行为 | 用户表现 |
|---|---|---|
| 用户请求非法 | 立即 `invalid_request` | 明确修正输入 |
| 模型参数 schema 错误 | 不执行；返回 tool-level invalid；重规划一次 | 不显示内部 422 |
| 模型调用了非法 scope 工具 | 不执行；记录 rejected；重规划一次 | 有核心数据则继续回答 |
| 核心数据 provider 失败 | 保留已知数据；若无核心事实则终止 | 明确数据服务不可用/可重试 |
| 可选历史/H2H 失败 | 保留核心事实，生成 warning outcome | 回答中说明该资料暂未提供 |
| 最终 LLM 失败且有数据 | 使用结构化事实 fallback | 比赛卡片和简短事实仍可见 |
| 最终 LLM 失败且无数据 | typed terminal error | 明确查询未完成 |

`invalid_request` 只表示用户请求或服务器契约错误，不再表示“模型自行选了一个当前 scope 不允许的工具”。

### 6.3 SSE 事件

保留现有 `status`、`data`、`text_delta`、`done`、`error` 事件类型，并向 `status` 增加可选进度字段：

```json
{
  "stage": "fetching_data",
  "phase": "context",
  "completed": 2,
  "total": 3,
  "tool": "get_match_intelligence"
}
```

新增可选 `warning` 事件用于部分失败和被拒绝的可选调用。旧客户端忽略该事件仍能显示核心数据；新客户端把它放入 `warnings`，不设置 terminal `error`。

事件顺序约束：

```text
status(resolving)
status(planning)
status(fetching_data) × N
data × M
warning × K（可选）
status(generating)
text_delta × L
done
```

只要核心事实已经发出，单个 optional tool 的 failure/rejected 不得发送 terminal `error`。全局“tiafoe 的比赛如何了”应至少得到 `data → generating/text_delta → done`，不再出现 `data → invalid_request`。

## 7. 前端状态语义

当前前端把任何 `chat.error` 都渲染成“查询未完成”，即使 `chat.data` 已经成功。这会放大后端的编排错误。T39 的前端调整：

- `error` 仅表示请求无法完成或没有可用核心事实的 terminal failure。
- `warnings` 保存 optional tool 的 `unavailable`、`failed`、`rejected` 原因。
- `data` 已存在时，继续展示结构化卡片和正文；warning 以轻量可见提示呈现。
- `status` 的批次进度映射到现有“解析问题/取数/组织回答”进度文案，必要时显示 `2/3`。
- 失败、取消、重新提问时清理 `warnings`、progress 和旧请求控制器；不把上一条问题的 warning 带入新问题。

这样可以区分：

```text
请求错误       → 查询未完成
部分资料缺失   → 回答完成 + 资料暂不可用
模型最终失败   → 结构化事实 + fallback 说明
```

## 8. 关键业务流程

### 8.1 当前回归：全局实时查询

用户输入“tiafoe 的比赛如何了”：

```text
global / discovery
  → 仅向模型提供 find_player_matches、get_live_matches
  → 找到当前比赛并发 data
  → 不允许 get_match_intelligence
  → synthesis(tool_choice=none)
  → done
```

### 8.2 详情页综合分析

用户在比赛详情页询问“根据当前比分、每盘统计和逐分走势分析趋势”：

```text
match / frozen snapshot
  → context batch（并行）
      statistics
      points
      momentum
  → synthesis(tool_choice=none)
```

### 8.3 详情页需要球员背景

用户明确要求近期表现和 H2H：

```text
match / frozen snapshot
  → context batch（并行）
      statistics / points / momentum（按问题需要）
  → enrichment batch（并行）
      player_1 recent
      player_2 recent
      head_to_head
  → synthesis(tool_choice=none)
```

如果某一项历史能力返回 `not_found` 或 `unsupported`，它只能形成 warning，不得覆盖已经拿到的当前比赛事实。

## 9. 可观测性与安全

每个请求使用现有 request ID，并记录以下脱敏字段：

- `scope`、阶段、规划轮次、允许工具集合的 hash；
- 模型返回的 tool name、参数 schema 校验结果、scope reject 原因；
- call 数量、并行批次大小、每个工具耗时和稳定结果码；
- 核心/可选结果数量、重规划次数、最终状态和 fallback 原因；
- match scope 的 `state_version` 与 `as_of`，不记录原始 provider payload。

禁止记录 API key、完整 Authorization、供应商外部 ID、供应商 URL、原始响应或完整用户 prompt。日志只用于解释“在哪个边界失败”，不能成为新的敏感数据副本。

新增指标建议：

- `chat_tool_calls_total{tool,scope,phase,status}`
- `chat_tool_scope_rejected_total{tool,scope}`
- `chat_parallel_batch_duration_ms`
- `chat_replan_total{reason}`
- `chat_partial_completion_total{reason}`
- `chat_terminal_error_total{code}`

## 10. 测试与验收门

### 10.1 Backend 单元与契约测试

- global catalog 不包含 `get_match_intelligence`。
- match 当前分析不包含未请求的 history/H2H 工具。
- global `get_match` schema 要求 match ID；match scope 仍由服务器注入 ID。
- 一个 `ModelTurn` 返回多个独立 tool call 时全部执行。
- 并行批次用 barrier/时间断言验证确实并行，结果顺序仍稳定。
- 有依赖调用分批串行，下一批只能看到上一批结果。
- 非法 scope tool 不实际执行，最多触发一次 replan。
- 参数错误变成 tool-level outcome，不直接发用户 terminal `invalid_request`。
- optional provider failure 保留核心 data 并发 warning。
- core failure、LLM final failure、超预算、重复调用分别有明确终止语义。
- 所有 `role=tool` 消息和 `tool_call_id` 一一对应。
- OpenAI-compatible request 明确携带 `parallel_tool_calls`，final request 使用 `tool_choice=none` 且不传工具。

### 10.2 Backend 回归与真实门

- 真实问题“tiafoe 的比赛如何了”重复运行至少 5 次：每次 `data → text/done`，无 `invalid_request`。
- 详情页复杂分析至少覆盖 statistics + points + momentum 并行批次。
- 详情页可选球员资料缺失时仍返回当前比赛分析。
- 真实 Qwen tool loop 的工具名、scope、轮数和 canonical 事实一致。
- 真实 API-Tennis 数据失败/429 时不泄漏凭据并保留结构化降级。

### 10.3 Frontend 与真实浏览器

- Home 输入实时球员查询，看到 progress、结构化卡片和最终回答，不出现“卡片成功后查询失败”。
- Match 页面复杂问题看到多个取数阶段，最终回答的 `answer_context` 保持同一 snapshot。
- partial warning 不渲染成 terminal error。
- 取消、重试和连续提问不串用旧状态。
- 双视口 Playwright 功能与视觉回归通过。
- 使用真实浏览器鼠标完成 Home → 查询 → 结果卡片 → Match Page → 复杂分析，检查浏览器 error/warn 和 backend SSE 原始事件。

### 10.4 安全与范围门

- 全局模型永远无法看到或执行 match-only tool。
- 日志、SSE、模型上下文和公共响应不包含 API key、Authorization、供应商原始字段或供应商外部 ID。
- 不新增预测、赔率、市场或交易能力。
- 根目录 `.env` 仍是唯一人工配置入口。
- 用户已有未跟踪文件保持原样。

## 11. 分阶段实现顺序

实现批准后按以下顺序执行，每一步先写失败测试再修改生产代码：

1. 建立能力注册表和 scope/phase catalog；补 global 非法工具回归，先修复当前 `tiafoe` 案例。
2. 在 OpenAI-compatible adapter 增加 `parallel_tool_calls` 参数；实现批次校验、去重、并行执行和依赖阶段。
3. 将非法工具、参数错误和 optional failure 转为 tool outcome/replan/warning，保持核心事实优先。
4. 调整 final synthesis 的 `tool_choice=none`、SSE progress/warning 和前端 `warnings` 状态。
5. 补齐单元、契约、集成、双视口 E2E 和真实 Qwen/API-Tennis gates。
6. 用真实浏览器复跑全局查询和详情页复杂分析，核对日志、原始 SSE、浏览器 console 与最终视觉。

不新增额外路由模型、不做数据库迁移；如果实现过程中发现现有 `ChatEvent` 或工具 Schema 无法在兼容范围内扩展，必须先回到本 spec 更新接口决策。

## 12. 完成定义

T39 只有在以下条件全部满足时才可标记完成：

- 当前真实回归不再出现结构化数据成功后 `invalid_request`。
- Global、Match scope 的工具可见性和执行防线均有测试。
- 无依赖工具并行、有依赖工具串行，且有明确预算与去重。
- optional failure、非法模型调用、最终 LLM failure 均按降级语义工作。
- SSE 和前端能区分 progress、warning、terminal error。
- backend/frontend 全量测试、typecheck、build、隔离 Playwright 和真实业务流程均有实际通过证据。
- 真实 Qwen 请求遵循阿里云官方 Function Calling / OpenAI 兼容参数语义。
- `CURRENT.md`、`ROADMAP.md` 与代码、测试、Git HEAD 一致，并提交推送所有任务内成果；任务外未跟踪文件未被提交。
