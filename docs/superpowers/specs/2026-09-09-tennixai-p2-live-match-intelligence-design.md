# TennixAI P2 Live Match Intelligence 设计规格

**状态：** 已批准，等待按任务路线实施
**日期：** 2026-09-09
**交付目标：** 本地完整运行、私人测试、最多分享给少量好友
**前置阶段：** P1 已完成
**实施计划：** [P2 实施计划](../plans/2026-09-09-tennixai-p2-implementation.md)

## 1. 目标

P2 将 TennixAI 从“能查询比赛信息”推进到“能解释一场正在发生的比赛”。用户打开 Match Page 后，不刷新浏览器也能看到比分、发球方、逐分、技术统计和近期走势持续更新，并能围绕当前比赛提出结构化问题。

P2 的最小成功状态是：

```text
API-Tennis REST + WebSocket
          ↓
Provider adapters
          ↓
Canonical live reducer
          ↓
PostgreSQL + Redis
          ↓
FastAPI snapshot/SSE + business tools
          ↓
Next.js Home / Match / Chat
```

这仍然是 Tennis Data Platform，不是 API-Tennis Chatbot。数据源、LLM 和 UI 可以替换，canonical domain、service contract、provider interface 和状态语义必须保持稳定。

## 2. 已冻结的产品边界

### 2.1 P2 包含

- Home 使用 API-Tennis 统一提供 live、upcoming、球员、赛事和轻量历史数据。
- Home 默认优先展示高级别比赛，并提供赛事级别、性别、单双打叠加筛选。
- Match Page 通过 WebSocket 获得 live score、server、PBP 和 statistics 更新。
- 完整 PBP 按盘、局、分组织，支持关键分标记和历史折叠。
- 技术统计尽可能覆盖供应商语义明确的字段，缺失值诚实降级。
- Recent Control Index 用可解释的确定性算法描述近期比赛控制走势。
- Match Chat 使用当前 `match_id` 和带版本的 compact intelligence fact packet 回答上下文问题。
- PostgreSQL 保存身份映射、canonical live observations、PBP、统计变化、控制指数和数据质量。
- Redis 负责观看需求租约、当前热状态和进程间事件分发。
- API-Tennis 的近期结果与 H2H 按需查询，不复制完整供应商历史库。
- 原始供应商 payload 保留 14 天，用于诊断、重放和纠错审计。
- 使用确定性 replay 做主要自动化测试，真实 API 与真实 LLM 做 opt-in 冒烟。

### 2.2 P2 不包含

- Polymarket、赔率、隐含概率、预测概率、edge、confidence 或交易建议。
- API-Tennis 的 `get_live_odds`、prematch odds、AI news 或 MCP 能力。
- 自动下单、paper trading 或任何交易执行。
- 用户账户、认证、权限系统、云部署或正式公网服务。
- 全量赛季历史回填、完整历史镜像、数据导出平台或赛季分析仓库。
- Redis Streams、Kafka、Kubernetes、微服务、LangGraph、Vector DB、Elasticsearch 或复杂 event sourcing。
- 将 Recent Control Index 描述成心理状态、胜率预测或确定性比赛结论。
- 为供应商未提供且无法从 PBP 严格证明的数据造值。

## 3. 数据供应商结论

### 3.1 API-Tennis 是 P2 主供应商

P2 默认 REST provider 和 live feed 都切到 API-Tennis。P1 的 `LiveTennisProvider` 保留为备用 adapter，不再是默认业务数据源。

API-Tennis 官方 REST 文档当前列出：

- `get_events`
- `get_tournaments`
- `get_fixtures`
- `get_livescore`
- `get_H2H`
- `get_players`
- `get_standings`

其中 `get_fixtures` 和 `get_livescore` 会在比赛对象内联返回 `scores`、`pointbypoint` 和 `statistics`；P2 不为同一比赛额外发起三个供应商请求。参考 [API-Tennis REST documentation](https://api-tennis.com/documentation)。

API-Tennis 官方 WebSocket 文档说明 `wss://wss.api-tennis.com/live` 会在 live score 或 point-by-point 出现事件时推送，并支持按 `match_key` 过滤。参考 [API-Tennis WebSocket documentation](https://api-tennis.com/documentation_websocket)。因此 P2 实时主路径必须使用 WebSocket，不能把固定轮询当作正常更新机制。

### 3.2 已完成的 Trial 能力探测

2026-09-09 使用用户提供但未入库的 Trial key 验证：

- `get_livescore` 可返回比分、发球方、PBP 和 statistics。
- `get_fixtures` 可按日期查询已结束比赛；抽样年份包括 2019、2022、2024、2025、2026。
- 早期历史样本可能只有比分，PBP/statistics 的历史覆盖并不稳定；2024 以后抽样更丰富。
- `get_H2H` 可返回双方交手及各自近期比赛。
- `get_players` 可返回跨赛季聚合记录。
- WebSocket 认证成功，并收到真实 live push。
- `get_live_odds` 可访问，但能力存在不代表产品应使用；P2 明确禁止接入。

供应商没有公开承诺最早历史年份、逐分历史保留期限或任意日期都具备统计。TennixAI 必须把“没有返回”表达成 unavailable/partial，不能推断为零或不存在。

### 3.3 商业计划假设

P2 以 API-Tennis Business 能力为目标。实现不得把某个价格、每日配额或并发上限硬编码成领域规则；实际 entitlement 由环境配置和 live capability smoke test 验证。若套餐约束变化，只调整并发上限、降级策略或商业选择，不改 canonical model。

任何 API key 只允许存在于被 Git 忽略的本地环境文件。日志、异常、raw payload、fixture、文档和 SSE 都不得包含 key 或带 key 的完整 URL。

## 4. 运行拓扑与职责

```text
Browser
  ├── REST / chat ──────────────┐
  └── match SSE ────────────────┤
                                ↓
Next.js Route Handlers → FastAPI
                           ├── Home / history / H2H REST
                           ├── Match snapshot
                           ├── Match SSE clients
                           ├── TennisService
                           └── Chat / business tools
                                ↕
                       Redis demand / hot state / pubsub
                                ↕
                         Realtime Worker
                           ├── REST snapshot/reconcile
                           ├── API-Tennis WebSocket
                           ├── canonical reducer
                           ├── statistics + control index
                           └── PostgreSQL persistence
                                ↕
                            PostgreSQL
```

P2 采用“双进程、单仓库、共享 domain package”：

- FastAPI 负责请求/响应、Home、history、H2H、Match snapshot、SSE 客户端、Chat 和需求租约。
- Realtime Worker 负责上游订阅、重连、REST 校准、事件归并、版本推进、持久化和发布。
- 两个进程都复用 `app.domain`、provider contracts、repository contracts 和 reducer 类型。
- Worker 是单独的 host process，不嵌入 FastAPI lifespan，避免开发热重载或 Web 进程重启破坏订阅。
- 本地基础设施只有 PostgreSQL 与 Redis 使用 Docker Compose；FastAPI、Worker 和 Next.js 仍由 `uv`/`pnpm` 在 host 启动。

## 5. Canonical domain

### 5.1 比赛分类

在 P1 `Tournament`/`Match` 基础上新增稳定枚举：

```text
CircuitTier: atp | wta | challenger | itf | other
Gender: men | women | mixed | unknown
Discipline: singles | doubles | team | unknown
```

API-Tennis `event_type_type` 只在 adapter 内解析。可靠的大类映射为：

```text
ATP / WTA → 顶级巡回赛
Challenger → 挑战赛
ITF → ITF
未识别 → other / unknown
```

P2 不维护 Grand Slam、Masters 1000、500、250 等精细赛事目录。分类规则未确认时宁可 `other`，不能依靠赛事名称猜测精确级别。

### 5.2 实时状态

扩展 `LiveMatchState`：

```text
score
server_player_id
state_version
connection_status
last_event_at
as_of
```

`connection_status` 使用：

```text
connecting | live | reconnecting | stale | ended | unavailable
```

`state_version` 是每场比赛单调递增的整数。只有 canonical 状态实际改变时才递增；供应商重复推送的相同全量 snapshot 不产生新版本。

### 5.3 PointEvent

`PointEvent` 至少包含：

```text
id
match_id
sequence
set_number
game_number
point_number
server_player_id
winner_player_id?       # 只有能够确定时才填写
score_before?
score_after
is_break_point
is_set_point
is_match_point
observed_at
provider
source_fingerprint
revision
quality
```

逐分顺序由 reducer 统一生成。若供应商只给分后比分而不能可靠确定胜者，`winner_player_id` 保持空，并在 `quality` 中说明，Recent Control Index 跳过该分。

### 5.4 MatchStatistic

P2 canonical catalog 接受以下 22 个语义明确的名称：

```text
aces
double_faults
first_serve_percentage
first_serve_points_won
second_serve_points_won
service_points_won
service_games_won
break_points_saved
break_points_converted
return_points_won
first_return_points_won
second_return_points_won
return_games_won
winners
unforced_errors
net_points_won
total_points_won
total_games_won
match_points_saved
average_first_serve_speed
average_second_serve_speed
distance_covered
```

每项携带 `period`、两个球员的值、单位、来源、`as_of` 和 availability。原始 `stat_name` 未识别时记录在 provider diagnostic/raw payload，不进入公共 DTO。

API-Tennis 的 `Last 10 balls` 没有足够清晰的官方语义，不能直接映射；TennixAI 从最近 10 个可确定 `PointEvent` 自己计算“最近 10 分”。

PBP 衍生统计只允许来自可证明的逐分事实，并标记 `provenance=derived_pbp`。无法严格计算的一发率、ACE、双误或球速等保持 unavailable，不从比分猜测。

### 5.5 MomentumObservation 与 DataQuality

公开产品名使用“近期控制指数”，内部可保留 `MomentumObservation` 作为领域名。每条 observation 包含：

```text
match_id
point_sequence
state_version
algorithm_version
value                 # -100..100
leader_player_id?
is_provisional
as_of
input_summary
```

`DataQuality` 按 capability 表达 `available | partial | unavailable | stale`，并附 provider、原因和时间。缺失、零、过期和不支持必须可区分。

## 6. Provider interfaces

P2 将查询与流式能力分离：

```python
class TennisDataProvider(Protocol):
    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        raise NotImplementedError

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        raise NotImplementedError

    async def search_players(self, query: str) -> list[Player]:
        raise NotImplementedError

    async def get_player(self, player_id: str) -> Player:
        raise NotImplementedError

    async def get_match(self, match_id: str) -> Match:
        raise NotImplementedError

    async def get_match_snapshot(self, match_id: str) -> MatchSnapshot:
        raise NotImplementedError

    async def get_recent_results(self, player_id: str, *, limit: int) -> list[Match]:
        raise NotImplementedError

    async def get_head_to_head(
        self, first_player_id: str, second_player_id: str, *, limit: int
    ) -> HeadToHead:
        raise NotImplementedError

class TennisLiveFeedProvider(Protocol):
    def stream_match(self, external_match_id: str) -> AsyncIterator[ProviderLiveEnvelope]:
        raise NotImplementedError
```

`ApiTennisProvider` 负责 REST 参数、响应验证、错误翻译、timezone、event taxonomy 和 vendor-to-canonical 映射。`ApiTennisLiveFeedProvider` 负责 WebSocket 认证、按 match 过滤、消息验证和断线信号。两者都不能把供应商字段暴露给 service/UI。

`ProviderLiveEnvelope` 是 adapter 与 reducer 之间的私有 DTO，可以包含完整供应商 snapshot；它不进入 API response 或 Chat。

## 7. Identity 与 PostgreSQL

### 7.1 Identity

第三方 ID 不是主键。内部 ID 继续使用 `mat_`、`ply_`、`trn_` 前缀，并持久保存映射：

```text
matches / players / tournaments
          ↑
match_external_ids / player_external_ids / tournament_external_ids
          provider + external_id 唯一
```

旧 `MemoryIdentityRepository` 保留给纯单元测试；P2 运行时使用 PostgreSQL repository。P1 已产生但未持久化的 URL 不承诺迁移，P2 切换后新生成的 ID 必须跨进程重启稳定。

### 7.2 表职责

P2 最小表集合：

- `players`、`tournaments`、`matches`
- `player_external_ids`、`tournament_external_ids`、`match_external_ids`
- `match_state_snapshots`：每场当前 canonical state 与 `state_version`
- `point_events`：当前有效逐分序列
- `point_event_revisions`：供应商纠错前后的差异与时间
- `match_statistics`：每项当前值
- `statistic_observations`：仅状态改变时追加
- `momentum_observations`：与 point/state version 对齐的长期记录
- `raw_provider_events`：原始 payload、通道和观察时间，14 天清理

Chat 内容、浏览器状态、观看租约和完整 API 历史不进入 PostgreSQL。

### 7.3 数据保留

- Raw provider payload：14 天后清理。
- Canonical live state、PBP、统计变化、控制指数、identity/provenance：长期保留。
- On-demand history/H2H response：只走短 TTL cache，不做历史镜像。
- 清理任务由 Realtime Worker 周期执行，必须按显式表和时间条件删除，不能使用宽泛文件或数据库清空操作。

## 8. Redis 职责

Redis 只承担短生命周期协调：

- 每个 Match SSE 客户端的观看需求租约。
- 当前被需求的 match 索引。
- 每场比赛最近的热 snapshot。
- `match:{id}` 实时 pub/sub。
- worker reconnect/backoff 与短期去重状态。

Redis 不保存长期 PBP、统计历史、控制指数历史或 Chat。Redis 丢失后系统通过 PostgreSQL 和 REST reconcile 恢复，不把 Redis 当作事实唯一来源。

## 9. 按需订阅生命周期

P2 不订阅全天所有比赛，只订阅正在被观看的比赛：

1. Match Page 取得初始 snapshot。
2. 浏览器打开 Match SSE。
3. FastAPI 为该 SSE connection 创建 viewer lease，并每 20 秒续租。
4. Realtime Worker 发现第一位 viewer 后，通过 REST 获取初始/校准 snapshot，再按 external match ID 打开 WebSocket。
5. 多个浏览器观看同一比赛时共享一个上游订阅。
6. 标签页隐藏满 60 秒后，前端关闭 SSE；回到前台时重新 snapshot + SSE。
7. 最后一位 viewer 离开后，worker 保留上游订阅 60 秒 grace，避免标签切换导致连接抖动。
8. 比赛终态后立即持久化终态、发布 `match_ended` 并关闭订阅。

进程异常退出不能永久占用订阅：viewer lease 有 TTL；worker 重启后从 Redis demand index 和 PostgreSQL identity 恢复。

## 10. Reducer 与纠错

API-Tennis WebSocket 消息按官方示例可能携带整场 live object，而不是单一 point delta。Reducer 负责：

- 把 full supplier snapshot 转成 canonical candidate state。
- 比较 fingerprint；无变化则忽略。
- 追加真正新增的 point。
- 识别已存在 point 的值变化，写入 revision，而不是重复插入。
- 从最早受影响 point 重算依赖它的衍生统计和控制指数。
- 以数据库事务写入 state、points、statistics、momentum 和 raw payload。
- 提交成功后更新 Redis hot snapshot 并发布增量事件。

数据库写入失败时不能先向客户端发布一个无法恢复的版本。发布失败时 canonical 数据仍已在 PostgreSQL，客户端通过版本缺口重取 snapshot。

## 11. REST 与 SSE 合约

现有 Next.js Route Handler 代理策略保持不变；浏览器仍只访问同源 `/api/*`。

主要 FastAPI 路由：

```text
GET /api/v1/matches
GET /api/v1/matches/{match_id}
GET /api/v1/matches/{match_id}/stream
GET /api/v1/players/search
GET /api/v1/players/{player_id}/results
GET /api/v1/head-to-head
POST /api/v1/chat/stream
```

`GET /matches/{id}` 返回完整 `MatchSnapshot`：match、live state、PBP、statistics、control observations、quality、`state_version`、`as_of`。

Match Page 协议：

```text
REST full snapshot
      ↓
SSE versioned deltas
      ↓
version gap / reconnect / stale
      ↓
REST full snapshot reconcile
```

SSE transport 事件类型：

```text
ready
match_delta
match_ended
heartbeat
error
```

每个 `state_version` 只发布一条原子 `match_delta`，内部 `changes` 是以下类型化联合：

```text
score_updated
point_appended
point_corrected
statistics_updated
momentum_updated
quality_updated
connection_updated
```

除 heartbeat 外，每个状态事件携带 `match_id`、`state_version` 和 `as_of`。SSE `id` 等于 state version。客户端忽略小于等于本地版本的重复 delta，只接受恰好 `local + 1` 的 delta；发现跳号、修正无法局部应用或重新连接时重取 snapshot。这样同一版本的比分、逐分和统计变化不会因分别去重而丢失。

## 12. WebSocket、REST fallback 与连接体验

WebSocket 是 live 正常路径。REST 仅用于：

- 初始 snapshot。
- WebSocket 重连后的状态校准。
- WebSocket 确认不可用期间、且仍有 viewer 时的受限 fallback。

REST fallback 必须遵守供应商配额和配置的最小间隔；WebSocket 恢复后立即停止。它不是常态定时刷新。

连接异常时：

- 页面保留最后一次可信状态。
- 显示 `reconnecting` 或 `stale` 与最后更新时间。
- 不清空比分，不产生虚构 point。
- 恢复后先 REST reconcile，再继续增量。
- 比赛结束或上游长期不可用时明确展示终态/不可用状态。

## 13. Home 分类、排序与筛选

默认选择：

```text
Circuit: ATP + WTA
Gender: 全部
Discipline: 单打
```

三个 facet 可以叠加：

- Circuit：ATP、WTA、Challenger、ITF、其他。
- Gender：男子、女子、混合。
- Discipline：单打、双打、团体。

交互规则：

- 每项显示当前结果集中的数量。
- 不兼容或数量为零的组合禁用。
- 提供一键恢复默认筛选。
- Featured、Live Now、Upcoming 共用同一筛选状态。
- 排序先按 `ATP/WTA → Challenger → ITF → other`，再按 live 优先、开赛时间和稳定 tie-breaker。
- Featured 从筛选后的最高优先级比赛选择，不能再取供应商数组第一项。
- 无结果时展示筛选空态，不自动偷偷放宽用户筛选。

视觉上沿用现有 v0 Home，不重新设计页面。Facet 使用紧凑的多选 chips/popover，在桌面和移动视口都必须保留层级与可读性。

## 14. Match Page 体验

现有 `/match?status=...` 继续作为原型视觉真源；生产 `/matches/[matchId]` 在保持布局的前提下替换 P2 占位区。

### 14.1 实时结构化面板

- Hero、比分、发球方、状态和 freshness 通过 snapshot/delta 更新。
- 技术统计按发球、接发、关键分、制胜/失误、体能等分组；只显示 available 数据。
- 未返回的数据展示“暂未提供”，不能显示 `0`。
- 每组和整卡显示 `as_of`/quality；partial 数据不阻断其他模块。

### 14.2 PBP

- 完整 PBP 按 `Set → Game → Point` 分组。
- 当前盘和最近一局默认展开，旧盘/旧局可折叠。
- 新 point 在用户停留底部时自动追加并保持可见。
- 用户正在查看旧 point 时不强制滚动，改用“有新分”提示。
- Break point、set point、match point 使用明确标记。
- 修正事件更新原 point，并提供非打扰式“数据已校准”提示。

### 14.3 Chat

- Match Chat 自动携带内部 `match_id`。
- 用户不需要重复比赛、球员或当前比分。
- 旧回答是生成时刻的不可变快照，显示 `as_of` 与 `state_version`。
- 结构化面板继续实时变化；若当前版本已经超过回答版本，回答显示“比赛已更新”。
- 不因每一分到来自动调用 LLM。

## 15. Recent Control Index v1

产品将它定义为近期可观察比赛控制走势，不是心理学测量，也不是获胜概率。

对球员 A，在第 `i` 个可确定 point 后：

```text
yᵢ = 1  if A wins the point, else 0
pᵢ = pre-point baseline probability that A wins, adjusted for the server
rᵢ = 2 × (yᵢ - pᵢ)
Mᵢ = (1 - α) × Mᵢ₋₁ + α × rᵢ
indexᵢ = clip(100 × Mᵢ / scale, -100, 100)
```

`pᵢ` 使用 `circuit × gender × discipline` 的发球赢分先验，并用该场比赛此前已完成的发球分做收缩更新。校准任务输出固定、版本化的 prior strength、`α` 和 `scale`；运行时不能用未来 point。

设计规则：

- 前端展示最近 20 个 observation，但 20 只是产品视窗，不是硬截断的科学常数。
- 不使用“普通分 1.0、破发 1.5、盘点 1.75、赛点 2.0”固定倍率。
- 关键分作为图表 annotation 和事实解释，与控制指数数值分开。
- 少于 6 个可确定 point 时标记 `provisional`。
- 不可确定 winner 的 point 不参与数值更新，但仍可显示在 PBP。
- point correction 从受影响位置重算，algorithm version 与 state version 一同保存。
- LLM 只能解释 service 计算出的 index 和 input summary，不能自行计算或改变数值。

研究依据与限制：

- [Klaassen & Magnus](https://www.janmagnus.nl/papers/JRM057.pdf) 表明发球、比分重要性和短期依赖需要区分，偏离 IID 的效果存在但不应夸大。
- [Gauriot & Page](https://academic.oup.com/ej/article/129/624/3107/5536246) 的准实验发现男女样本并不一致，反对通用固定连胜加成。
- [Varshney et al.](https://krvarshney.github.io/pubs/Varshney_kddlssa2014.pdf) 将 point importance 定义为具体比分状态下赢/输该分造成的赢盘概率差，说明关键分不能只按名称赋固定倍率。
- [AppliedMath 2025](https://www.mdpi.com/2673-9909/5/3/77) 提供 20-point + EWMA 的先例，但不是行业标准。
- [Transparent Point-level Momentum Framework](https://doi.org/10.71052/srb2024/PAZZ7038) 同样把 EWMA 作为描述工具，并明确参数不是通用常数、预测增益有限。

若未来引入 score-state leverage，应作为独立 Pressure/Leverage 指标另行设计；不能在 P2 v1 中静默变成预测模型。

## 16. Chat fact packet 与业务工具

LLM 不接收供应商 JSON、完整 PBP 或数据库行。`TennisService` 生成 compact intelligence fact packet：

```text
match identity + lifecycle
score + server
selected available statistics
recent determinable points
latest control observations + explanation inputs
key point facts
quality / missing capabilities
state_version + as_of
```

P2 保留 P1 三个工具并新增：

```text
get_match_intelligence(topic)
get_player_results(player_name, scope, limit)
get_head_to_head(first_player_name, second_player_name, limit)
```

`topic` 限定为 `overview | score | statistics | points | momentum`。Match scope 忽略模型提交的其他 match ID，只使用页面 context。

P1 的通用历史 guard 在 P2 改为能力路由：支持的“昨天/最近比赛/H2H”走 API-Tennis；任意大范围历史、无覆盖数据或超出 entitlement 的请求返回 typed unavailable/unsupported。结构化事实先于 prose 输出的原则保持不变。

## 17. 历史数据策略

API-Tennis 已提供 fixtures、H2H 和 player season aggregates，因此 TennixAI 不重复建设供应商历史仓库。

P2 只支持：

- 某球员昨天是否比赛及结果。
- 某球员最近有限场结果。
- 当前两位球员有限条 H2H。

服务层限制返回条数并使用短 TTL cache。没有公开 retention SLA 时，UI/Chat 必须说明“供应商当前未返回”，不能宣称不存在历史比赛。

PostgreSQL 中自然积累的 P2 live canonical observations 可以长期保留，但它们是 TennixAI 自己实际处理过的比赛审计，不是 API-Tennis 历史替代品。

## 18. 测试策略

### 18.1 默认确定性门

- Domain/model validation。
- API-Tennis DTO mapping 与未知字段隔离。
- Classification/filter/sort/facet counts。
- Reducer 去重、追加、纠错、版本和事务顺序。
- Redis lease、共享订阅和 grace period。
- SSE event/version/gap/reconcile。
- 22 项统计映射、partial/unavailable 和 PBP 可证明衍生值。
- Recent Control Index 对称性、发球校正、无未来数据、provisional 和 correction replay。
- Chat fact packet、时间戳、版本和缺失值回答。
- Next typed client、visibility lifecycle 和各卡片交互。

### 18.2 ReplayTennisProvider

测试使用脱敏后的真实 API-Tennis snapshot/PBP/statistics 作为 fixture，并可：

- 原速或加速重放。
- 注入重复 snapshot。
- 注入 point correction。
- 模拟版本缺口。
- 模拟 WebSocket 断线与 REST reconcile。
- 驱动 Playwright 验证无需刷新浏览器的 UI 更新。

Replay 只在 fake/test mode 使用，不进入真实 provider 路径。

### 18.3 Opt-in 真实门

- 真实 API-Tennis REST contract smoke。
- 真实 API-Tennis WebSocket push smoke。
- 真实 LLM tool choice/fact agreement。
- 真实 provider + worker + REST/SSE + browser smoke，在有 live match 时运行；没有 live match 时如实 skip。

真实测试不断言精确自然语言，不把 key 或供应商完整响应写进失败 artifact。

## 19. 本地运行与资源控制

仓库根目录 `.env` 是 FastAPI、Next.js、Realtime Worker、Playwright 和 opt-in 真实测试的唯一人工维护配置入口；模板为根目录 `.env.example`。子目录环境文件不再使用，所有凭据只存在于被 Git 忽略的根目录 `.env`。

本地运行最少包括：

```text
docker compose up PostgreSQL Redis
uv run alembic upgrade head
uv run uvicorn app.main:app
uv run python -m app.realtime.worker
pnpm dev
```

私人测试也必须有服务端限制：

- 最大同时上游 match subscriptions 可配置。
- 单 match 共享一个上游连接。
- 订阅容量满时返回 typed `capacity_limited`，不静默轮询所有比赛。
- REST fallback 有最小间隔和 backoff。
- History/H2H 限制请求范围与返回条数。
- API/LLM key 永不进入浏览器。

P2 完成只要求本地完整运行；购买服务器、域名、TLS、生产监控、备份恢复和公网滥用防护另立部署阶段。

## 20. P2 验收矩阵

### Home

- 默认 `ATP + WTA / 全部性别 / 单打`。
- 高级别比赛排在 Challenger、ITF 前面，Featured 不再被 M15 占据。
- Circuit、Gender、Discipline 可叠加，数量、禁用和重置行为正确。
- Live、Upcoming、Featured 使用同一筛选状态。

### Match realtime

- 打开 live Match Page 后，不刷新浏览器即可更新比分、发球方、PBP、统计和控制指数。
- 两个浏览器观看同一 match 时只有一个上游 WebSocket。
- 标签隐藏 60 秒释放需求，恢复后先 snapshot 再增量。
- 重复供应商 snapshot 不增加版本或重复 point。
- 断线保留最后可信状态，显示 reconnecting/stale；恢复后 REST reconcile。
- Worker/FastAPI 重启后能从 PostgreSQL/Redis 恢复，无重复 point。
- 比赛结束后发送终态并停止订阅。

### Intelligence

- PBP 按盘/局/分完整展示，关键分有标记，查看旧分时不强制滚动。
- 统计缺失不显示为零，partial 能独立呈现。
- 控制指数使用版本化校准参数、发球校正和 EWMA；关键分没有固定倍率。
- Chat 能回答谁在发球、当前比分、一发表现、ACE/双误/破发点、最近走势和关键事件。
- Chat 回答固定 `state_version/as_of`；状态更新后旧回答提示已过时。
- 昨天/最近结果和 H2H 按需来自 API-Tennis，不读取本地完整历史镜像。
- P2 API、UI、DB 中没有 live odds、预测或交易字段。

### Engineering

- Raw payload 14 天清理，canonical/derived observations 长期保留。
- 默认确定性 backend/frontend suite、类型检查、build、Replay Playwright 和视觉门通过。
- 真实 REST、WebSocket、LLM 和组合门按环境条件通过或如实 skip。
- P1 既有 current/upcoming/chat 行为和 prototype preview 不回归。
- 本地 runbook 可以从干净 checkout 启动五个组成部分并完成验收。

## 21. 实施阶段

P2 按以下阶段顺序执行；只有 `CURRENT.md` 指定的一个任务可以处于 `in_progress`：

| 阶段 | 交付 |
|---|---|
| P2.0 Design freeze | 本规格、实施计划、三份总控 |
| P2.1 Durable foundation | PostgreSQL、Redis、migration、persistent identity、P2 domain |
| P2.2 Unified API-Tennis REST | REST adapter、历史/H2H、Home 分类排序与 facet |
| P2.3 Realtime core | reducer、PBP/statistics persistence、leases、WebSocket worker、REST reconcile、snapshot/SSE |
| P2.4 Match intelligence | Match PBP/statistics UI、控制指数、fact packet 与 Chat |
| P2.5 Acceptance | deterministic replay、fault injection、真实门、视觉验收、runbook |

具体任务、文件、接口和测试步骤见 [P2 实施计划](../plans/2026-09-09-tennixai-p2-implementation.md)。

## 22. 设计冻结说明

以下不构成未解决产品决策：

- Recent Control Index 的具体 `α`、scale 和 serve priors 由计划内校准任务生成；算法结构与验证门已经冻结。
- API-Tennis 商业配额由运行环境配置；架构不依赖某个不稳定数字。
- 某项历史/statistics 是否有值由供应商实际 coverage 决定；availability 语义已经冻结。

任何执行者若需要改变 WebSocket 主路径、历史不镜像、14 天 raw retention、赔率隔离、默认 Home facet、双进程架构或控制指数非预测边界，必须先停止当前实现，更新本规格并取得用户批准。
