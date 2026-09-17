# TennixAI P4.0 本地真实运行设计

> 状态：设计冻结，尚未实施。
> 关联任务：[T72](../../../ROADMAP.md)
> 产品边界：[PROJECT.md](../../../PROJECT.md)
> 当前交接：[CURRENT.md](../../../CURRENT.md)

## 1. 一句话目标

把已经完成的 P1–P3 能力收成一套**本地、真实、可观察、只做 paper trading**的日常运行方式：首次执行一次 `init`，平时只运行 `up`。

这里的“真实”指：

- 网球赛程、比分、发球方、PBP 和技术统计来自真实 API-Tennis；
- 市场价格和订单簿来自公开只读 Polymarket；
- 页面、Chat 和 P3 决策都消费同一份 canonical 数据；
- 没有合适的真实数据时诚实显示空态、延迟或 `NO BET`，不以 fixture、preview 或推测填充；
- 永远不提交真实订单，不增加钱包、私钥、签名或交易凭据。

它不是整个 P4 的优化路线，也不是云部署或自动交易计划。它只是 P4 的第一个小阶段：让当前产品作为一个完整本地应用可靠跑起来。

## 2. 为什么现在需要这一层

P1–P3 已分别验证过真实 provider、WebSocket、市场读取、paper ledger、前端和浏览器流程，但日常运行仍是分散的：需要分别启动基础设施、后端和前端；P3 的 `MarketWorker`/`DecisionWorker` 已有组件和 replay 验证，却没有被长期运行的应用生命周期统一启动。

当前 `create_app()` 在 API 进程的 lifespan 中启动 P2 `RealtimeWorker`，而 P3 只完成装配、不启动市场发现和后台编排。这样适合测试和阶段交付，但不适合长期本地使用：容易重复持有上游 WebSocket，或者把旧测试数据库误当成真实运行数据。

本设计要解决的不是“再增加功能”，而是以下四件事：

1. 一条命令启动完整本地栈；
2. 每条上游实时流只有一个明确拥有者；
3. 真实运行数据与测试/回放数据物理隔离；
4. 用户能一眼看出数据是否新鲜、哪条连接出了问题，以及系统绝不会真实下单。

## 3. 已确认的产品决定

以下内容已经由用户确认，是本规格的硬约束：

| 主题 | 决定 |
|---|---|
| 本地入口 | `init`、`up`、`status`、`down` 四个日常命令；可额外提供 `logs` 与显式 `verify` |
| 数据库 | 新建隔离的 `tennix_live_local`；绝不清理、复用或迁移旧 `tennix` 测试库 |
| 网球实时 | 正在跟踪的 live 比分等走 API-Tennis WebSocket；不是固定秒级 REST 轮询 |
| 市场实时 | 已发现且精确匹配的 Polymarket book 走公开 WebSocket |
| 赛程与排名 | 真实但低频自动同步；赛程不是 WebSocket，排名通常按周变化，不做秒级刷新 |
| 球员中文名 | 首次/显式维护时可离线 LLM 补齐；`up` 绝不为翻译反复消耗 LLM |
| 故障原则 | 保留最后可信数据和时间；断流/过期时显式 `STALE`/`GAP`，禁止新的 `BUY`/`SELL` |
| P3 | 使用真实市场与真实比赛数据，但仅 `paper`；当前模型未晋升时保持 `NO BET`/`MARKET_ONLY` |
| 配置 | 根目录 `.env` 是唯一人工配置入口；绝不新增 `backend/.env`、`frontend/.env` 或 `.env.local` |
| 数据保留 | 供应商 raw payload 保留 14 天；canonical 事实和 paper 审计证据按既有策略保留 |

## 4. 用户实际会怎么用

这部分是日常“人话版”；命令名为本阶段要实现的接口，并非当前仓库已存在的脚本。

```text
第一次：tennix-live init
平时启动：tennix-live up
查看情况：tennix-live status
停止：tennix-live down
```

`init` 是第一次准备：建立一套干净的真实运行数据库、下载初始球员和排名、建立英文别名，并对缺失中文名做一次离线补齐。它完成后退出，不保持连接，不持续更新比分。

`up` 是每天开机：启动数据库、Redis、真实数据后台、后端和前端；它持续运行，并自动跟进真实数据。

`status` 用一句话和简表说明：服务是否启动、网球流和市场流是否健康、赛程/排名最后更新时间、当前跟踪比赛/市场数量、P3 是否仍为 paper-only，以及模型是否可产生动作。

`down` 只停止本工具启动的本地进程和容器，不删除数据库、Redis 数据、paper ledger 或任何项目文件。真正清空数据必须是单独、显式、有确认的未来命令；本阶段不提供隐式 reset。

## 5. `init` 与 `up` 的精确分工

| 数据或动作 | `init` | `up` |
|---|---|---|
| 创建/迁移 `tennix_live_local` | 是，幂等 | 只检查已完成；缺失时提示先运行 `init` |
| 初始 ATP/WTA 排名与球员目录 | 是 | 读取并低频同步更新 |
| 英文和中文球员别名 | 建立英文；仅缺失项离线补中文 | 只使用现有别名；当前新球员先有英文，不自动调用 LLM |
| 当前 live/upcoming 赛程 | 做首个 canonical seed | 启动时刷新并持续低频同步 |
| live 比分、发球方、PBP、统计 | 不持续接收 | 对被跟踪比赛通过 WebSocket 实时更新 |
| Polymarket 市场和订单簿 | 不需要长期订阅 | 发现市场、严格映射后通过 WebSocket 实时更新 |
| P3 paper lifecycle | 不运行 | 持续跟踪，但绝不真实交易 |
| LLM 调用 | 仅中文别名补齐，且只补缺失项 | 仅用户主动 Chat；启动和日常同步不调用 LLM |

### 5.1 `init` 的具体行为

`init` 必须按顺序完成：

1. 读取并校验根 `.env`，但日志只出现变量名和错误码，不出现任何值；
2. 启动或等待本地 PostgreSQL 与 Redis；
3. 确认目标数据库是专用 `tennix_live_local`，拒绝指向默认 `tennix`、测试库或未知宽泛目标；
4. 若数据库不存在则创建；运行 Alembic 至当前 head；不会 downgrade、truncate 或删除已有 live 数据；
5. 用真实 API-Tennis 拉取 ATP/WTA 单打排名，写入 canonical player identity、内部 ID、英文别名和排名快照；
6. 拉取当前 live/upcoming 赛程，写入最小 canonical 比赛目录和当前参赛球员身份；
7. 对缺失中文显示名的已知球员执行离线批量 enrichment。每批先整体校验再写入；重跑只补缺失项，已覆盖成员不再调用 LLM；
8. 输出聚合数字：球员数、ATP/WTA 覆盖、英文/中文显示名覆盖、发现的比赛数、迁移版本。不得打印供应商 payload、外部 ID 或凭据。

若 API-Tennis 或 LLM 不可用，`init` 必须报告哪一步未完成并返回非零；不得创建看似完整、实际混入 fake 数据的库。已有成功数据不被删除。

### 5.2 `up` 的具体行为

`up` 只在数据库已完成 `init` 和迁移已到 head 时启动。否则明确提示“请先运行 `tennix-live init`”，不偷偷初始化，以免意外消耗 API/LLM 配额。

启动后，`up`：

1. 启动/等待基础设施；
2. 启动唯一的 `runtime` 后台进程；
3. 等待 runtime 写入健康状态和第一轮赛程/市场发现结果；
4. 启动 FastAPI；
5. 启动 Next.js；
6. 输出本地浏览器地址和 `status`/`logs` 的下一步提示。

若某个子进程不能健康启动，`up` 只关闭这次由它启动的进程，保留数据库数据，并给出可执行的下一步，例如“API-Tennis key 缺失”或“8000 端口已被其他程序占用”。它不得杀死未知的用户进程。

## 6. 进程边界与数据流

本阶段采用一个 launcher 管理多个本地角色，而不是让浏览器、FastAPI 和测试各自争抢供应商连接。

```text
根目录 .env
      │
      ├── PostgreSQL + Redis（Docker Compose）
      │
      ├── runtime：唯一的上游实时连接拥有者
      │      ├── API-Tennis discovery + live WebSocket
      │      ├── Polymarket discovery + market WebSocket
      │      ├── canonical persistence / Redis hot state
      │      └── P3 prediction / decision / paper lifecycle
      │
      ├── FastAPI：REST、SSE、Chat、canonical 查询
      │
      └── Next.js：浏览器界面
```

### 6.1 runtime 的职责

`runtime` 是唯一可以：

- 持有 API-Tennis live WebSocket；
- 持有 Polymarket market WebSocket；
- 周期性发现赛程、市场、规则和最终结算；
- 合并 P2 viewer demand 与 P3 durable tracking demand；
- 向 PostgreSQL 写入 canonical 更新、向 Redis 发布 hot state/SSE 事件；
- 驱动 `RealtimeWorker`、`MarketWorker`、`DecisionWorker` 和 `PaperTradingService`。

它使用一个本地异步进程即可，不拆微服务、不加入 Kafka、Redis Streams、外部队列或云 cron。

P2 viewer lease 仍可让正在打开 Match Page 的比赛获得实时订阅；P3 的赛前窗口、已精确映射比赛和未结 paper position 仍可在无人打开网页时持续跟踪。最终 demand 是两者的并集，并受既有订阅上限保护。

### 6.2 FastAPI 的职责

FastAPI 不再在 local-real runtime 模式中自行启动上游 WebSocket 或定时 discovery。它负责：

- 读取 PostgreSQL canonical facts 和 Redis hot state；
- 对浏览器发送 REST/SSE；
- 运行业务语义 Chat 工具与 LLM；
- 按现有接口返回 Home、Match、Players 和 Markets 数据。

为保留 P2 的按需历史/H2H 查询，FastAPI 可以对**用户主动触发且本地未命中**的、受 cache 和限流保护的 API-Tennis REST 查询调用现有 `TennisService`。这不是后台轮询，也不持有 WebSocket；结果仍必须转换为 canonical 模型并按既有规则缓存/持久化。常规 Home、实时 Match、排行和市场页面优先读取 runtime 已同步的 read model。

### 6.3 浏览器的职责

浏览器只连接 Next.js 同源 Route Handler，再由它代理 FastAPI。浏览器绝不获得 API-Tennis key、LLM key、数据库地址、Polymarket token ID、供应商外部 ID 或交易材料。

浏览器刷新不会重建上游 WebSocket。它只会重新请求快照和 SSE；runtime 中的共享 demand/订阅继续存在。

## 7. 为真实运行增加的 read model

现有 provider adapter、canonical model、identity repository、P2 snapshots、P3 market repository 和 paper ledger 保持权威语义。本阶段只补齐“运行中读取”的必要投影，不镜像供应商 JSON。

| 读模型 | 内容 | 写入者 | 读者 |
|---|---|---|---|
| Canonical match catalog | live/upcoming/finished 的最小比赛事实、筛选字段、内部 ID、source/as-of | runtime discovery / reducer | Home、Match、Chat |
| Player directory + ranking snapshot | 内部 player、英文主名、中文辅名、aliases、排名和更新时间 | `init` / ranking sync | Players、resolver、Chat |
| Live match snapshot | 当前 score、server、PBP、statistics、quality、version | `RealtimeWorker` | Match、SSE、prediction |
| Market + exact link | 公开市场的 canonical 信息、规则快照、严格 match link | market discovery | Markets、DecisionWorker |
| Hot book and decision state | 最新 book、freshness、decision cursor | `MarketWorker` / `DecisionWorker` | API/SSE、P3 UI |
| Paper ledger | intent、fill/no-fill、position、exit、settlement | `PaperTradingService` | `/markets`、Match、Chat |
| Runtime health summary | 每个 source 的状态、last success、last event、stale/gap、计数 | runtime | `status`、本地健康端点 |

所有表只保存 canonical 事实、最小审计证据或健康摘要。供应商 raw payload 仍使用既有 14 天清理策略。第三方 ID 仍只存在私有映射表，不能出现在公共 API、页面、日志或 Chat。

## 8. 赛程、排名、市场的更新策略

“真实”不等于所有数据每秒请求一次。不同数据按变化速度采取不同策略。

| 数据 | 更新机制 | 默认频率 | 原因 |
|---|---|---:|---|
| 已跟踪比赛的比分/PBP/统计 | API-Tennis WebSocket + 首帧/重连 REST 校准 | 事件驱动 | 这是 live state，不能依赖常态轮询 |
| 已跟踪 Polymarket book | Polymarket WebSocket + 首帧/重连 REST 校准 | 事件驱动 | 这是可执行价格，实时性优先 |
| live catalog | API-Tennis REST discovery | 60 秒 | 发现新开始/结束比赛和状态变化，不替代单场 WebSocket |
| upcoming catalog | API-Tennis REST discovery | 10 分钟 | 赛程变化相对低频，控制配额 |
| ATP/WTA 排名 | standings 同步 | 启动后每天一次 | 排名通常按周更新；日检足够且可发现修订 |
| Polymarket tennis moneyline discovery | 公共 Gamma/CLOB REST | 2 分钟 | 发现新市场、规则变化和可映射对象 |
| resolution/rules recheck | 只对 close/position/有变化市场 | 有界低频 | 结算必须以 provider 最终状态为准 |

这些默认值必须成为有边界的 root `.env` 配置，便于本地调整，但不允许设置为无限高频。实现时要在真实 provider 配额和 WebSocket 能力范围内保守运行。

市场映射继续严格遵循 P3 规则：两个 outcome 必须解析为内部 player ID、无序球员对唯一一致、时间窗口和赛事上下文不冲突、单打且在模型覆盖域。不得用 LLM、模糊分数或人工永久绑定凑映射。未映射市场仍可展示为 `MARKET_ONLY`，但不会进入决策或 paper lifecycle。

当前赛程中遇到目录外球员时，runtime 可以建立确定性的英文 identity/alias，使其能参与 canonical 匹配；中文名留待下次显式 enrichment。这样既不阻塞实时市场映射，也不让后台悄悄花 LLM 配额。

## 9. 数据新鲜度、断流与安全行为

这里的 `STALE`/`GAP` 不是假设市场会比裁判数据慢几秒。它只处理真正的连接中断、重连缺口、过期快照或无法验证的状态，避免把旧数据误认为新数据。

### 9.1 四种状态

| 状态 | 含义 | 界面与决策行为 |
|---|---|---|
| `fresh` | 连接健康，最近成功校准在允许窗口内 | 正常显示；P3 可在其他 hard gate 通过时评估动作 |
| `degraded` | 某个非关键低频同步失败，但仍有可信上次结果 | 显示更新时间和降级说明；不伪造新数据 |
| `stale` | 关键数据太旧或连接健康无法确认 | 保留最后可信值和时间；撤销新的 `BUY`/`SELL` |
| `gap` | 断线、序列缺口、队列溢出或重连期间 | 标记 gap，REST 校准后才恢复；不得补造 point、book 或成交 |

实时体育流不能仅因“几十秒没有得分”标为 stale：网球比赛可能自然停顿。体育 freshness 依赖连接/心跳状态和成功 reconciliation，而不是单纯的比分变化频率。市场 book 使用既有 book freshness、WebSocket 心跳和 REST 对账共同判定。

### 9.2 故障处理

- 单场网球流断开：关闭旧 reader、记录 gap、REST 取最新 canonical snapshot、重新订阅；恢复前不产生依赖该状态的新动作；
- 市场流断开/队列溢出：记录 gap、REST 重建 order book、重新订阅；恢复前不产生新 `BUY`/`SELL`；
- 赛程或排名同步失败：保留上次成功结果和时间，下一轮重试；不删除目录或把字段写成零；
- Polymarket discovery/mapping 失败：不影响网球页面；市场面显示现有数据或诚实空态；
- LLM 失败：已有 structured facts 仍可展示；Chat 使用既有安全降级，不影响数据后台；
- 数据库/Redis 失败：runtime 标记核心失败并停止发布不可信的新状态；launcher 让 `status` 明确显示失败来源。

任何 pending paper intent 到期时，如订单簿无法被验证，只能按照既有 `BOOK_UNVERIFIABLE`/`NO_FILL` 语义结束，绝不补造成交。

## 10. P3 的运行边界

`up` 在完整真实运行模式下使用 `TENNIX_P3_MODE=paper`：这允许真实比赛数据、真实公开市场数据、真实 quote 和 paper ledger 走完整链路，但没有交易 client，也不存在真实订单能力。

当前没有通过晋升门的 model artifact。因此第一版真实本地运行通常会显示：

```text
真实市场 + 真实比赛数据 + MARKET_ONLY / NO BET
```

这不是故障，也不是伪造的保守结论，而是 P3 的 fail-closed 设计。只有未来在独立、可审计的模型训练和 shadow 证据通过后，才可能出现 paper `BUY`/`SELL`。即使那时，仍然只影响 paper ledger；自动下单继续是单独 `deferred` 议题。

## 11. 配置与隔离

根 `.env` 继续是唯一人工维护文件。本阶段新增的 local-runtime 设置必须采用 `TENNIX_LOCAL_RUNTIME_` 前缀，并在 `.env.example` 给出安全本地默认值。例如：

```dotenv
TENNIX_LOCAL_RUNTIME_DATABASE_URL=postgresql+asyncpg://tennix:tennix@127.0.0.1:5432/tennix_live_local
TENNIX_LOCAL_RUNTIME_REDIS_URL=redis://127.0.0.1:6379/11
TENNIX_LOCAL_RUNTIME_LIVE_CATALOG_SECONDS=60
TENNIX_LOCAL_RUNTIME_UPCOMING_CATALOG_SECONDS=600
TENNIX_LOCAL_RUNTIME_RANKING_SECONDS=86400
TENNIX_LOCAL_RUNTIME_MARKET_DISCOVERY_SECONDS=120
```

launcher 只把这些值映射为子进程已有的 `TENNIX_DATABASE_URL`/`TENNIX_REDIS_URL`。测试、replay、Playwright 和普通开发命令继续使用它们自己的显式隔离配置，不被 launcher 重写。

安全约束：

- `init`/`up` 拒绝 `tennix_live_local` 之外的默认数据库名，除非未来有单独明确的高级覆盖；
- `init`/`up` 拒绝运行在 `.env` 不完整、provider 不是 `api_tennis` 或 P3 不是 `paper` 的“真实运行”配置下；
- 只给 runtime 和服务端进程注入必要 secrets；Next.js/browser 永不读取这些变量；
- logs、`status`、真实 smoke 和异常信息只输出聚合状态/错误码，不打印 key、URL query、raw payload、token/external ID 或 wallet 材料；
- launcher 自身的 PID、端口和日志索引写入操作系统临时目录，不污染 Git 工作树。

## 12. `status`、`logs` 与可观察性

`tennix-live status` 应输出易读的本地摘要；也支持机器可读 JSON 供以后测试使用。最少包含：

```text
stack: running
database: healthy
redis: healthy
runtime: running
tennis live stream: connected, 2 tracked, last reconcile 12s ago
schedule: fresh, last successful sync 4m ago
rankings: fresh, last successful sync 3h ago
polymarket: connected, 3 tracked markets, last book update 1s ago
p3: paper-only, model not promoted, real orders disabled
api / frontend: healthy
```

数字只是示意；没有 live 比赛、没有可映射市场或模型未晋升都是正常状态，必须显示为事实而非红色故障。

`tennix-live logs runtime`、`logs api`、`logs frontend` 只读取本次 launcher 创建的日志。所有日志采用结构化、secret-safe 的 event name、reason code、计数和时间，不记录完整供应商响应。

runtime 还必须向 Redis/数据库写入低频 health summary，以便 API/浏览器在不访问外网的情况下展示 freshness；`status` 即使某一个 HTTP 服务已经停止，也能区分“进程不存在”和“数据源连接断开”。

## 13. 启动与停止的可靠性

### 13.1 `up` 的顺序

1. 加载 root `.env`，验证 live-local URL、必需 API-Tennis/LLM 值及 `paper` 边界；
2. 以 Docker Compose 确保 PostgreSQL 和 Redis healthy；
3. 检查 `tennix_live_local` 的 init marker、schema version 和运行锁；
4. 检查 8000/3100 等端口；若被非本 launcher 的进程占用，退出并说明，不杀进程；
5. 启动 runtime，等待健康记录和第一次 discovery；
6. 启动 FastAPI，等待本地 health endpoint；
7. 启动 Next.js，打印浏览器地址；
8. 写入自己创建的 PID/容器 ownership 信息。

### 13.2 `down` 的顺序

1. 先请求 runtime 有序停止：停止接收新 demand、关闭 WebSocket、flush 有界 observation buffer；
2. 停止 API 和 Next.js；
3. 仅停止本次 `up` 启动的 Compose 服务；若容器在 `up` 前已运行，则保留；
4. 不删除 volume、数据库、Redis 数据或日志诊断材料。

如果 launcher 意外退出，下一次 `up` 必须检测遗留 PID 并只回收自己可证明拥有的进程；它不能按端口号粗暴 `kill`。

## 14. 验证策略

“真实运行”必须有证据，但不能让每次普通测试都消耗外部配额。

### 14.1 默认确定性门

所有单元、contract、replay、PostgreSQL/Redis integration、前端单测、typecheck、build 和 Playwright 视觉/功能门继续使用 fake/replay。它们是每次开发的主回归门。

新增 launcher/runtime 测试必须覆盖：

- `init` 仅指向专用数据库、幂等、禁止 reset；
- `up` 在未 init、配置错误、端口占用、子进程失败时安全退出；
- runtime 只创建一套上游 WebSocket ownership；
- P2 viewer demand 与 P3 durable demand 合并且不会重复订阅；
- 赛程/排名/市场 scheduler 的有界频率；
- stale/gap 状态、恢复路径和新动作抑制；
- `down` 不停止未知进程、不删 live 数据；
- 公开 REST/SSE/日志没有 provider ID、凭据或交易材料。

### 14.2 显式真实核验

新增 `tennix-live verify` 是用户主动执行的受限 smoke，不会被 `up` 自动调用。它使用 root `.env`，只做有限、只读检查：

- API-Tennis 认证、排名或当前赛程读取；
- API-Tennis live WebSocket 在存在可订阅比赛时接收/校准；没有 live 比赛时记录诚实 skip；
- Polymarket tennis discovery、规则读取与 market WebSocket；没有活跃 book 事件时记录诚实 skip；
- 可选真实 LLM Chat contract（仅显式 flag 开启）；
- 根数据库、Redis、API 和浏览器端到端状态一致性。

它输出通过/失败/诚实 skip 和聚合计数。缺少凭据、赛事空窗或公开市场安静不能被包装成“全部通过”，更不能导致 fallback fake 数据。

### 14.3 浏览器验收

本地完整运行至少验证：

1. Home 显示真实赛程或诚实空态，并带正确 freshness；
2. Players 显示真实排名和英文主名/中文辅名；
3. Match Page 对已跟踪比赛显示真实 score/PBP/统计更新，或在无 live 比赛时诚实说明；
4. `/markets` 显示真实公开市场，精确映射失败时仍为 market-only；
5. Match Decision Workbench 显示 paper-only、未晋升即 `NO BET` 的真实状态；
6. 断开某条数据流后，页面保留最后可信值、标出延迟，并不产生新的动作；
7. 重启 `up` 后内部 ID、canonical 数据、paper ledger 和 cursor 恢复，不产生重复 intent/fill。

## 15. 明确不做

- 不做云部署、后台常驻系统服务、cron、认证、多用户或好友共享账本；
- 不做自动下单、钱包、私钥、签名、交易 API 或交易按钮；
- 不做新的市场类型、加仓、换边、重新入场、仓位管理优化或模型阈值放宽；
- 不做全量历史数据镜像、供应商 JSON 镜像或未经许可的训练数据积累；
- 不用 LLM 作实时球员翻译、市场映射、概率计算、成交推断或动作决策；
- 不增加 Kafka、Kubernetes、微服务、Redis Streams、Airflow、Feature Store 或 Vector DB；
- 不修改已冻结的 P1–P3 页面视觉设计，除非未来有单独的产品设计任务。

## 16. 实现完成的退出条件

后续实施任务完成时，必须同时满足：

1. 根 `.env` 是唯一人工入口，且 `init/up/status/down` 可在干净本机按文档完成；
2. 测试数据库 `tennix` 和 live 数据库 `tennix_live_local` 相互不影响，所有 destructive 操作都不存在或显式拒绝；
3. runtime 是 API-Tennis/Polymarket 上游 WebSocket 的唯一拥有者；浏览器刷新和 FastAPI 重启不导致重复订阅；
4. live score/book 事件驱动，赛程/排名/市场 discovery 有界低频同步，实际频率可从健康状态核验；
5. P1、P2、P3 页面和 Chat 从真实 canonical 数据工作，空窗/无权限/断流均诚实降级；
6. P3 仍只有 paper lifecycle，任何路径均无法发真实订单；
7. 默认确定性全量门、真实 opt-in smoke、双视口 Playwright 和一次人工 local-real run 都有实际证据；
8. `PROJECT.md`、`ROADMAP.md`、`CURRENT.md`、runbook 和 Git 提交记录彼此一致。

## 17. 需要在实施计划中继续细化的事实

本规格已经冻结产品和架构边界，但不假装替代实现前的代码级调查。实施计划应在不扩大范围的前提下，确认：

- 现有 migration/read repository 哪些可直接复用、哪些最小 read-model 投影确实缺失；
- API-Tennis 当前套餐对 standings、fixtures 和 live WebSocket 的实际配额/并发上限，以决定各 scheduler 上限；
- Polymarket 当前公开 discovery/WS 的实际事件活跃度和重连语义；
- 本机 Docker、`uv`、`pnpm` 的最短可靠启动命令；
- 真实数据库创建权限与最小、可逆的 init marker schema；
- 已有 P2/P3 replay 和 live gate 中哪些可以直接作为 P4.0 验收证据。

这些是验证和拆分实现任务的工作，不授权改写本规格中的安全边界。
