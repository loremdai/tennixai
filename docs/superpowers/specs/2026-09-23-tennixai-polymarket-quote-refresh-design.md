# TennixAI T91 Polymarket 报价覆盖与刷新设计

> **状态：** 已按用户选择 B 与官方文档/只读实测形成；实施范围仅限 T91。
> **日期：** 2026-09-23
> **关联任务：** [T91](../../../ROADMAP.md)
> **项目边界：** [PROJECT.md](../../../PROJECT.md)
> **当前交接：** [CURRENT.md](../../../CURRENT.md)

## 1. 目标与非目标

修复 /markets 大量缺报价的根因，让全部活跃网球单场胜者市场都能以供应商真实 outcome 名称展示；报价有值时来自真实 CLOB 买卖盘，空簿、缺失和断流各自明确标记。用户已选择：即使球员身份暂时无法严格匹配、或为双打，也可进入展示目录；这些行绝不因此获得球员 ID、模型、机会或 Paper 资格。

机会页为空是独立模型状态：当前部署未晋升模型时继续诚实显示无机会；本任务不伪造 BUY/WAIT，也不以填充机会页为验收目标。

不做：自动交易、钱包/签名、LLM/RAG 名称补全、模型训练/晋升、完整行情历史库、其他市场类型、浏览器定时轮询、P2 比赛 SSE 改动。

## 2. 经官方资料与只读实测确认的依据

- Gamma 官方 keyset 支持 next_cursor → after_cursor 全量翻页，Events keyset 过滤参数使用 tag_id；tag slug 可由 /tags/slug/{slug} 查询数值 ID。本地完整遍历得到 485 个活跃网球赛事、412 个两项胜者市场。
- Polymarket 官方 market WebSocket 支持动态订阅/退订 token，并可启用 custom_feature_enabled 收 best_bid_ask。824 个当前 outcome token 的单条只读连接实测持续 60 秒，接收 49,221 帧；官方没有公布订阅数量上限，因此实现需有界、可降级，不能宣称无限容量。
- 官方 CLOB POST /books 每次最多 500 个 outcome token。全目录 824 token 的只读复核返回 820 本：397 场两边有挂单、13 场两边空簿、2 场四个 token 未返回。空簿显示暂无挂单；未返回显示暂不可用，均不得补造数值。
- 官方参考：[Real-Time Data](https://docs.polymarket.com/market-data/realtime-data)、[Prices and Order Books](https://docs.polymarket.com/market-data/prices-order-books)、[Discover Markets](https://docs.polymarket.com/market-data/discover-markets)。

当前缺失主要来自应用只取 Gamma 第一页、严格球员解析失败即丢弃 listing、旧 listing 未退役，而不是大部分市场没有流动性。页面当前只在首次挂载读取第 1 页，且快照 job 没有发出页面失效通知。

## 3. 目标架构与安全隔离

采用两条数据通道：

| 通道 | 输入与消费者 | 身份要求 | 允许副作用 |
|---|---|---|---|
| 全目录展示报价 | Gamma keyset + 单条只读 market WebSocket + CLOB REST 校准 → /markets 全部市场 | 两个真实 outcome 名称和私有 token mapping 即可；不要求 player ID | 保存最新两侧报价、发布合并后的 listings 更新通知 |
| 严格决策/Paper | 现有 canonical Market + active match link + 严格赛事/单打资格 + tracking demand → Prediction/Decision/Paper | 两个真实 internal player ID 与严格比赛映射 | 保持现有规则、模型、账本和结算行为 |

新增独立 MarketListing 展示领域类型；不放宽 MarketOutcome.player_id 必填约束。Gamma provider 可返回完整有效胜者 listing，但只有解析出两个 distinct canonical player IDs 且符合既有资格的行才可构造严格 Market、抓取决策规则、关联模型或进入 paper。双打/未映射行只保存展示名称、状态、赛事时间与 private external mapping。

Provider event/condition/token IDs 继续只存在 adapter、market_external_ids 与受 14 天保留的 raw 记录。公共 DTO、SSE、页面、URL 和日志只用内部 market ID、outcome 名称、真实报价和时间；不得输出 provider IDs 或凭据。

## 4. 发现、持久化与安全退役

1. 先以官方 /tags/slug/tennis 将稳定 slug 转为 tag_id，再以 /events/keyset?tag_id=…&closed=false 开始扫描；将 next_cursor 作为下一页 after_cursor。循环 cursor、传输失败、响应/页面解析失败都将本轮标为不完整，不得用不完整结果退役已有 listing。
2. 仅接纳 active、未关闭、tennis moneyline、恰好两个非空 outcome 名称、两个 token 和 condition mapping 均有效的 listing。按供应商 outcome/token 顺序固定 A/B 对齐。
3. 成功完整扫描后 upsert 所有展示 listing，再把本轮未出现且仍 open/scheduled 的历史 listing 标为 closed。只改活动状态，不删除 market、private mapping、rules、link、observation、quote 或 paper ledger；不覆盖 resolved。失败时保留旧状态，下轮重试。
4. Rules 仅对严格身份映射且符合现有 decision/paper 资格的市场抓取。展示目录不为数百条双打/未映射行串行读取 rules。
5. 未结 Paper position 仍由既有 ledger 驱动 resolution recheck；Gamma 中暂时缺席不能删除/抹除其追踪与结算需求。

## 5. 报价获取、刷新及失败语义

- 使用单个、只读、独立于严格 MarketWorker 的广目录 WebSocket，订阅全部当前 open/scheduled listing 的 token；订阅声明带 custom_feature_enabled=true。目录变化时使用官方动态订阅/退订更新，不按每场另开 socket。只按 best_bid_ask.payload.tokenId 对接私有 token mapping；不用 event 的 condition/token 字段进入公共 DTO。
- 启用 custom_feature_enabled，展示通道只消费 best_bid_ask；高频 price_change 等非目标帧不得逐帧写 PostgreSQL、Redis Pub/Sub 或触发浏览器重取。每个 market/token 只保留最新值，按短窗口合并写入；真实内容未变则沿用幂等写入规则不落库。
- 启动、断线重连和定期校准使用 CLOB POST /books，按最多 500 token 分批。当前 824 token 仅需两批；将现有快照保护上限提高至能覆盖至少 500 场并把默认批次提高到官方上限 500，使当前 412 场可完整刷新。保留 Retry-After、退避、失败隔离与 coverage 计数。未来触及配置保护上限时，仍展示目录行，报价状态明确 limited 并公平轮转，不静默饿死。
- 盘口字段按 outcome 顺序保存到既有 MarketQuoteSnapshot projection；未知身份时 levels 可为空、player IDs 为空，只使用 outcome_a/b 的 bid/ask 列，不伪造 OutcomeBook.player_id。可在无 schema 变更情况下表达 id-less 报价；如实现证实必须改 schema，则增加可逆迁移。
- 严格 P3 per-market WebSocket、DecisionWorker、PredictionService、PaperTradingService 不消费广目录 feed。该通道的任何报价变化不得产生模型概率、edge、动作或 paper 事件。
- 无效/空响应不等于 0。两边有盘、单边/部分、双边空簿、token 未返回、数据过期、配额/网络失败、保护上限未轮到必须维持当前 QuoteState 的诚实区分。
- 行情 WebSocket 的“无新价格帧”表示价格没有变化，不表示数据断开。展示报价仍保留真实 source as_of；只在广目录连接健康时把 realtime projection 判为实时，连接断开则立即降级，等 REST 校准完成后恢复。定期 REST snapshot 为安静市场提供新采样；不能把静默的 token 当成断流。

## 6. 查询、SSE 与页面

- /markets 查询返回全 catalog 的分页 total 与所有有效行。名称始终优先使用供应商 outcome label；仅在严格 canonical identity 已有时才补 canonical 名称和 internal match link。
- API 的 page/page_size 继续生效。页面初次读取第一页，并提供可访问的“加载更多”直到已加载数达到 total；筛选继续覆盖全部已加载列表。报价通知触发已加载页的 listings 合并重取，不触发机会与 paper 重取。
- 增加独立全局 quote/catalog invalidation SSE 事件（建议 quotes_changed），表达“报价展示投影有更新”，不伪装成 market_delta、不携带 provider ID/quote 原始 payload。runtime 按短窗口合并/节流，连接状态变化也通知页面；前端复用现有 debounce，只重取 listings。
- 快照投影只有内容或有效状态真的改变时才发通知。不得以 heartbeat、无关 decision/paper 事件冒充 quote 更新。
- `/markets` 继续显示清晰的 realtime/snapshot/partial/no_liquidity/unavailable/stale/limited 状态与真实 source 时间；页面布局沿用已批准 v0，不改 P1/P2。
- opportunities 在模型 not_promoted 时仍为空并说明原因。真实报价覆盖提高不会改变 model_availability、安全规则或机会资格。

## 7. 验收门

1. Provider 测试覆盖多页完整遍历、重复/失败 cursor fail closed、两项胜者筛选与真实名称、无身份/双打保留、畸形市场隔离；严禁泄露 provider IDs。
2. Reconcile 测试证明完整扫描后 unseen 活跃市场被关闭；任何中途页失败、持久化失败都不退役；resolved 与未结 ledger 历史保留。
3. 报价测试证明无 player IDs 的 REST/WS 双边报价可持久化和展示；空簿、缺 token、partial、stale 不补零；500-token batch 边界与保护上限公平轮转正确。
4. Broad WS 测试覆盖动态 add/remove、只处理 best_bid_ask、断流 stale、REST baseline 恢复、短窗 coalesce、有界队列/重连；与严格 MarketWorker/Decision/Paper 零耦合。
5. SSE/API 测试证明 quote change 发布独立事件、仅 listings 刷新，无变化无通知，其他 stream cursor 语义不变。
6. 前端单测与 Playwright 覆盖多页加载、total/筛选、实时报价事件刷新、诚实空态。未映射/双打不出现 Match 导航/模型动作；not_promoted 的机会仍诚实为空。
7. 运行涉及模块测试、后端确定性套件、前端 test/typecheck/build、Playwright 功能与视觉门；任何视觉 PNG 变化逐张审阅，不能 mask、调阈值或盲目重录。
8. 真实只读 smoke 使用完整 Gamma 与最多 500-token CLOB `/books`；只报告聚合数量/状态，不打印 token、condition、事件 ID、凭据或 payload；不启动本地全栈，除非用户明确要求。
