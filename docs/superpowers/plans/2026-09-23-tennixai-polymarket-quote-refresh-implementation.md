# TennixAI T91 Polymarket 报价覆盖与刷新实施计划

> **Goal:** 修复 Gamma 漏页、身份耦合、旧市场不退役、报价无刷新通知与广目录实时覆盖；保持严格模型/Paper 安全边界。
> **Architecture:** 完整 Gamma keyset → MarketListing catalog；单条只读广目录 WS + REST baseline/校准 → id-less latest quote projection → 分页 /markets 与独立 quotes_changed SSE。既有 strict MarketWorker → Decision/Paper 路径不变。
> **Tech Stack:** Python 3.12、FastAPI、Pydantic v2、SQLAlchemy async、PostgreSQL、Redis、httpx、websockets；Next.js App Router、TypeScript、Vitest、Playwright。
> **Spec:** [T91 design](../specs/2026-09-23-tennixai-polymarket-quote-refresh-design.md)
> **Global Constraints:** 只读 Polymarket；不新增钱包/签名/下单、LLM、模型训练/晋升或行情历史；根目录 .env 是唯一配置入口；不打印 provider IDs/凭据；保留已有用户改动；`MarketOutcome.player_id` 不放宽； P2 SSE 字节级契约不变；未映射/双打零 model/decision/paper；snapshot/广目录 WS 零 Decision/Paper 副作用；已批 v0 几何不改；完成时更新三份总控、提交并推送。
> **Review Focus:** 全扫描是否严格 fail closed；未知身份是否确实停留在展示通道；断线/静默与 no_liquidity 是否区分；通知/写库是否按变化合并；closed/reconcile 是否保留 unsettled ledger；机会空态是否仍显示真实 not_promoted 原因。

## 权威输入

- 设计规格：[T91 design](../specs/2026-09-23-tennixai-polymarket-quote-refresh-design.md)
- 官方：[Realtime Data](https://docs.polymarket.com/market-data/realtime-data)、[Prices and Order Books](https://docs.polymarket.com/market-data/prices-order-books)、[Discover Markets](https://docs.polymarket.com/market-data/discover-markets)
- 总控：[PROJECT.md](../../../PROJECT.md)、[ROADMAP.md](../../../ROADMAP.md)、[CURRENT.md](../../../CURRENT.md)
- Next.js 改前端前，先读 `frontend/AGENTS.md` 指定的本地 Next.js 文档。

## 执行任务

### [x] 1. 全量 Gamma listing adapter（先测后实现）

**文件：** `backend/app/markets/polymarket.py`、`backend/app/markets/polymarket_dtos.py`、市场领域模型；`backend/tests/test_polymarket_provider.py`。

- 先加失败测试：官方 /tags/slug/tennis 解析 tag_id，再按 /events/keyset 的 next_cursor → after_cursor 多页直到终止；重复 cursor、传输失败、畸形页使整次扫描报不完整；保留双打/未知身份有效 moneyline 的两侧供应商名称；拒绝非 moneyline、closed、缺名/token/condition；断言公共/异常字符串不含 provider ids。
- 新增展示专用 MarketListing/扫描结果；不要把 MarketOutcome 改成可空。
- 每场仅做必要的严格 identity resolve；未识别时仍返回 display listing。provider 负责把私有 event/condition/token mapping 交给既有 registrar。
- 验证现有严格 Market 接口消费者未改变；运行 provider focused tests 与 Ruff。

### [x] 2. 完整目录写入与安全退役

**文件：** `backend/app/persistence/market_repositories.py`、`backend/app/persistence/models.py`（仅必要时）、`backend/app/runtime/daemon.py`；`backend/tests/integration/test_market_catalog_reconciliation.py`、runtime focused tests。

- 先测试：全量 listing upsert 后 unseen open/scheduled 变 closed；扫描不完整或 upsert 失败时不关任何旧行；resolved、rules、links、quote、observation、unsettled ledger 不删除；恢复出现的 listing 可重新 active。
- 目录成功后才执行 reconcile。必要时批量事务；provider 预扫描失败时不得改变活动目录。
- 仅对严格 mapped 且现有领域条件合格的 Market 执行 rules fetch / match link；展示-only listing 不产生 rules 请求。
- 验证：先写 runtime RED 测试，证明旧发现路径没有 reconcile listing；实现后 RED/GREEN 聚焦测试通过。隔离 PostgreSQL reconciliation integration `3 passed`；`tests/test_runtime_daemon.py` `51 passed`；相关 Ruff check/format 通过。

### [x] 3. id-less 全目录 REST quote baseline 与轮转

**文件：** `backend/app/markets/quotes.py`、`backend/app/runtime/market_snapshot.py`、`backend/app/config.py`、`backend/app/runtime/config.py`、`backend/app/runtime/assembly.py`、`.env.example`、runbook；对应 snapshot/provider/config tests。

- 先测试没有 player IDs 的两个 token 仍按 A/B 顺序生成双边真实 quote；空簿= no_liquidity、缺 token= unavailable/partial、超过保护 cap= limited，绝不造 OutcomeBook player ID。
- SnapshotCandidate 改为只需 internal market ID 与 private token pair。保留 fair rotation；默认覆盖上限提高到至少 500 场、token batch 500（官方每批上限），以覆盖当前 412 场/824 token。
- 429 继续尊重 Retry-After；单批失败隔离；聚合 coverage 显示候选、尝试、fresh、空簿、不可用、limited。
- 检查现有 schema 是否足够保存 id-less outcome_a/b bid/ask；只有确有必要才加可逆 migration。
- 已实现：quote projection 对任一缺失身份的 listing 保留按供应商顺序排列的真实 outcome bid/ask、spread/depth，但不生成 `OutcomeBook` 或内部球员 ID；`SnapshotCandidate` 仅依赖内部 market ID、私有 token pair；每轮用进程内 round-robin 游标轮转保护窗口，稳定保留 live/start/tier 优先级顺序；默认 500 市场、500 token/批。现有 nullable outcome quote 列足够，无 schema migration。
- 验证：先写 id-less、unmapped 和尾部轮转测试，原实现分别因 `OutcomeBook` 拒绝 null、candidate 排除、窗口不轮换而 RED；GREEN 后 quote/config/snapshot/runtime/provider 聚焦集合 `222 passed`，隔离 PostgreSQL reconciliation + id-less quote roundtrip `4 passed`，Ruff check/format 通过。
- 范围说明：round-robin 游标只在 runtime 进程内保存，重启后从首个优先候选开始；当前已实测目录 412 个市场，低于默认 500 上限。若未来目录长期超过 500 且进程频繁重启，再以真实需要评估持久化轮转游标，不在本任务引入额外状态表。

### [x] 4. 独立广目录 quote WebSocket

**文件：** `backend/app/markets/` 下的 quote-feed/decoder、`backend/app/runtime/daemon.py`、`backend/app/runtime/assembly.py`、runtime health/metrics；新增 `backend/tests/test_market_catalog_feed.py` 与 provider WS tests。

- 先测 decoder：custom_feature best_bid_ask 按私有 token→internal market/outcome index 更新正确；忽略 price_change/last_trade 等事件；未知 token 丢弃且不泄漏。
- 实现仅一个独立广目录只读 WS、动态 add/remove；strict `MarketWorker` roster/decision path 不共用。
- 使用有界 ingress 和 per-token latest-value coalescing；不逐帧持久化/发布；短窗 flush 同一 market 只写最后状态。断线/队列缺口立即将广目录 feed 标记 degraded，并用 `/books` baseline 恢复后标 live。
- 若正常关闭、取消或重连，task 退出必须被 await；无静默无限重连/无限队列。
- 已实现：单连接订阅所有 open/scheduled listing token，启用 `custom_feature_enabled`，按官方协议动态订阅/退订；只解析 `best_bid_ask`，私有 token 路由冲突时丢弃歧义 token；每市场仅保留最新两侧值，收到两 outcome 的双边字段后短窗合并写入；不混用 REST 旧值；每 10 秒 PING，3 个心跳周期未收到 PONG 即隔离降级并退避重连；每次连接前 REST baseline；健康源 `polymarket_catalog_quotes` 与严格决策源分开。daemon 托管 feed task，停止/取消会 cancel 并 await。
- RED/GREEN：feed 专项 `7 passed`（仅 `best_bid_ask`、原始名称身份无关、 coalesce、动态订阅、重连 baseline、心跳健康/超时、取消关闭）；quote + daemon + assembly 组合 `74 passed`；隔离 PostgreSQL 目录/id-less quote `4 passed`；相关 Ruff check/format 和 `git diff --check` passed。
- 页面将如何依据独立 feed 健康源立即将广目录 REALTIME 标为 stale、重连后恢复，由 Task 5 的读侧和 SSE invalidation 完成。

### [x] 5. 持久化镜像与独立报价 SSE invalidation

**文件：** `backend/app/markets/quotes.py`、`backend/app/markets/publisher.py`、`backend/app/api/routes.py`、`backend/app/service.py`、`backend/app/runtime/assembly.py`；对应 persistence、publisher、market-stream API tests。

- 先测 id-less REALTIME QuoteSnapshotRecord upsert/read roundtrip、REST/WS precedence、相同报价不产生无意义通知；feed 断线状态会让广目录 realtime 显示 stale，baseline 恢复后恢复可信状态。
- 新增全局 quotes_changed（或同义明确名）事件，独立于 market_delta；只在投影/连接健康状态实际变化且经合并后发布。公共 payload 仅含内部聚合版本/时间/计数，不含 provider ID、原始盘口或 token。
- SSE 订阅新增独立 channel/type；不更改既有 market/decision cursor，不给决策流伪造 market_delta。
- 已实现：id-less REALTIME quotes 可安全写入现有 nullable quote 列；广目录断线时服务层保留最后报价但标 stale，独立 feed 恢复后恢复 realtime；目录扫描仅在展示字段变化时更新 `updated_at` 并发通知，供应商 `observed_at` 递增不会制造虚假刷新；市场目录列表对相同更新时间增加内部 ID 稳定排序，保证 offset 分页不乱序。快照投影按真实 upsert/limited 变化合并通知；新 `quotes_changed` Redis/SSE channel 与 market/decision cursors 分离，内容只有 sequence/count/time；通知发布失败单独计入 health，不伪装成 Polymarket 行情断线。
- RED/GREEN：隔离 PostgreSQL 覆盖目录变化计数、相同目录幂等、更新时间戳推进、同更新时间稳定排序、id-less snapshot/REALTIME roundtrip；P3 service 验证断线 stale 与重连恢复；Redis publisher、SSE、snapshot job、runtime assembly/daemon 专项回归通过。任务收尾全量验证另记于 Task 7。

### [x] 6. API 与前端完整目录读取

**文件：** `backend/app/api/schemas.py`、`backend/app/service.py`、`backend/app/api/routes.py`；`frontend/lib/api/types.ts`、`frontend/lib/api/p3-types.ts`、`frontend/lib/api/client.ts`、`frontend/hooks/use-market-stream.ts`、`frontend/components/markets/markets-state.tsx`；相关 Vitest/API tests。

- 先测后端：所有 listing 名称来自真实 outcome labels；player_ids/match_id 缺失时仍有报价，但无 model action/link；page/page_size/total 对全 catalog 正确。
- 先测前端：第一页显示真实 total；Load more 追加无重复行直至 total；筛选作用于已加载 rows；quotes_changed 只重新取已加载 listings，不重取 opportunities/paper；错误保留最后可信数据。
- 增加 SSE decoder/event hook 对新的 invalidation 类型的严格判别；未知事件保持既有 fail-safe 行为。
- 改 UI 前读取本地 Next 指南；保持原布局，仅增加加载更多和必要计数/空态，禁止无关视觉改版。
- 运行相关 API/decoder/hooks/markets-page tests、typecheck、build。
- 已实现：后端分页返回供应商真实 outcome labels、真实 quote 与全目录 `total`；无球员身份的 listing 不生成 model action/link。前端严格解码 `quotes_changed`，独立序列不碰 market/decision cursor；显示已加载/总数；Load more 每页 50 条并按内部 market ID 去重；筛选只作用于已加载 rows；报价 SSE 仅重取已加载 listings 页，不刷新 opportunities/Paper，并以最多每秒一次合并持续事件。改 UI 前已读取 `frontend/AGENTS.md` 与 Next 16 本地 Client Components/data fetching 文档。
- 验证：前端 Vitest `410 passed`、TypeScript 和生产 build 成功；新增分页筛选 Playwright 用例已纳入 Task 7 完整 E2E。

### [x] 7. 端到端回归、真实只读核验与收口

**文件：** `frontend/e2e/` 对应 markets 场景、后端 `tests/integration/` 对应 catalog/quote stream；更新 `PROJECT.md`、`ROADMAP.md`、`CURRENT.md` 与 runbook。

- E2E：两页以上目录、未映射/双打真实名称展示、load more 后 total 覆盖；报价状态 no_liquidity/unavailable/stale 各自清楚；报价 SSE 后只刷新 listings；not_promoted 时机会仍为空且明示原因；P1/P2 和冻结视觉基线不变。
- 最终验证（2026-09-23）：后端确定性套件 `1223 passed, 122 deselected`；隔离 PostgreSQL reconciliation + query-service tests `19 passed`；前端 Vitest `410 passed`、TypeScript 成功、生产 build 成功；Playwright 功能 lane desktop/mobile `92 passed, 40 skipped, 0 failed`，视觉 lane `34 passed, 4 skipped, 0 failed`，批准截图零 diff。跳过项均受真实服务或 replay 显式 opt-in gate 控制。
- 只读公开 API smoke（无凭据、无原始 payload 输出）：Gamma tag 与首批 keyset 均 HTTP 200；首批 100 个 event 中发现 49 个开放 moneyline listing；CLOB `/time`、`/books` 均 HTTP 200，两个真实 outcome 都返回含报价盘口。官方 Realtime Data 文档确认 market WS 地址、每 10 秒应用心跳、`custom_feature_enabled` 下 `best_bid_ask`；此前已实测 824-token 当前目录订阅。
- 安全/范围审计：公共 API/服务/前端未出现 provider asset/token/condition/event 标识；`MarketOutcome.player_id` 与 strict MarketWorker roster 未放宽；P2 SSE 既有事件契约未改；closed catalog reconcile 保留 rules/links/quotes/ledger 历史；未跟踪用户文件与 `.env` 未改、未纳入提交。项目 app 保持关闭。
- Ruff 对相关修改文件的 lint 检查通过；格式检查中 3 个历史文件（`routes.py`、`service.py`、`test_p3_query_service.py`）原本就在 `origin/main` 上不满足 Ruff formatter，其他 24 个相关文件已格式化；未为本任务制造整文件无关重排。`git diff --check` 通过。
- 更新三份总控并提交/推送 T91 完成证据；只提交任务文件与已跟踪总控，不提交 `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。
- 更新三份总控并提交/推送 T91 完成证据；只提交任务文件与已跟踪总控，不提交 `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts`。

## 执行记录

- Pre-flight interfaces：Task 1 的 MarketListing/完整扫描供 Task 2 持久化与 reconcile；Task 2 的全量 external mapping 供 Task 3/4 取 token；Task 3 的 id-less quote projection 由 Task 4 共用；Task 4 的 feed health 与 coalesced quote updates 供 Task 5 SSE/API；Task 5 的 quotes_changed 事件由 Task 6 hook 消费；Task 6 完整分页由 Task 7 E2E 验证。当前代码与规格边界相符，无接口冲突。
- Ruling：工作区进度记录放在本实施计划内，不创建 `.superpowers/sdd/` ledger；项目指令明确保护现有未跟踪 `.superpowers/` 用户资料。代价：计划文件承担临时执行账本，收口后需保留简洁验证摘要。
- Ruling：在当前已领取的 main 任务执行，不新建 worktree；根目录 AGENTS.md 要求单一主任务在 main，且禁止未经批准的并行分支。代价：实现直接写入当前 checkout，需严格保护已有未跟踪文件并仅按任务范围提交。
- Task 1: complete — new `MarketListing` keeps supplier labels with optional internal identity; tag slug lookup plus bounded Gamma keyset pagination; cursor/page validation; complete/incomplete scan semantics; `list_tennis_moneylines()` remains a strict-only projection. RED: three keyset cases failed on missing method; GREEN: provider suite 24 passed; Ruff check/format passed.
- Task 2: complete — PostgreSQL transaction upserts all supplier-labeled listings, closes unseen open/scheduled rows only after a complete scan, never retires on incomplete scans, preserves resolved state and market-related history. Runtime strict mapping/rules work only from listings convertible to strict `Market`; unknown identities and doubles remain display-only. RED: runtime reconciliation test failed before daemon adoption; GREEN: three isolated PostgreSQL tests, 51 runtime tests, Ruff check/format all passed.
- Task 3: complete — id-less REST quotes are persisted in existing nullable outcome columns without `OutcomeBook` identities; all open/scheduled listings with private tokens become snapshot candidates; defaults cover 500 markets and batch 500 tokens; process-local round robin rotates the cap. RED/GREEN quote+config+snapshot/provider/runtime tests `222 passed`; isolated PostgreSQL reconciliation/id-less quote roundtrip `4 passed`; Ruff check/format passed. No migration.
- Task 4: complete — separate read-only broad market WebSocket, dynamic subscription, bounded quote coalescing, REST baseline/reconnect, PONG liveness and awaited shutdown.
- Task 5: complete — id-less realtime persistence/read path, truthful connection-health overlay, changed-only catalog/snapshot notifications and independent quotes_changed Redis/SSE invalidation.
- Task 6: complete — backend full-catalog pagination and truthful quote DTO; frontend page append, local filtering and independent quotes_changed invalidation; full unit/type/build coverage passed.
- Task 7: complete — final backend/integration/frontend suites, desktop+mobile functional and visual Playwright lanes, public Gamma/CLOB read-only smoke, provider-identifier and strict model/Paper boundary audits all recorded above. Implementation was committed and pushed as `784ccf8`; final control files close the task.
