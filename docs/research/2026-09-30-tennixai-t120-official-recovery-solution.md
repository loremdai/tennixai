# T120 官方文档支持的启动恢复方案

日期：2026-09-30。起始提交 `4e7c6d9`；领取 `c8e0161`。用户要求先研究如何彻底避免同类启动失败，并结合官方文档。本文件是待实施方案，不表示产品修复已批准、完成或通过测试。

## 纠正与现场核验

Polymarket [List markets](https://docs.polymarket.com/api-reference/markets/list-markets) 明确 `/markets` 的 `closed` 参数默认 `false`。对 T119 的同一市场，使用数据库强制只读连接取 condition，发送三个有界公开 GET；仅输出 HTTP 状态、行数和状态布尔值，不输出凭据、供应商 ID 或原始 payload：

| 查询 | HTTP | 行数 | 结果 |
|---|---|---|---|
| 未传 closed | 200 | 0 | 默认过滤后不存在于列表 |
| closed=false | 200 | 0 | 不属于开放市场集合 |
| closed=true | 200 | 1 | active=true、closed=true、acceptingOrders=false、umaResolutionStatus=resolved |

该资源仍存在。准确故障链为：已取消比赛/关闭市场错误进入 TrackingDemand → Gamma 默认过滤关闭市场 → 适配器抛 not_found → 单市场错误中断全局恢复/tick → 后置同步不能执行 → 首次健康门超时。T119 的传播机制仍成立，但“资源删除/消失”推断应撤回。

## 推荐改动与官方依据

### 1. 明确市场查询用途与生命周期

开放目录显式使用 `closed=false`；读取已知市场元数据、规则或结算时，不能沿用仅开放市场的过滤。最小可行改动为已知 condition 先查 `closed=false`，未命中再查 `closed=true`，并验证唯一且 condition 精确匹配；两边都缺失才记录暂不可用，不凭空判定取消或结算。查询形状不合法应与合法空列表分别处理。

依据 [Market Details](https://docs.polymarket.com/market-data/market-details)：市场关闭后仍可能可查询；官方可交易判断为 `active && !closed && acceptingOrders`，`active` 单独不够。盘口恢复还需检查 `enableOrderBook` 与现有报价/规则安全门。关闭市场不请求实时可执行盘口，历史数据继续保留。

`backend/app/markets/polymarket.py:get_resolution()` 当前也调用 `_gamma_market_by_condition()`，遇到 not_found 返回 None。因此只修 TrackingDemand 会遗留关闭市场结算查询问题。应将盘口需求与未结持仓结算需求分开；结算只接受供应商最终结果及完整有效 payout，不能仅凭 closed、比赛 winner 或超时推断。依据 [Resolution](https://docs.polymarket.com/concepts/resolution)：结算存在提议、争议与最终确认流程，也存在 50/50 结果。当前零未结持仓，此项为代码确认的潜在风险，不是已发生的账本损害。

### 2. 恢复前刷新并核对需求，运行中处理终态

对无未结持仓的比赛，以现有 canonical 状态排除 cancelled/finished 等终态，再应用追踪时间窗；检查市场当前状态与观测 freshness。历史链接保留为查询关系，不把 active link 等同当前盘口订阅需求。旧 live 超出有效观测窗口时输出 stale/unknown 并做有界校准，不自行生成赛果；延期/暂停按现有产品规则单独处理。

[API-Tennis REST](https://api-tennis.com/documentation) 说明 `get_livescore` 只返回当前进行中的比赛，`get_fixtures` 可按日期和 match_key 查询。因此恢复中未出现在 livescore 的旧 live 记录需通过 fixtures 核对状态，不能直接等同比赛结束。其 [WebSocket 文档](https://api-tennis.com/documentation_websocket) 说明消息包含收到更新的比赛；文档没有保证重连自动重放全部漏失消息。本项目的 REST 恢复/校准是设计选择，不应声称供应商保证无缺口。

[Polymarket Real-Time Data](https://docs.polymarket.com/market-data/realtime-data) 支持 `custom_feature_enabled=true` 接收 `market_resolved`，支持 `operation=unsubscribe` 动态移除 token，并要求每 10 秒发送文本 PING。实施时核对既有适配器覆盖，补缺口即可，不新增 SDK 或第二条订阅连接。WS 终态事件用于触发刷新/退订，重启仍需 REST 校准以补离线期间的变化。

### 3. 单市场失败隔离，同步与结算继续推进

在每个市场 baseline/订阅边界处理已知供应商错误与超时，记录内部 market ID、错误类别及下次重试时间；临时故障采用有上限的退避，已关闭市场退出盘口需求。未受影响的订阅、目录/排名 jobs、已有结算 jobs 和健康持久化继续执行。不能在大循环外吞掉所有异常后标全局健康，也不能让目录校准以盘口恢复全部成功为前置条件。

使用已有 asyncio 与调度器即可；[Python 3.12 asyncio](https://docs.python.org/3.12/library/asyncio-task.html#timeouts) 提供 `asyncio.timeout()` 限制等待并把超时转为可处理的 TimeoutError。不要吞掉 CancelledError；若采用 TaskGroup，必须先在业务边界隔离预期错误，否则其失败传播语义会取消兄弟任务。具体退避/总时限需结合现有配置确定，不在本次研究中任意设值。

### 4. 区分本地可运行、数据源可用与允许模拟动作

本地依赖 DB/Redis、schema 与租约失败仍须阻止启动；上游某个市场暂不可用应记录 degraded，API/UI 可提供历史只读数据与真实 freshness。新的 paper 动作继续服从既有规则、实时性与 gap 安全门，不能以“允许启动”替代数据有效性。合法零订阅与恢复失败要有不同状态。

[Docker Compose 启动顺序](https://docs.docker.com/compose/how-tos/startup-order/) 明确 running 不代表 ready，已有依赖须按 healthcheck 判定；[Kubernetes 探针文档](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/) 区分 liveness、readiness 和 startup，依赖暂不可用不应一律杀掉进程。这里借鉴健康语义，不引入 Kubernetes；是否允许降级启动是待批准的本项目行为设计，不能直接绕过现有 launcher 首次健康门。

### 5. 初始化事实以持久库为准

[Python tempfile](https://docs.python.org/3.12/library/tempfile.html#tempfile.gettempdir) 将 gettempdir 定义为临时文件目录，并按环境/平台选择路径。它不是本项目初始化事实的可靠权威。建议持久记录初始化版本，以实际 DB schema 与所需初始化数据核验；临时 PID/log/状态文件丢失时只重建进程状态。数据库/schema 不兼容时显式提示所需 init/migration；日常 up 不因临时标记丢失而重新执行目录补名/LLM。

此项是本项目设计建议。没有证据确认 T118 的临时标记由哪个具体清理机制删除，不把 Python 文档解读为“每次重启必定清空”。

## 实施顺序与验收门（均未执行）

先实施查询语义、需求过滤、单市场隔离与调度推进，再验证结算；最后独立评审健康门和初始化持久化行为。最小修复复用现有 provider、worker、调度器、DB 与 health registry，无需新基础设施。

1. 取消比赛进入两小时窗口、市场 closed 且 link active：无未结持仓时不恢复其盘口，其他市场和目录 jobs 正常推进。
2. 默认 Gamma 返回空列表而 closed=true 返回已结算市场：元数据和最终结算可读取，不把关闭解释为删除；开放市场查询/盘口行为保持正确。
3. 单市场真正缺失、超时、429/5xx、非法响应：明确 degraded 与有界重试；其他市场、同步/结算/健康持久化不被饿死；不伪造健康或执行新动作。
4. 旧 live 未出现在 livescore、fixtures 有最终状态或校准失败：分别接受权威终态、保持 stale/unknown，不按时间猜赛果。
5. 有未结持仓的关闭/取消市场：盘口退订后仍能读取最终 resolution，含 disputed/尚未最终确认与 50/50，账本幂等且不产生重复结算。
6. WS 收到市场终态、断线/重连、离线期间市场关闭：订阅集合正确校准且保持单一所有者，gap 期间新动作仍被拦截。
7. 临时目录丢失、正常 down/up 与模拟重启：已初始化库直接恢复、不额外调用 LLM；DB/schema 真不兼容仍安全拒绝；历史市场与 Paper 数据完整保留。
8. 完成单元/集成证明后，执行受支持 up/status 与 API/首页真实运行门；没有执行的测试不得称通过。

本次完成官方文档核验和上述三个真实只读 GET。未修改产品代码/配置/数据库数据，未启停应用或调用 LLM，未执行实现测试或浏览器门。T118 仍 blocked。
