# TennixAI 当前任务与交接

> 快速了解现在做到哪里、最近做完什么、接下来由谁接手。长期路线与阶段证据见 [ROADMAP.md](./ROADMAP.md)，产品定位和稳定架构见 [PROJECT.md](./PROJECT.md)。

**最后更新：** 2026-09-30 09:46（北京时间）

**当前主任务：** T119 — 只读调查隔夜启动失败原因（`in_progress`）；Codex / 本地 ADE / `main`，起始提交 `b2e27d9`；T118 启动仍 `blocked`。最近完成 T117 — 按批准示意图实施市场页前端改版（`done`）；完成提交 `ed6f6a7`，验收与实现说明见下方。T113 本地启动器备用端口验收仍 `blocked`，此前服务栈运行于 3100；本次实际应用均已停止，T118 启动被恢复健康门阻断。3101 回退场景仍待验证。T110 私人测试服务器部署仍 `blocked`。

**最近任务：** T117 — 按批准示意图实施市场页前端改版（`done`，实现 `ed6f6a7`）；T116 — 市场页信息层级与扫读体验设计（`done`，设计 `7a15254`）；T115 — 修复比赛详情页预测快照持久化与市场/GAP 展示（`done`，实现 `1d6e4d4`）；T114 — 调查比赛详情页预测模型数据未显示（`done`）；T113 — 本地启动器前端备用端口与真实运行验收（`blocked`，实现 `ea1d760`）。

**最近执行者 / ADE / 分支：** Codex / 本地 ADE / `main`；T118 从 `3f41bc6` 开始，领取 `591b4ef`，当前启动受恢复错误阻塞；T117 从 `c276bb0` 开始，2026-09-29 21:36 CST 领取，代码完成提交 `ed6f6a7`；截至收口前已 fetch `origin/main` 并确认基线一致。T116 从 `98aada0` 开始，设计 `7a15254`；T115 领取 `30ea130`、实现 `1d6e4d4`。已知用户工作区改动全部保留且不纳入任务提交。

**运行手册与证据：** [本地真实运行手册](docs/runbooks/local-real-runtime.md)。

## T119 只读调查隔夜启动失败原因（`in_progress`）

- **领取：** 2026-09-30 09:46 CST；Codex / 本地 ADE / `main`；起始提交 `b2e27d9`。用户要求先探查为何昨天能启动、今天失败。
- **范围：** 读取代码/Git/持久化健康/数据库聚合与必要的有界只读 provider 请求，定位 `NOT_FOUND` 的具体对象和恢复传播路径；不修复产品代码、不改根 `.env`、不启停服务、不写运行数据、不调用 LLM。已有用户工作区修改全部保留。

## T118 启动本地真实项目（`blocked`）

- **授权与领取：** 用户要求“启动项目”；Codex / 本地 ADE / `main`；起始提交 `3f41bc6`；2026-09-30 09:04 CST。
- **核对：** 已 fetch；本地与 `origin/main` 同步。已有用户改动全部在保护清单内，保留且不提交。实际 `status` 为 stack stopped、PostgreSQL/Redis absent、三个子进程 stopped；修正此前服务仍运行的记录。
- **范围与验收：** 使用 `./scripts/tennix-live up/status` 启动既有本地栈，检查 API 与首页 HTTP；保留数据库和 Paper 数据，不改产品代码或根 `.env`，不主动执行 LLM 核验。
- **实际操作与证据：** 领取 `591b4ef` 已推送。首次 Compose 失败原因是 Colima 未运行；启动 Colima 后依赖健康，但 OS 临时 launcher 初始化标记已丢失，`up` 返回 `LOCAL_NOT_INITIALIZED`。依据 T113 已保存的完整初始化批准执行幂等 `init`，成功返回 `revision=0009 players=3989 matches=529`，含实际 LLM 中文名补齐；未改根 `.env`，未重置数据，未发生 schema 升级。
- **启动阻塞：** 初始化后两次受支持 `up` 都以 `LOCAL_RUNTIME_UNHEALTHY` 失败（180 秒首次健康门未通过）；第二次持久健康源明确记录 `recovery=degraded/NOT_FOUND`、`daemon_tick=degraded/NOT_FOUND`，sports/Polymarket 为 `gap/STARTUP_RECOVERY`。日志为空，当前证据不能确定具体缺失对象。最终 `status`：PostgreSQL/Redis healthy；runtime 已被启动器停止，API/frontend 未启动。未通过 HTTP/浏览器验收。
- **交接：** 需定位并修复恢复阶段 `NOT_FOUND` 后再执行 `up`；不绕过健康门、不手工单独启动服务、不删除旧链接或账本来掩盖错误。Colima 启动自动恢复的其他项目容器未触碰，已有用户改动全部保留。

## T116 市场页信息层级与扫读体验设计（`done`）

- **领取：** 2026-09-29 18:14 CST；Codex / 本地 ADE / `main`；任务起始提交 `98aada0`。
- **用户目标：** 先交付 `/markets` 前端优化方案与设计，优先让信息更清晰、扫读更快。用户明确要求下一步再单独指示实施，因此本任务不修改产品前端。
- **范围：** 基于当前生产页、双视口视觉基线和现有组件，设计三视图的信息层级、市场行、筛选、空态/延迟态与响应式规则；保留真实报价、未晋升模型、未匹配市场和 Paper 模拟语义。
- **验收：** 提交可审阅的设计规格，写明桌面/手机布局、状态矩阵、边界和未来实施验收条件；检查文档链接、范围与 `git diff --check`。不声称产品测试或视觉回归通过。
- **现场保护：** `backend/app/service.py` 及既有未跟踪文件保留；根 `.env`、运行中服务、数据库和前端代码均不触碰。
- **完成：** [市场页信息层级与扫读体验设计](docs/superpowers/specs/2026-09-29-tennixai-t116-markets-readability-design.md) 已提交为 `7a15254`。包含现有三视图优化与两种备选的取舍、桌面/手机线框、内容优先级、报价与 Paper 状态矩阵、响应式/无障碍规则和未来实施边界。用户尚未批准实施。
- **实际验证：** 文档两个相对链接目标存在；只暂存设计文档后 `git diff --cached --check` 通过，暂存清单只有设计文档。未运行产品测试、TypeScript、Playwright 或视觉回归；生产前端未改动。

## T117 按批准示意图实施市场页前端改版（`done`）

- **领取：** 2026-09-29 21:36 CST；Codex / 本地 ADE / `main`；任务起始提交 `c276bb0`。
- **用户授权：** 用户明确要求“那就按照这个示意图来”，并强调前端应与示意图一致；随后说明页面背景不用改成深墨绿色。按此保留全站原背景，将示意图的深绿用于报价卡片。
- **规格与计划：** [T116 设计稿](docs/superpowers/specs/2026-09-29-tennixai-t116-markets-readability-design.md)；[T117 实施计划](docs/superpowers/plans/2026-09-29-tennixai-t117-markets-redesign-implementation.md)。
- **实现：** 生产 `/markets` 采用示意图的紧凑标题、下划线式三视图导航、筛选优先顺序、双方并列真实报价卡及状态/次要指标区；移动端筛选可折叠，长名称换行。机会与 Paper 行在桌面断点才切换多列，手机菜单与机会空态按钮达到 44px。保留 API、URL、分页、模型及 Paper 语义；冻结 `?preview=p3` 未改。
- **完成提交：** `ed6f6a7`（前端、回归与实施计划）。
- **验证：** focused Vitest `3 files / 38 passed`；`tsc --noEmit`、`git diff --check` 通过。真实 `/markets?view=all` 在 375/390/768/1024/1440px 做了视觉检查，手机筛选选择/重置与 URL 同步通过；未改视觉基线。独立审查的三项问题已由新增测试先 RED 后 GREEN。
- **限制：** 针对性 Playwright 尝试因 Chromium `bootstrap_check_in` 在沙盒中被拒绝而无法启动；运行时没有 Paper 行/机会数据用于实际绘制这两类行，相关断点由组件回归覆盖。该任务没有声称自动 E2E 通过。
- **现场保护：** 根 `.env`、`.next`、数据库和运行服务未触碰；所有已有用户工作区改动均保留且未纳入提交。

## T113 本地启动器前端备用端口（`blocked`）

- **领取与实现：** 初次领取于 2026-09-28 17:54 CST；Codex / 本地 ADE / `main`；起始 HEAD `2835e19`；领取 `7d5d325`；代码、回归与手册 `ea1d760`。用户批准初始化后于 2026-09-28 18:10 CST 恢复执行；恢复基线 `88c4281`。
- **实现与边界：** `tennix-live up` 优先使用 3100，若被其他进程占用则使用 3101，并打印实际地址；两个端口均被占用时安全拒绝，不向外部进程发送信号。用户已批准此行为。3100 当前由另一 ADE 的 Vite 预览占用，未停止该进程。
- **代码验证：** 新增端口选择回归先按预期失败，再通过；启动器 `63 passed`，完整后端确定性套件 `1379 passed, 131 deselected`，改动文件 Ruff lint/format 与 `git diff --check` 通过。
- **已批准恢复：** 用户于 2026-09-28 明确批准现在开始完整初始化。按运行手册执行唯一受支持的 `./scripts/tennix-live init`；它会迁移专用本地 schema、同步赛程/排名与目录，并可能批量调用 LLM 补齐中文名。此前 schema 为 `0008`，T112 要求 `0009`；不手工绕过启动器迁移，不清空数据库或 Paper ledger。
- **运行验收节点（2026-09-28 18:27 CST）：** 获批的 `init` 成功，数据库迁移到 `0009`，同步摘要 `players=3979 matches=281`。`up` 因 180 秒内未达到必需的首次健康发现而返回 `LOCAL_RUNTIME_UNHEALTHY`；按启动器保护逻辑仅停止本次 Tennix runtime，API/frontend 未启动。失败后 `status` 确认 PostgreSQL/Redis healthy、Tennix 子进程均停止；3100 的其他 ADE 未触碰。
- **运行验收节点（2026-09-29 北京时间）：** `./scripts/tennix-live verify`：`6 passed / 2 skipped / 0 failed`（跳过项为无活跃映射盘口的 WebSocket 与未请求 LLM）；TLS 正常，未绕过验证。用户要求启动后 `./scripts/tennix-live up` 成功；状态为 stack running，runtime/API/frontend 均运行，数据库与 Redis healthy（external）；sports stream、schedule、rankings、Polymarket 均 `ok`，paper 为 `paper_only`、模型 `not_promoted`。实际前端地址 `http://127.0.0.1:3100`；`/api/v1/health` 返回 200，首页返回 Tennix 标题。服务保持运行。
- **根因证据：** 不调用 LLM 的只读 `verify` 为 3 passed（API-Tennis 排名、赛程目录、网球 WebSocket）、4 skipped（无已映射/活跃盘口，LLM 未请求）、1 failed（Polymarket `market_discovery: PROVIDER_UNAVAILABLE`）。匿名只读 TLS 探测中，Gamma `/tags/slug/tennis` 和 CLOB `/time` 均返回 curl error 60 / TLS verify result 18：证书为自签名、当前信任链无法验证。故障发生于 HTTPS 证书验证，不是 API key、无 live 比赛或市场匹配空结果；尚不能断言是 IP 封锁。没有关闭 TLS 校验。
- **阻塞与下一步：** TLS 阻塞已解除，完整栈现运行于 3100。剩余验收仅为 3100 被其他 ADE 占用时的 3101 实测；本次启动时端口空闲，因此没有占用或停止其他进程来人为制造冲突。保留 TLS 校验，不跳过市场首次发现健康门，不手工单独启动 API/frontend。3101 场景可在实际有其他 ADE 使用 3100 时通过受支持的 `up` 验证。
- **边界：** 根 `.env` 仅由启动器读取，不输出凭据；不终止 3100 的其他 ADE 进程，不删除或重置运行数据，不改变市场模型晋升或 paper-only 边界；所有已有用户工作区改动继续保留且不纳入提交。

## T115 修复比赛详情页预测快照持久化与市场/GAP 展示（`done`）

- **领取与完成：** 2026-09-29；Codex / 本地 ADE / `main`；起始 HEAD `349b31d`；领取记录 `30ea130`；实现 `1d6e4d4`。用户明确要求修复 T114 调查结论中的后三项。
- **目标：** 让现有预测快照读写链连通；市场 $10 可执行均价不可得时，仍诚实呈现已有双边盘口参考价；修正 `GAP` 和 `NO_BET` 的误导性文案。
- **已确认路径：** `DecisionWorker` 注入的 `MarketRepository` 已实现 `save_prediction()`；Match 决策查询从该仓库读取最新预测。决策 DTO 已带双方 `best_bid/best_ask`，前端 Match 页也有现成的 outcome/player 映射。无须数据库迁移或新增 API 字段。
- **改动：** `DecisionWorker` 在取得非空预测快照后调用现有幂等 `save_prediction()`，接通详情页预测读写链。$10 可执行均价为空时，工作台显示 DTO 中双方盘口最佳可买入参考价；有持仓时只显示持仓方最佳可卖出参考价，并明确说明单档参考价不代表 $10 可成交均价。GAP 文案改为“实时数据更新中断”，避免推断断流来源；`NO_BET` 标题改为中性表述，具体阻断原因继续由 reason 展示。
- **边界：** 规则/stale/gap 对新模拟动作的安全门未变；模型未晋级时仍不提供胜率。没有新增 API 字段、数据库迁移或供应商/LLM 请求，也未重启运行栈。既有 worker 测试替身已补 `save_prediction()` 接口。
- **验证：** `frontend/node_modules/.bin/tsc --noEmit` 通过；后端 `worker.py` Python AST 语法解析通过；`git diff --check` 通过。未运行测试。`pnpm run typecheck` 因 pnpm 尝试清理 modules 目录并要求交互确认而中止，之后直接运行本地 TypeScript 编译器成功；清理了该失败调用生成的空 `.pnpm-store`。既有用户工作区改动保留且未纳入提交。

## T114 比赛详情页预测模型数据未显示调查（`done`）

- **领取与范围：** 2026-09-29；Codex / 本地 ADE / `main`；起始 HEAD `f61486f`，领取记录 `0ddde48`。按用户请求只调查、不修复产品代码。
- **复现对象：** 浏览器比赛详情 `mat_4c0f46acce4c472185587afb8613ae0d`（WTA Beijing 决赛，Marina Bassols Ribera 对 Xiaodi You）；截图 URL 与现有 Chrome 页面对应同一 match ID。
- **结论：** 当前部署健康快照 `model_status=not_promoted`。`PredictionService` 未加载已晋升产物时对所有比赛弃权并返回空 `outcomes`，因此没有模型胜率是当前安全设计的直接结果。另发现生产链路缺口：`DecisionWorker` 仅在内存保留 prediction 并持久化 decision observation；仓库虽实现 `save_prediction()`，全仓无调用点；详情查询却从独立 prediction 表读取 `latest_prediction()`。本场 REST 决策快照因此同时返回 `model_probabilities=null`、`model_availability=null`、`data_version=null`。即使日后加载已晋升模型，这条读写链未接通也会令工作台拿不到模型预测数据。
- **其他空值与红色状态：** 本场 decision `reason_code=RULES_UNAVAILABLE`；规则硬门先于模型/报价决策，故 `quote_average_price=null`。同一响应仍有两边盘口档位（0.65/0.66 与 0.34/0.35），页面走势也显示 66%/35%；空的是 $10 可执行均价，非所有市场报价都缺失。`has_gap=true` 来自运行时同时检查 tennis 与 Polymarket 两条源；健康快照中 `tennis_live=ok`、`polymarket=gap/CONNECTION_LOST`，所以比赛分数流不是该 gap 来源。前端却把所有 `has_gap` 显示成“比赛数据更新中断”。
- **展示层问题：** 服务端当前动作是 `no_bet`、原因是规则未确认，但前端对任意 `no_bet` 都使用“模型与市场价格差距不明显”标题和“扣除成本后差距不明显”描述，和本场的真实阻断原因不符。
- **运行时证据：** 2026-09-29 06:30 UTC 只读 `GET /api/v1/runtime/health` 返回 200；同一时段后端与 Next 代理的 `GET /api/v1/matches/{id}/decision` 均返回 200 且内容一致，`as_of=06:30:09Z`。健康快照模型未晋升、Polymarket 决策流 gap；比赛详情 DOM 同时展示新鲜比分/统计与 66%/35% 买入价。未发起供应商/LLM 请求。
- **代码证据：** `PredictionService.predict()` 在缺少 artifact 时通过 `_abstain()` 产出空 outcomes；`DecisionWorker._decide()` 写 decision observation，但未调用 `save_prediction()`；`P3QueryService.match_decision()` 通过独立 `latest_prediction()` 生成 nullable model fields；规则门先于 model 和 quote 估算；`RuntimeHealthRegistry.freshness_for()` 对已映射市场同时检查 `tennis_live` 与 `polymarket`，前端将合并后的 `has_gap` 固定映射成比赛数据中断文案。
- **安全与验证边界：** 未读取/输出根 `.env`，未触发供应商或 LLM 请求，未重启服务、未读写数据库、未修改产品代码、未新增或运行测试。完成记录提交包含本段调查结果。

## T112 修复 Polymarket 市场规则链路（`done`）

- **领取与提交：** Codex / 本地 ADE / `main`；起始提交 `5d31ba0`；领取记录 `6be5fae`；实现与回归 `6b7de72`，已推送至 `origin/main`。
- **完成内容：** 从 Gamma market `description` 与 `resolutionSource` 读取规则，不再读取不存在的 `rules` 或把 `resolvedBy` 当来源；随网球目录扫描一次性带回，严格匹配到内部比赛后保存，规则文本和来源共同用于识别变化。规则历史按时间保存，即使从 A 改为 B 再改回 A，也记录为三个版本。决策只认最近一次完整且未过期的扫描；扫描失败、不完整、过期、规则缺失或发生变化时，暂停新的模拟买入/退出，但市场名称和报价仍照常展示。当前还不能自动判断规则变化是否影响赛果，因此发现任何新版本都会持续暂停操作，不猜测新旧规则等价；同时移除了缺少规则时伪造的 `unfrozen` 标记。前端新增普通用户可读的规则缺失说明。
- **验证：** TDD 覆盖 Gamma 真实字段形状、来源单独变化、缺失规则、单次扫描请求量、A→B→A、同 hash 刷新、完整/失败/过期扫描、缺失/变更规则门、Paper 拒绝无 hash intent。后端非外部服务/基础设施确定性套件 `1377 passed, 131 deselected`；前端 Vitest `41 files / 536 passed`、`tsc --noEmit` 通过；改动 Python 文件 Ruff lint 通过，10 个新增/重点文件 Ruff format 检查通过；`git diff --check` 通过。隔离数据库迁移 `0001→0009` 成功，规则持久化集成 `3 passed, 6 deselected`，验证 A→B→A 后降级被安全拒绝，临时测试库已删除；共享运行库未迁移/重置。
- **外部核验限制与运行状态：** 官方 Gamma [keyset 文档](https://docs.polymarket.com/api-reference/events/list-events-keyset-pagination)、[market 文档](https://docs.polymarket.com/api-reference/markets/get-market-by-id)、[规则澄清说明](https://help.polymarket.com/en/articles/13364548-how-are-markets-clarified)及一个官网市场 Rules 页面已检查；但当前网络对 Gamma API 主机返回不受信任的 TLS 证书，实时 API payload 与网页 Rules 文本的逐字比对未完成，也没有关闭 TLS 校验。没有迁移共享运行库、重启服务、启用模型或调用订单接口；根 `.env` 未读取/更改。重新运行服务前需要先按日常流程应用 migration 0009。
- **工作区保护：** `backend/app/service.py`、`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 均为任务外已有用户改动，未暂存或提交。

## T111 修复比赛阶段统一显示为 Semi-finals（`done`）

- **领取：** Codex / 本地 ADE / `main`；起始提交 `49a48b6`，领取记录 `e2903d7`。
- **根因：** API-Tennis `get_fixtures` 的 `tournament_round` 被 provider 直接写入 canonical `Match.round`，前端又直接显示该值。对当前赛程的只读核对发现不同场次均收到 `Semi-finals`；同赛事 `get_draw` 响应以相同 `match_key` 标注为 `Qualifying Round 1`。Git 历史显示近期只增加了去空格，并未改变轮次语义映射。官方接口文档确认 `get_draw` 提供轮次、签表和比赛 `match_key`，并可包含资格赛：[API-Tennis 官方文档](https://api-tennis.com/documentation)。
- **修复：** 仅当供应商轮次标为半决赛时，按赛事/赛季读取一次 `get_draw`，用完全相同且唯一的 `match_key` 校正轮次；缺失、冲突或不可用时保留原供应商值，不做猜测。赛事签表缓存 6 小时、空签表缓存 15 分钟、过期数据最多容忍 24 小时；失败后 15 分钟内不重复请求。覆盖赛程、直播、比赛详情和比分快照；不改 UI、schema、其他字段或市场/Paper 语义。
- **验证：** 新回归先 RED、后 GREEN，覆盖资格赛校正、严格按比赛 ID 匹配、签表缓存、比赛详情/快照复用、live 轮次及签表 API 不可用时安全回退。Provider 测试 `96 passed`；后端非 integration/live 确定性测试 `1366 passed`；前端轮次 view-model 测试 `66 passed`；`git diff --check` 通过。全量后端 pytest 运行约 80 秒后人工中断：已完成 18 项、10 个数据库集成用例因本机测试库缺少 `match_state_snapshots.freshness` 列失败，其余尚未执行；未迁移、重置或改动数据库。未重启现有真实服务，所以修复代码会在下次安全重启/重载后进入运行中的 API；未读取或输出凭据。
- **提交：** 实现与回归 `84a344e`。既有用户工作区改动均保留，未纳入本任务。

## T110 私人测试服务器 Docker 镜像部署（`blocked`；显式交接暂停）

- **状态交接：** 用户于 2026-09-28 优先要求修复 T111，因此暂停 T110；T111 已完成，T110 仍为唯一未完成但受阻任务。T110 的只读预检和原始授权继续保留，用户补齐阻塞决策后再显式接续。

- **用户授权：** 为 amd64 服务器构建镜像、部署 TennixAI，并在部署后执行真实 `init` 与 API 运行；目标 `8.134.76.110`。本机 Docker Buildx 已确认支持 `linux/amd64`。
- **只读预检：** 服务器为 Ubuntu 24.04 / amd64，Docker Engine 与 Compose 已安装；`/opt/tennixai` 不存在，Docker 当前无容器、镜像或数据卷。现有 DEUCE/Nginx 监听 80/443/8080，DEUCE API 使用 `127.0.0.1:8000`；服务器本机没有 3100 监听。Nginx 是 catch-all，现有 IP 证书为自签名，无法作为浏览器可信 HTTPS 入口。不得覆盖/停止既有站点或服务。
- **容量与访问阻塞：** 系统盘 40GB、可用空间为 0；`/tmp` 约 9.5GB 来自 4070 个旧 `heavy-radar-*` 目录，均属 `deuce:deuce`，无匹配运行进程/打开文件；未删除。内存 1.6GiB、当前可用约 728MiB、另有 2GiB swap；本地实测 runtime RSS 约 535MiB、Next 生产风格服务尚未实测，部署后内存余量可能不足。UFW inactive；应用无登录认证，不能假设公开端口只给好友使用。外部探测 3100 得到空响应，与服务器本机无监听的结果不一致，网络边缘状态待部署后验证。
- **未执行事项：** 未安装镜像、创建部署目录/数据卷、修改 Nginx/防火墙、读取/复制 `.env` 值或运行远端 `init`。本地根 `.env` 的 provider/LLM/Paper 模式及必需密钥字段已只检查存在性，值未显示或写入文档。
- **待决条件：** 扩容系统盘或明确授权清理上述精确临时目录；确定好友访问限制方式。未获决定前不删除 DEUCE 数据、不开放公网端口、不进行远端写入。整体 Compose 方案已提出，等待用户确认。
- **保留的用户工作区改动：** `backend/app/service.py`、`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 均已原样保留，未纳入 T110 或 T111 提交。

## T109 比赛详情记分牌视觉复刻（`done`）

- **用户授权：** 以仓库内的[已批准示意图](docs/superpowers/specs/2026-09-27-tennixai-t109-scoreboard-reference.png)为视觉目标，去掉可见“本局”标题。首版浏览器复核后，用户要求缩小头图比例并移除下方重复比分卡；第二次复核后，再要求将桌面字体稍微缩小。
- **完成内容：** 实现 `db3b156` 复刻紧凑单张记分牌，移除下方重复比分卡，收紧桌面字号与头图比例，压平 P3 网格空白。只读审阅指出五盘窄屏双位局分/抢七可能串列、已完赛但无已知盘分时缺少说明；`ed9789a` 为五盘增加宽度和紧凑抢七小分、补“最终比分暂未提供”及胜者保留，并去掉无 paper 持仓时的空网格行。比赛事实、数据接口、模型及 paper 语义未改。
- **验证与真实运行：** 审阅修补的定向回归先红后绿；最终前端 Vitest `41 files / 534 passed`、`tsc --noEmit`、P3 工作台 Playwright `29 passed / 1 skipped`、修补后 Match 视觉基线桌面/手机 `4 passed`、`git diff --check` 通过。运行手册 `tennix-live verify` 实际结果 `7 passed / 1 skipped（未请求 LLM）`；获用户授权后 `down`→`up`，未执行 `init`、未清数据卷或 paper ledger。重启后真实运行浏览器验收桌面/手机 `6 passed`，首页与 API HTTP 200，数据库/Redis 健康，runtime/API/frontend 均运行，比分流、赛程、排名、Polymarket 均 `ok`。浏览器实查真实直播赛场 `/matches/mat_ab9657dd950440408f3400e9daa3aaae`：单张头图展示双方真实姓名、逐盘比分、抢七小分、当前局分和发球方，无重复比分卡。实现与审阅修补提交分别为 `db3b156`、`ed9789a`；本次总控提交关闭任务。
- **工作区保护：** `backend/app/service.py`、`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 为已记录的用户现有改动，仅保留，不纳入提交。

## T108 比赛详情页比分头图区精简改版（`done`）

- **领取与完成：** 2026-09-26 16:00 CST 领取；Codex / `main`；起始 HEAD `89780e3`。领取记录 `1667e1b`，实现与回归 `ffdabce`。
- **已批准设计：** 将比赛头图区合并为一张记分牌。每位球员只出现一次：照片、英文主名/中文辅名、国旗和排名，与逐盘/当前局比分同列；球员姓名可换行。顶部只保留赛事/轮次/场地、比赛状态与更新时间。发球标记只放在实际发球球员行；未知发球方只提示一次。赛前展示开赛时间，完赛只标一次胜者；移除重复对阵标题、二次头像/姓名/排名及比分复述。页面下方的详细比分保持现有能力。
- **完成内容：** `match-hero.tsx` 改为一张紧凑记分牌：球员照片、英文主名/中文辅名、国旗/排名与单打比分在同一行；live 只在发球者一行标记并把当前局分放进表格；finished 在获胜者行标记胜者，抢七分作为次级信息；upcoming/unavailable 只列一次双方和开赛信息。顶部仅保留赛事上下文、状态、更新时间；删除重复对阵标题、头像/姓名/排名、比分复述和多余数据状态文案。下方详情区及数据链路未改。
- **边界：** 只改比赛页展示，不改 canonical 数据、实时更新、服务端/API、P3 市场/决策/Paper 语义；保留既有演示与真实页面行为。
- **验证：** 前端 Vitest `41 files / 533 passed`、`tsc --noEmit` 通过；Playwright `p1-preview-finished` 视觉检查桌面与 390px 手机均 `2 passed`，更新了对应截图基线。运行中真实比赛页桌面浏览器核验通过；真实五盘完赛页以 390px 全页截图检查，长姓名及抢七盘分可读、无横向溢出。`git diff --cached --check` 通过。未运行全量浏览器套件：现存 `p1-match-live` 视觉用例等待固定“暂未提供技术统计”文案，与当前真实比赛已返回技术统计的页面状态不符；该用例未作为本任务通过证据。没有修改/重启后端、真实服务或 `.env`。
- **工作区保护：** `backend/app/service.py`、`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 均是 T108 前已有用户修改，不纳入本任务。

## T107 比赛详情近期得分走势图可读性改版（`done`）

- **领取：** 2026-09-26 14:35 CST；Codex / `main`；起始 HEAD `c72e454`。本任务是已有 Match 走势卡的局部改版，不更改 Recent Control 算法、供应商、API、数据库、市场或 Paper。
- **目标：** 普通用户能一眼看懂近期走势偏向哪位球员、何时越过零线转向，以及指数不是胜率。英文主名、中文辅名规则继续生效。
- **已批准设计：** 首屏以人话结论为主、指数为辅；图上固定两位球员对应的正负方向，0 为相对均衡；横轴解释为第几分，交互提示展示已确认的逐分事实；未知得分造成的序列缺口不能用连续实线覆盖。少于 6 个可确认得分不下偏向结论，无数据则显示诚实空态。移除无信息量的“走势已更新”，保留最近记录时间及“不是胜率”说明。
- **实施计划：** ① 先补视图映射和卡片失败回归，覆盖正负方向、零值、20 条窗口、未知得分缺口、样本不足和无数据；② 最小改动 `frontend/lib/view-models.ts` 与 `frontend/components/match/match-momentum.tsx`，复用现有 Recharts、PlayerName 与主题；③ 跑前端全量 Vitest、TypeScript、受影响浏览器/双视口视觉与差异检查。若共享运行栈或用户未提交文件阻碍构建/浏览器门，如实记录，不覆盖现场。
- **完成提交：** 领取 `4389aa1`；前端实现与回归 `3ce6f41`；复审边界修补 `ddbfb01`、长姓名换行 `bd33d78`。主结论、双球员正负方向、零线、得分序号、逐分悬浮说明与双语姓名已落地；未知得分与未生成的观测不连线、不计入已确认样本。较新未知得分会显示走势停留位置；零附近指数、同姓球员、得分者身份异常、少于 6 分及无数据有专门处理。
- **验证：** TDD 定向回归先红后绿；最终前端 Vitest `41 files / 533 passed`、`tsc --noEmit`、`git diff --check` 通过。复用已运行的本地真实 Next/API 服务，在桌面及 390px 手机页检查标题、双方全名、零线、完整横轴刻度和缺口点；点击观测可见序号、指数、得分者；手机页面宽度未溢出。未运行会改动共享 `.next` 的 production build 或隔离 Playwright 套件；真实页面手工验收覆盖本卡主要路径，边界数据由确定性测试覆盖。没有修改或重启 backend；未读取/输出根 `.env`。
- **复审：** 独立只读审查无 Critical；指出尾部未知得分、孤立观测隐藏、非本场得分者、同姓姓名及微小指数舍入等问题，已逐项修补并通过上述回归。保留既有 Recent Control 算法/供应商/API/P3 语义。
- **工作区保护：** `backend/app/service.py`、`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 均属既有未提交改动；只读或保留，不纳入 T107 提交。

## T106 比赛详情逐分记录中未知得分者的诚实展示（`done`）

- **领取/完成：** 2026-09-26 11:53 CST 领取，12:16 CST 完成；Codex，`main`，起始 HEAD `b6ec415`；领取记录 `919281f`，实现提交 `f7ea297`。
- **根因：** API-Tennis 没有直接的逐分 winner 字段。后端只在比分变化可确定时填充 winner；无法判断时保留 null 和 `winner_indeterminate`。比赛详情把每个 null 都展示为“胜者待定”，把历史数据不确定误说成尚未发生并重复刷屏。
- **实现：** 对 null 或无法映射到本场两名球员的 winner，逐分行显示横线，并给屏幕阅读器保留“得分者未能确认”；整段时间线只显示一次“部分逐分记录无法确认得分者”。已知球员、比分、顺序、分组、关键分及后端推断保持不变；字段完整性矩阵已同步更新。
- **验证：** 本地规范快照样本 129 条逐分记录中 25 条无法确认得分者；新增回归在旧页面先红（多个重复“胜者待定”），修复后绿。前端 Vitest `41 files / 524 passed`、`tsc --noEmit`、`git diff --check` 通过。没有运行 build/Playwright 或浏览器新构建验收：本地整栈仍运行，工作区含未提交的 P3 backend 修改；为避免触碰 `.next` 或重启加载用户修改，没有重建/重启。未读取/输出 `.env`，无上游请求。
- **工作区保护：** 既有 `backend/app/service.py` 修改及 `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 均保留且未纳入 T106 提交。
- **规格/计划：** [T106 设计规格](docs/superpowers/specs/2026-09-26-tennixai-t106-point-winner-clarity-design.md)；[T106 实施计划](docs/superpowers/plans/2026-09-26-tennixai-t106-point-winner-clarity-implementation.md)。

## T105 全站球员英文主名/中文辅名统一（`done`）

- **领取/完成：** 2026-09-26 10:25 CST 领取，Codex，`main`，起始 HEAD `b0f386b`；领取提交 `c15b061`。实现提交 `991b9f0`、`a44fc6e`。
- **目标：** 全站所有结构化球员身份显示统一采用英文主名、中文辅名；中文名缺失时只显示英文。
- **已确认边界：** Home、Match、Markets/Opportunities/Paper、Players、排名/搜索/资料/赛果和助手结构化球员卡均覆盖；AI 自然语言回答不强制插入双语。未知市场球员继续显示供应商 outcome 名称，不猜中文翻译。模型、比赛/市场/Paper 事实与身份解析不变。
- **完成内容：** canonical `Player.name` 与 P3 `player_names` 作为英文主名，新增顺序对应的可空 `player_localized_names`。共享 `PlayerName` 贯通 Home、Match、Markets/Opportunities/Paper、Players 排名/搜索/资料/赛果及 P3 图表；中文缺失时仅显示英文，未知市场 outcome 不猜译。比分、身份解析、AI 自然语言、模型/市场/Paper 语义未改。
- **验证：** 后端定向 API/集成测试 `16 passed`；前端 Vitest `41 files / 523 passed`、`tsc --noEmit` 通过；Playwright 桌面/手机视觉回归 `22 passed / 4 skipped`（P2 Replay 视觉用例按 opt-in 配置跳过）；审阅后更新 60 张视觉基线；`git diff --check` 通过。首次 Playwright 运行因隔离后端缺少 Redis、并错误连到旧 `tennix` schema 而中止；没有迁移旧库，最终视觉套件改用已有 schema `0008` 的 `tennix_live_local` 并通过。
- **真实服务：** 用户授权后执行 `./scripts/tennix-live up`，exit 0；API 与前端 HTTP 200，数据库/Redis healthy，runtime/API/frontend 均运行。首轮同步完成后的最终 `status` 中 sports stream、schedule、rankings、Polymarket 均为 `ok`。未执行 `init`，未重置数据库。
- **规格/计划：** [T105 设计规格](docs/superpowers/specs/2026-09-26-tennixai-t105-global-bilingual-player-names-design.md)；[T105 实施计划](docs/superpowers/plans/2026-09-26-tennixai-t105-global-bilingual-player-names-implementation.md)。
- **工作区保护：** `backend/app/service.py` 有用户已有 P3 freshness 修改；`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 均保留且不纳入 T105 提交。根 `.env` 未手动检查或输出；Playwright 使用既有配置加载流程，任何凭据均未打印或提交。

## T101 修复过期比赛误入当前列表（`done`）

- **领取：** 2026-09-25 21:22 CST，Codex，`main`，起始 HEAD `5af1b49`；用户已授权修复并要求复核方案。
- **目标：** 当前直播和近期赛程只展示可确认的有效比赛，首页与比赛列表/问答使用一致的时间语义；多日赛程注明北京日期。
- **边界：** 保留历史 canonical 行，不根据时间推定最终赛果；不变更供应商、数据库 schema、市场、模型或 paper。先做确定性回归，再用运行中的本地真实服务复核；不读取或输出根 `.env`。
- **现场保护：** `backend/app/service.py` 中 P3QueryService 的两处用户已有修改及 `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 均不纳入本任务提交。
- **实现：** `2b6e217`。当前直播按最后观测时间限制为 5 倍同步间隔、近期赛程为 3 倍同步间隔且必须有未来开赛时间；使用真实 `age_seconds/is_stale`，配置变更时窗口随同步间隔变化。过滤放在共用 TennisService 读取处，覆盖 Home、目录、列表、球员当前比赛和 Chat，不删除历史行、不推断结束比分。Home 将多日赛程命名为「近期赛程」，展示北京日期与时间，并修正空态和旧市场浏览器验收文案。
- **验证：** 目录/Chat/首页回归先红后绿；后端非 integration 测试文件 `1334 passed`，前端 Vitest `36 files / 485 passed`、TypeScript 与 Next production build 通过；真实本地桌面/手机 Playwright `6 passed`。重启后状态为数据库/Redis healthy，sports stream、schedule、rankings、Polymarket 均 `ok`，runtime/API/frontend 运行中；真实 Home 从旧的默认 44 场直播/186 场赛程收敛为 3 场有效直播/17 场未来赛程，页面核对显示北京日期。包含旧 integration 库的粗跑为 `1409 passed / 16 failed / 12 skipped / 25 deselected`，16 例因本机旧测试库 schema 缺列/约束不符，未把这次运行声称为全绿；未修改或重置该测试库。用户既有 P3 代码与未跟踪文件保留，根 `.env` 未输出或提交；真实服务继续运行。

## T102 逐字段走查并修复球员详情页（`done`）

- **领取：** 2026-09-25 22:04 CST，Codex，`main`，起始 HEAD `5c8e998`。
- **目标：** 对 `/players/ply_44ff6e422d48462aa51b5a06b8d72fdc` 的真实页面逐字段核对数据来源、API 响应、转换和呈现，修复确认的问题，并验证同一路径上的筛选、分页和桌面/手机视口。
- **范围：** 英文/中文名、赛事属性、国籍/旗帜、生日/年龄、排名/积分/变化/时间、赛季摘要、当前比赛、历史记录筛选与表格各字段、空值/错误态。根据证据区分上游未提供与本地映射/展示错误；不推测真实数据，不增加供应商能力。
- **已确认的数据规则：** 完整的 API-Tennis 赛季统计优先显示。供应商没有给出完整统计时，只从本地已记录、可验证的单打赛果计算场数、胜负和胜率，并在对应指标上单独标注来源；不推算冠军数或场地胜负。当前赛果若关键日期、参赛球员或胜者缺失，则不派生摘要；没有可靠指标时隐藏整块摘要。历史比分不补造空值；对手姓名、中文名和国籍由现有 canonical 球员目录补齐，不增加供应商请求。
- **已完成修复：** 比赛摘要与逐场赛果分开；可用局分标为“部分局分”，不再出现空盘占位符；移除赛事轮次重复前缀和面向开发者提示；后端批量目录读取补齐当前结果页对手信息；赛季摘要优先权威供应商统计，无可用供应商统计时按上述可信规则派生，并仅在派生指标上标注来源。
- **验证：** 真实浏览器检查目标球员 profile、结果筛选/重置/分页以及桌面和 390px 手机视口。重启后 2026 赛季显示已收录单打赛果 47 场、44 胜 3 负、胜率 93.6%，没有推算冠军数/场地数据；2025 年使用 API-Tennis 统计，显示 64 场、58–6、90.6%、6 冠及硬地 39–3 / 红土 11–2 / 草地 8–1。历史对手显示完整姓名、中文名和国籍。`./scripts/tennix-live down` / `up` 均成功，数据卷保留且未运行 `init`；数据库、Redis、runtime、API、frontend 与同步状态均正常。后端确定性测试 `1338 passed`；前端 Vitest `37 files / 494 passed`；TypeScript、球员专项测试、P3 查询新鲜度回归、Ruff 与 `git diff --check` 通过。未读取或输出根 `.env`。
- **完成提交：** 实现与回归测试 `a885a6a`；本任务不包含用户已有 P3 工作区差异。总控关闭记录随下一提交。
- **环境与保护：** 复用已运行本地真实服务；不运行 `init`、不读根 `.env`；保留 `backend/app/service.py` 中两处既有 P3 修改及 `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts`，不纳入本任务提交。

## T103 彻查并修复历史赛果盘分/局分丢失（`done`）

- **领取：** 2026-09-26，Codex，`main`，起始 HEAD `0d63c48`；领取记录 `c82cd11`、`0e63258` 已推送。
- **目标：** 查清为什么历史赛果中经常缺少盘分或每盘局分，逐层比较供应商原始返回、provider 解析、canonical `Match/SetScore`、存储读回、REST DTO、前端 view model 与最终页面；修复实际丢失数据的根因，而不是只调整空值文案。
- **调查范围：** 检查 API-Tennis 官方数据契约与多个真实不完整/完整样本；区分“供应商确实未提供”与“本地解析、归约、持久化、缓存、序列化或展示丢失”；覆盖球员历史列表和共享比赛详情路径；确认已落库空值能否通过正常有限重取恢复，以及不可恢复时的诚实呈现。
- **已验证根因（2026-09-26）：** 本地真实 `get_fixtures` 返回抢七盘分为 `score_first="6.7"`、`score_second="7.9"`（另有 `7.7` / `6.2`）；当前 `parse_non_negative_int()` 只接受纯数字字符串，因而把两侧都转成 `null`。同一响应保留 `event_final_result="3 - 1"`，所以盘数在、含抢七的逐盘局分缺失；普通数字分如 `6` / `3` 正常通过。球员赛果 API 与比赛详情 API 都能复现。两盘 PBP 最终比分分别是 `7–9`、`7–2`，与小数点后数字相符。比赛详情的已存快照也保留缺值（`as_of=2026-09-25T16:29:48Z`），故需要兼顾旧快照按需刷新。官方文档说明 fixtures 内联提供 `scores` 与 `pointbypoint`，但未写明点号编码；参考：[REST fixtures](https://api-tennis.com/documentation)，[WebSocket score payload](https://api-tennis.com/documentation_websocket)。
- **设计与计划：** [T103 比分完整性设计](./docs/superpowers/specs/2026-09-26-tennixai-t103-score-integrity-design.md) 与 [T103 实施计划](./docs/superpowers/plans/2026-09-26-tennixai-t103-score-integrity-implementation.md)；用户已确认方案。严格解析、稀疏快照合并、已结束不完整比分按需修复和前端展示均已实现并通过真实运行验收。无 schema migration、批量历史抓取或 `.env` 读取。
- **已完成切片：** `f22d19d` 为 canonical `SetScore` 增加向后兼容的抢七分字段并严格解析供应商格式（如 `6.7` → 局数 6、抢七分 7）；`02b614f` 按同一比赛、球员顺序和盘号归并稀疏比分；`321917d` 为已结束且局分不完整的旧快照增加详情读取时按需补取，复用 `match-metadata:<id>` 缓存、Reducer、持久化及 SSE 发布；`e47b5e1` 将逐盘抢七分贯通球员历史、比赛详情和首页比分展示。纯比分补取跳过额外场地查询；完成、进行中和未开始的完整/不适用场景不会触发比分补取。
- **自动化验证：** 后端 deterministic 套件 `1358 passed, 37 skipped, 91 deselected`；前端 Vitest `37 files / 499 passed`、TypeScript、T103 改动文件 Ruff、`git diff --check` 通过。此前全量后端尝试的 16 个失败仍是本机既有集成测试库 schema 不匹配（缺少 `match_state_snapshots.freshness` 列及 `point_events.is_break_point` 非空约束不满足）；未迁移或重置数据库。
- **真实运行验收（2026-09-26）：** 经批准执行 `./scripts/tennix-live down` → `up`，down 明确报告数据保留、未触碰 volumes；没有运行 `init`、迁移或清库。`status` 随后显示数据库、Redis、runtime、API、frontend 均健康/运行中，sports stream、schedule、rankings、Polymarket 均为 `ok`，paper 仍为 `paper_only`、模型仍为 `not_promoted`。同一比赛 `mat_127f7e0acb5c443ba79e4fb90bf8471b` 的历史 API、详情 API 和浏览器页现均显示完整四盘 `6–7（7–9）、7–6（7–2）、6–3、6–4`；详情页显示两盘抢七双方小分。重启后核验该球员 2026 赛季 47/47、2025 赛季 64/64 条记录均含完整逐盘局分；2026 样本中有 19 个抢七盘分行。检查到的 111 条真实赛果没有上游缺盘分样本；provider/service 回归测试覆盖无效/缺失值保持未知、补取失败或仍不完整时不覆盖已知比分，未用推算填空。浏览器首次载入时仍显示旧缓存时间，刷新后 API 与页面时间均更新至 08:17（北京时间）。
- **执行边界：** 真实字段缺失继续未知；不依据胜负、胜盘数或 PBP 反推局分，不做周期轮询或批量历史抓取；只在查看已结束且比分不完整的比赛时按需刷新，并复用现有缓存。
- **验收门（通过）：** 真实 API 样本证明供应商提供的完整比分和抢七分可从历史/详情 API 到页面；partial、invalid、missing 与 provider-failure 行为由确定性 provider/service 测试验证，未知值继续为空、不推算。后端 deterministic、前端全量、TypeScript、改动文件 Ruff、`git diff --check` 均有通过证据。实查的 111 条真实记录均完整，因此没有把 fixture 误称为真实上游缺分样本。
- **安全与现场：** 根 `.env` 未读取或输出；没有 API key、查询凭据或原始供应商 payload 被打印/保存。真实服务保持运行，数据库卷未重置。`backend/app/service.py` 的两处既有 P3 freshness 修改及 `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 均为用户已有改动，不纳入 T103 提交。

## T104 全站球员照片贯通（`done`）

- **领取与提交：** 2026-09-26，Codex，`main`，起始 HEAD `c3abe16`；实现提交 `9e26970`（供应商/canonical/目录持久化）、`cea6988`（service 与 P3 API）、`d672578`（全站前端），回归提交 `6402831`（排名照片请求并发上限）、`19ee1a4`（损坏照片中性占位）。
- **目标：** 让首页、比赛详情、市场、排名、球员搜索/详情及其他显示球员身份的页面统一使用真实球员照片；彻底移除姓名首字母头像。
- **方案：** 仅使用 API-Tennis 明确提供的球员照片；复用现有球员目录 `image_url` 存储和内部 `player_id` 关联。按页面实际需要填充并缓存，避免启动时批量请求全部球员；没有供应商照片或无法唯一识别球员时用中性头像，不伪造、不猜测身份。
- **边界：** 不读取/输出根 `.env` 或凭据；不新增图片供应商、爬虫或图片生成；不修改市场匹配、模型、Paper 语义；保留已有用户修改与未跟踪文件，尤其 `backend/app/service.py` 的 P3 freshness 修改。
- **规格/计划：** [设计规格](docs/superpowers/specs/2026-09-26-tennixai-t104-global-player-photos-design.md)；[实施计划](docs/superpowers/plans/2026-09-26-tennixai-t104-global-player-photos-implementation.md)。方案已落盘并直接进入实施，无额外等待确认。
- **完成情况：** canonical `Player.image_url` 贯通 API-Tennis 比赛 `player_logo` 与球员资料 `player_logo`，按内部球员 ID 复用目录缓存；空照片更新不覆盖已知照片。排名只为当前页面缺图球员按需补齐，最多 5 个并发；比赛/首页目录读取不因头像而额外请求供应商，比赛详情需要补齐时复用 profile 缓存。照片缓存写入失败只记录异常类型，不影响核心数据响应。P3 市场、机会、Paper 和市场脉搏按内部 outcome/player ID 传图，不按名字猜测；全站统一 `PlayerAvatar`，无图/坏图使用中性人像，已删除姓名首字母头像。演示数据没有权威照片时保持中性占位。
- **验证：** `uv run pytest -q --ignore=tests/integration`：`1363 passed, 37 skipped`；P3 查询与照片相关 PostgreSQL 集成：`14 passed`；前端 `./node_modules/.bin/vitest run`：`39 files / 505 passed`；`./node_modules/.bin/tsc --noEmit`、T104 后端 Ruff 与 `git diff --check` 均通过。全站真实浏览器/Playwright 视觉验收未运行：项目 Playwright 配置会读取根 `.env` 并可能启动服务，本任务边界禁止触碰；未重启服务、未运行 `init/up`，未读取或输出根 `.env`。一次较宽 integration 组合运行中有 1 个既有测试库 schema 不匹配失败（缺少 `match_state_snapshots.freshness`）；未迁移/重置该库；本任务相关 P3 与照片数据库集成测试另行通过。
- **范围保护：** `backend/app/service.py` 中两处既有 P3 freshness 修改仍未暂存/提交；`.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 等既有未跟踪文件均保留。

## T99 初始化并启动本地真实服务（`done`）

- **目标：** 经用户批准运行一次 `./scripts/tennix-live init`，随后启动真实本地服务并检查健康状态。
- **起始状态：** `main` / `8ee0807`，与 `origin/main` 同步；PostgreSQL/Redis 容器停止。启动后发现保留的数据卷已有数据库（迁移前 `0006`、已有目录数据和历史 init 标记），没有删除或重置数据。工作区内既有用户修改和未跟踪文件全部保留。
- **边界：** 仅通过根目录运行手册和 `./scripts/tennix-live` 操作；不输出或提交 `.env` 凭据；只操作 TennixAI 自有容器/进程，不触碰其他项目容器。初始化可能同步目录并消耗 LLM 配额；用户已明确批准。
- **首次尝试：** `init` 将 schema 从 `0006` 迁移至 `0008`，之后在目录排名引导阶段失败（启动器只报告脱敏的 `AppError`）。ATP/WTA 最新排名仍为 `2026-09-23T13:32:27Z`；初始化顺序证明该次失败发生在中文别名 LLM enrichment 之前，没有调用 LLM。目录数据未删除或重置。
- **首次尝试的供应商核验：** 按官方文档使用大写 `ATP`/`WTA` 的 `get_standings` 请求，均返回 HTTP 200，但响应含 `error` 字段、缺少文档成功响应的 `success` 字段，未返回可用排名。错误正文未输出；官方文档说明 standings 数据取决于当前订阅计划：[API-Tennis 文档](https://api-tennis.com/documentation)。具体账户/套餐原因尚不能从脱敏结果确定。
- **此前状态：** `./scripts/tennix-live status` 显示 PostgreSQL、Redis healthy；runtime、API、frontend 均 stopped，故真实服务尚未启动。此前 `up` 因本地 launcher 初始化成功标记被失败的 `init` 清除而拒绝。
- **本次续接与完成提交：** 用户报告已更新根目录 `.env` 中的 API key 并要求重试；领取记录 `e31c623`，`.env` 内容未读取或输出。验收证据提交 `4d1289a`：`init` exit 0（`revision=0008 players=3976 matches=185`）；`up` exit 0；随后 `status` 显示 PostgreSQL、Redis、sports stream、schedule、rankings、Polymarket 全为 `healthy/ok`，runtime/API/frontend 三进程均 running，`paper_only` / `model not_promoted` 保持原状。首页和 API health 均为 200。`init` 含离线中文名补齐，可能使用 LLM 配额；启动器没有报告实际翻译批次数，无法据此核算。未执行浏览器视觉测试或额外 provider/LLM 核验。
- **安全与范围：** 没有重置既有数据、没有绕过初始化标记、没有碰其他项目容器，也没有输出或提交任何凭据。真实服务保持运行；浏览器视觉/全站内容验收不属于本次启动任务。

## T100 排查首页展示过期比赛（`done`）

- **目标：** 查明首页为什么显示已经结束的旧比赛，区分是 API 源数据、查询范围/排序、日期时区、前端过滤还是缓存导致。
- **起始状态：** `main` / `45a4308`，与 `origin/main` 同步；TennixAI 本地真实服务正在运行。已知工作区改动均为用户所有，本任务只读，不修改产品代码。
- **边界：** 只读取当前浏览器页面、本机应用的只读 HTTP 响应和相关实现；不读取根 `.env`，不发起供应商/LLM 请求，不重启或关闭服务，不改数据库数据，不改任何代码。完成后报告证据与根因；如需修复，另行授权。
- **调查结论：** 不是 API key 过期或服务未运行。北京时间 2026-09-25 20:01 的本机 API 查询中，默认 ATP/WTA 单打“直播”结果 43/43 的开赛时间都已过去，最早为 9 月 18 日；“即将比赛”187 场中 168 场的开赛时间也已过去，最早为 9 月 17 日。最近条目的时间已到 9 月 27 日，因此首页“今晚比赛”还会把未来多日赛程当作今晚展示。
- **根因证据：** 19:59:48 的本机 runtime health 快照显示 `live_catalog` 和 `upcoming_catalog` 最近一次同步分别在 19:59:10 和 19:59:16 成功，说明后台活着；但最旧直播记录仍是 `status=live`、`scheduled_at=2026-09-18T16:55Z`、最后观测时间 `2026-09-18T18:11Z`。目录同步只 upsert 新结果、不清除 feed 中消失的比赛；`MatchCatalogRepository.list_matches` 只按状态查询，不检查开赛时间/最后观测时间；前端按 ATP/WTA 等筛选后直接展示 API 返回的所有比赛，没有过期过滤。目录加载还只设置 freshness 的 `observed_at`，`is_stale=false`、`age_seconds=0` 使用默认值，错误地把一周未观测的数据标成新鲜。
- **完成提交：** `c81c222`（调查结论与证据）、`105a487`（标记调查完成）。没有产品代码改动。现场验证为本机 live/upcoming catalog GET、runtime health GET、Home 与筛选/排序/目录实现核对，`git diff --check` 通过。具体证据见上方调查结论。

## T98 全产品缺陷与字段真相审计（`done`）

- **目标：** 以当前代码、测试、演示页面和官方数据契约为证据，跨 Home、Players、Match、Markets、Opportunities、Paper 及关键后端链路逐域走查；修复可复现 bug，并为每个对外字段确认来源、转换、空值/异常语义及验证证据。
- **起始状态：** `main` / `4ccf257`，与 `origin/main` 同步；工作区现有用户改动按下方已知清单保留。
- **边界：** 继续使用演示/fixture 数据；不运行 `init`、真实 provider/LLM 请求，不读取或修改根 `.env`，不访问 `.next`，不启停本任务之外的服务或容器。
- **完成提交：** `ad3edb9`（实现/测试）；总控与收口说明随后提交。
- **完成情况：** 已修复并有回归的缺陷：Chat 结构化市场机会卡缺失/多条 data 漏卡、EOF 与 `done(ok=false)` 被当成功、错误图标误报比赛卡、候选球员国家码裸露、旧 `/players/search` 客户端类型不符及畸形响应误当无结果、市场未知原因码泄漏、市场价差/最佳档金额文案不精确、持仓退出估算误称可退出金额且未披露未扣费用/未按盘口深度成交、Polymarket 结算 WS 提示未触发及时 REST 核验、已确认结算没有 `resolution_delta` 广播导致页面不及时刷新/盘口不冻结、未知或缺失 phase 被当成完赛/赛前、缺失的单人模型概率被伪造为 0%、待确认/未成交 Paper 行把计划报价误写成已投入/已持有、全部市场的单一模型胜率未注明对应球员，以及球员历史查询在 `unavailable` 时误说“暂无赛果”、`partial/stale` 有结果时未披露限制。另修复首次读取 Home 赛程时球员目录懒加载竞态导致排名短暂为空：目录同步完成前不再读取/覆盖比赛卡球员资料，并确保并发调用等待同一轮同步完成。完整 DTO 字段与未消费项记录在字段矩阵 T98 附录。
- **Chat/市场结算结果：** P3 `market_opportunities` 现显示结构卡并披露截断；`match_decision` 仅 Match scope，独立工作台继续消费 REST/SSE 快照。官方 `market_resolved` 订阅带 `custom_feature_enabled: true` 后只触发 REST 核验；只有供应商 REST `FINAL` 能结算 Paper。该确认在即时提示和 120 秒兜底路径都会发布 `resolution_delta`，重复相同终态只结算、不重复广播；Markets/Home 订阅该事件后刷新，市场 hook 将终态盘口冻结。WS 本身从不决定结算结果。
- **字段结论：** 已逐项记录 Match Catalog facets、Player Resolution、Chat 请求/事件/结构化字段、Home 市场脉搏、基础/runtime 健康、Match/P3 SSE、错误信封，以及此前比赛、球员、历史、市场、机会与 Paper 字段的来源、转换、消费和空值规则。未供普通用户页面消费的字段明确标为内部/未消费；provider 语义未知和真实 runtime 未验收均保留为限制。
- **演示数据覆盖：** 当前没有全站统一的演示模式。`/players?preview=1`、`/match?status=...`、`/markets?preview=p3` 各自可看固定样例；首页 `/?preview=p3` 只控制 P3 预览，首页比赛/搜索仍走后端数据链路。为覆盖全站交互，本次在 `/tmp` 隔离副本里运行 Next + FastAPI：`env -i`、fake provider/LLM、P3 disabled、固定时钟，不复制 `.env`，不触碰项目目录的 `.next`、数据库或真实服务。该做法只验证演示/fixture 链路，不表示真实 provider 全站可用。
- **视觉基线核查：** 旧 Home/Markets/Players 截图已由隔离的演示环境重新生成并写回 76 张桌面/手机基线，覆盖 Home、Players、Markets、P3 Match 多状态；代表页面已人工查看。Playwright 视觉对比 `30 passed / 4 skipped`。4 项是演示模式不运行的 P2 Replay 状态；P1 Match live/upcoming 的 Redis 依赖视觉用例从本轮排除，不能据此声称实时详情页通过。
- **验证：** 前端 Vitest `36 files / 484 passed`；隔离副本 Next production build 与其 TypeScript 检查通过；静态 source check `173 files` 通过，均未检查项目 `.next`；用户未跟踪的 `next-env.d.ts` 未纳入 source check。字段名盘点确认 `frontend/lib/api/types.ts` 的 211 个属性名、`backend/app/api/schemas.py` 的 100 个公开 DTO 属性名均已出现在矩阵。后端最新完整确定性套件以 `env -i` 运行，`1332 passed / 128 skipped`；pytest 测试启动器在导入 `app.main` 前将未显式指定的 `Settings` 环境文件设为 `None`，生产设置仍保留根 `.env` 默认路径；哨兵 `.env` 防回归测试先红后绿，证明测试不继承环境文件。API/Chat 测试使用内存 `RealtimeBundle`，无需 Redis/PostgreSQL；resolution publisher、两条 FINAL 路径和公开 SSE 透传均有测试。Playwright 功能 `80 passed`、首页问答另 `4 passed`、P1 首页结果移动端重复 `5 passed`；视觉 `30 passed / 4 skipped`。Ruff lint 与 `git diff --check` 通过；两份旧 API 测试文件的 formatter 差异均在未改动行，未做整文件重排。P1 Match live/upcoming 截图视觉用例仍因浏览器后端需要 Redis 而未计入通过；P2 Replay 视觉 4 项仍跳过。未读取根 `.env`，未调用真实 provider/LLM/Polymarket；未运行项目 `.next` 或真实运行栈。
- **执行边界：** 当前 Goal 已授权修复可复现 bug 并查清字段；用户明确选择不初始化、继续用演示/fixture。仍不运行 `init`、真实 API/LLM/Polymarket，不读取或修改根 `.env`，不访问项目目录 `.next`，不启动/停止真实运行栈或容器。隔离临时目录中的假数据 E2E 服务按测试配置自动启停；不将 fixture 结果表述为线上验收。
- **保留的用户改动：** `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/app/service.py` 中原有的 freshness 两处改动、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts`。T98 在 `service.py` 的独立 phase 代码段做了最小修复，没有覆盖原 freshness 改动。

## T97 Global Field Presentation Audit (`done`)

- **目标：** 按全站页面核对字段可见性与表达是否准确，不把真实供应商缺项误报为 UI bug，也不把测试夹具通过当成真实数据通过。
- **范围：** Home/全局搜索与结构化回答、Players 排名目录/球员主页/历史结果、Match 详情（比分/时间/球员/赛事/统计/PBP/momentum/chat/决策）、Markets（两侧报价/深度/时间/模型状态/机会原因）、Paper ledger，以及桌面/窄屏布局、缺省/错误/partial/stale 状态、北京时区和供应商字段隔离。
- **起始状态：** `main` / `c84fa6d`，工作区只有已知用户未跟踪文件；服务栈停止，`./scripts/tennix-live up` 之前返回 `LOCAL_NOT_INITIALIZED`。不读取或修改根 `.env`，不运行 LLM 消耗型 `init`，不手工迁移数据库。
- **证据方法：** 复用 T95–T96 canonical 字段矩阵和现有 E2E/fixtures；打开实际页面检查完整用户可见字段，按供应商能力、映射/数据、传输/缓存、展示层分层记录；每个确认缺陷必须有复现样例和回归测试。
- **验收门：** 全部列出页面至少有浏览器或 E2E 实际覆盖证据；真实运行时无法启动则单独列为阻塞，不声称真实数据通过；修复已证实问题并更新矩阵；运行受影响测试、前端测试/typecheck、相关 Playwright、改动文件 lint 和 `git diff --check`；最终提交并推送。
- **交付：** Home 移除产品阶段开关、重复入口、未实现的球员关注/历史入口和虚构市场概率卡；搜索与赛程发现仍在首页主路径。Players、Match、Markets、机会和 Paper 页面统一为面向网球用户的中文文案，保留数据来源、空值、延迟、未成交和模拟状态的区别。球员排名更新时间明确标为北京时间；未知决策原因不再泄漏内部代码。未改变供应商、预测、决策或 paper 语义。
- **验证：** 前端 Vitest `35 files / 454 passed`；TypeScript `tsc --noEmit` 通过；Playwright 的 P3 市场/比赛页面桌面与手机检查 `58 passed`，Home 结构化问答桌面/手机 `2 passed`；后端问答文案定向测试 `2 passed`；`git diff --check` 通过。较宽的两份 Chat 测试有 `53 passed / 1 failed`：唯一失败的比赛上下文流测试因本机 Redis `127.0.0.1:6379` 未运行而无法执行；没有为此启动 Redis。仓库无前端 lint 脚本或 ESLint 可执行文件。
- **真实数据边界：** 用户批准使用真实服务，但选择不执行首次初始化。`tennix-live status` 显示受管运行栈停止、无持久健康记录、无 Postgres/Redis 容器；真实浏览器数据门因此保持阻塞。首页/球员页所见是演示数据，Match 页面显示可恢复的加载错误，Markets 显示 P3 未开放状态；这些不是实时 API 验收。未运行 `init`、真实供应商/LLM 调用，未读取/修改根 `.env`，未启动/停止容器或服务，未访问 `.next`。
- **保留的用户改动：** `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/app/service.py`、`backend/tests/test_p3_query_freshness.py` 与 `frontend/next-env.d.ts` 均未纳入 T97 提交。

## T96 Player and Historical Results Field Audit (`done`)

- **范围与结论：** 审计排名、球员资料/赛季统计、球员历史赛果与 Home Chat 历史查询，并逐字段更新证据矩阵。共修复 25 个已由回归证明的问题，包括国家名称归一化/旗帜显示、历史比分缺少逐盘行时保留明确标注的总盘数、单双打边界、日期语义与不完整历史误报。
- **修复：** API-Tennis 国家名称通过 ISO registry 映射为 canonical alpha-3；alpha-2 仅作派生展示字段，前端使用动态旗帜资源，不维护手绘国家清单。历史比分仅在详细盘分不可用时显示供应商真实的总盘数，不臆造每盘局分。Home Chat 的 last/recent/yesterday 结果只取单打，遇到无法确定日期的供应商记录时标记为 partial。
- **验收：** 定向后端 `161 passed`；全量确定性后端 `1314 passed, 4 failed, 103 skipped, 25 deselected`。4 个失败用例在断开的 `127.0.0.1:6379` Redis 处无法执行到断言；按本任务边界未启动 Redis。前端 Vitest `432 passed`、TypeScript、改动 Python Ruff、`uv lock --check` 与 `git diff --check` 通过。实现提交 `b4acb8b`；细节与限制见 [T96 实施计划](docs/superpowers/plans/2026-09-24-tennixai-t96-history-h2h-field-audit.md) 和 [字段矩阵](docs/research/2026-09-24-tennixai-t95-match-field-integrity-matrix.md)。
- **边界与后续：** 未运行 `init`、未启动服务/容器、未调用真实 API/LLM、未触碰 `.env` 或 `.next`。数据库中先前已存为 null 的国家值需等下一次正常数据同步才会被供应商映射补齐；本任务未做运行中页面复验。T94 的本地浏览器复验仍待初始化授权。

## T95 范围与交接

- 目标：不预设其余字段没有问题；建立 canonical 字段清单，逐一追踪 API-Tennis 官方语义与原始值、provider mapping、reducer/持久化、REST/SSE DTO、前端显示及 `as_of`/freshness。重点覆盖比赛状态/时间、赛事与轮次、场地/赛制、球员身份/国家/排名、比分/发球方、PBP、22 项统计和 momentum。
- 按端到端数据流分批验收，不以“测试全绿”替代真实字段覆盖；有官方文档不清楚之处先核对官方文档，有值不一致之处记录样本、预期和证据。
- 修复范围限于已证实的 bug；不要加入轮询、供应商字段外泄、虚构值或新的架构/产品能力。
- 保留当前运行栈及根目录 `.env`，不读取/输出凭据；不触碰 `.next` 与已知用户未跟踪文件。
- **完成结果：** 建立覆盖 canonical 比赛字段的端到端证据矩阵；依据 API-Tennis 官方 REST/WS 文档及 fixtures 记录每个字段的来源、单位、缺失值和未公开语义。修复错误的当前盘标签/高亮、未文档化 PBP 关键分被误当成 false、比分/技术统计非法值或单位不准确、freshness 持久化丢失等问题。比分盘数只在供应商明确返回 `Set N` 时展示；无依据的值保持未知。
- **验证：** 后端确定性 `1289 passed, 128 deselected`；前端 Vitest `422 passed`；TypeScript、改动 Python 文件 Ruff 与 `git diff --check` 通过。真实 PostgreSQL round-trip `1 passed`；迁移 `0008` 在有 freshness 数据时安全拒绝回滚，实测版本仍为 `0008`、数据和列均保留。API-Tennis standings 真实只读 smoke `1 passed`。
- **运行边界：** 未运行项目 `init/up`、未触碰 `.env` 或 `.next`，未做浏览器/运行服务复验。真实 standings API 映射已单独验证，但当前页面是否已刷新排名、后台健康状态是否恢复，仍须启动服务后确认。其他项目的 Supabase 容器和本次 T95 临时 PostgreSQL/Redis 容器均已停止，未删除容器卷或数据；Colima 保持运行。

## T94 本地运行时/浏览器复验（阻塞：等待用户批准初始化）

- 用户已授权启用本地 API/服务；其他项目自动启动的容器按用户选择已停止。
- `./scripts/tennix-live up` 已尝试，明确拒绝并返回 `LOCAL_NOT_INITIALIZED`；API、runtime、frontend 没有启动。
- 启动依赖容器后读到的持久健康快照生成于 `2026-09-23T22:26:54Z`（约 4 小时旧），当时 schedule/rankings 标为 `ok`；这不是本次运行的刷新证明。数据库停着时健康快照不可读，因此之前显示 `unknown`。
- 下一步必须运行 `./scripts/tennix-live init` 才能初始化专用运行库并继续；按 runbook，此步骤会同步赛程/排名，且可能通过 LLM 批量补齐中文名、消耗配额。等待用户明确批准，不绕过 `init` 或改用手工迁移。
- 已执行 `./scripts/tennix-live down`；Tennix PostgreSQL/Redis 与其他项目自动启动的 Supabase 容器均已停止，未删除容器或 Docker volume；最终 `docker ps` 为空，Colima 保持运行。

## T94 调查结论与验收

- 现场复现：比赛详情/球员资料仍返回 Martin Damm `741`，排名快照为 `106`（快照时间 `2026-09-23T13:32:20Z`），ATP 官方排名页也列为 `106`；搜索结果排名为 `null`。T92 修复已提交，但共享 backend 尚未重启。
- 新发现的代码路径：`RealtimeWorker` 从 PostgreSQL 恢复旧快照；API-Tennis 新资料不含当前排名；`reduce_live_snapshot` 默认会把 incoming `None` 解释为字段缺失并保留旧非空排名，再经 Redis/SSE 发布。T92 未覆盖这条实时恢复路径。
- 目标：REST 与实时发布都只以最新 standings snapshot 为排名依据；缺少当前记录时必须输出 `null`，同时继续保留稀疏 feed 中完整姓名/国家。代码与单元/worker 回归已完成；运行时浏览器验证尚未执行，用户之后已允许启用本地 API/服务，可作为独立复验任务。
- Task 1 已完成代码与 RED→GREEN：比赛详情中目录缺失球员曾错误回退显示供应商旧 rank `40`；现在目录已配置时缺少最新 standings 就返回 `null`。Reducer 新增显式权威模式，rank `106/null` 能替换旧 `741/999`；默认稀疏更新行为不变。验证：`tests/test_live_reducer.py tests/test_player_profile_service.py` 为 `47 passed`。
- Task 2 已完成：`RealtimeWorker` 在每次实时更新前按内部球员 ID 投影最新 standings，排名缺失时清空旧值；`main.py` 与 runtime assembly 都传入现有目录 repo。旧快照和后续稀疏 frame 的存储/SSE 回归均通过，worker suite `10 passed`，Ruff lint 通过。
- 独立审查后补齐两个一致性边缘：REST 排名修正现在同步发布到 Redis/SSE 热快照，worker 会先基于更新后的热快照归约；目录读取临时失败会保留当前 frame 并在 1 秒后重试，不会把错误当作“排名缺失”。新增回归覆盖这两条路径。
- **验收：** 全量后端 `1336 passed, 12 skipped, 25 deselected`（208.49 秒）；player-directory PostgreSQL `9 passed`；改动文件 Ruff 与 `git diff --check` 通过；差异无新增供应商调用、凭据、UI/schema/config 改动。实现提交 `93e1243`。
- **范围说明：** 该任务当时未重启共享服务；T95 也按范围保持项目应用未启动。T92/T94 代码与真实 standings 只读 smoke 已验证，但页面排名和后台健康状态尚未通过运行时确认；用户已允许启用服务，可在单独复验中完成。排名快照单独同步时不主动 fan-out 到空闲实时订阅；下一次 REST/worker reconcile/feed event 才会看到更新。每个 feed frame 会多做目录与 Redis 热快照读取，先观察延迟/积压再决定是否优化。

## 最近完成：T93

实施计划：[T93 实施计划](docs/superpowers/plans/2026-09-24-tennixai-t93-live-statistics-preservation.md)。

修复内容：实时 reducer 现在按 `(统计名, 周期)` 合并。WebSocket 更新中缺失的指标会保留原数值和采集时间、标为过时；同时到来的新指标正常更新。页面使用统计自身的最新采集时间，并明确显示旧数据，不再把比赛快照时间误作统计更新时间。未增加轮询、供应商调用或数据库迁移。

验证：最终确定性 backend `1241 passed, 127 deselected`；实时 reducer/provider 定向测试 `71 passed`；frontend Vitest `416 passed`、统计卡定向测试 `7 passed`、TypeScript 检查通过；改动文件 Ruff lint 与 `git diff --check` 通过。独立审查发现并修复两点：旧指标现在显示各自采集时间；数值相同的新观测也会刷新时间戳，重复空帧仍不重复发布。格式检查仍报告两个被修改的 Python 文件有旧格式差异；对照任务前版本确认差异在未触碰的历史代码，没有整文件重排。共享运行栈在使用中，因此未运行会触碰 `.next` 的 build/Playwright，也没有重启服务。

## 最近完成：T92

排名不一致的根因是把 `get_players.stats[].rank`（按赛季、单双打分类的统计）当成当前单打世界排名；同时，目录表的缓存排名和排名快照不一致，导致排名页、搜索、profile 各自显示不同数值。比赛数据写入还可能用缩写名或空字段覆盖较完整的球员资料。

现已统一：排名页、搜索候选、球员主页和比赛卡均从每个 tour 最新的 standings 快照读取当前排名。前后快照用于计算变动；供应商变动字段没有明确比较周期，不直接信任。积分与快照时间随 profile 返回；没有可靠数据的赛季数字保持“暂无”，不补成 0。空排名结果不会覆盖最后一次成功快照。v0 页面布局没有改动。

实施细节、源头核验与限制见 [T92 实施计划](docs/superpowers/plans/2026-09-24-tennixai-player-data-integrity-implementation.md)。

## 验证结果

- 最新 T94 全量确定性 backend：`1336 passed, 12 skipped, 25 deselected`；包括 PostgreSQL 集成用例。T92 历史验证为 `1237 passed`。
- PostgreSQL：player-directory `9 passed`；runtime-catalog `13 passed`。
- 前端最近验证：T93 Vitest `416 passed`；`tsc --noEmit` 通过。T94 无前端改动。
- 本次改动文件 Ruff 通过；`git diff --check` 通过。全仓 Ruff 仍有 27 条旧问题，均位于本次未修改的文件。
- T95 未执行 Next production build/Playwright：任务边界要求不重启共享服务，且 `frontend/next-env.d.ts` 是用户未跟踪文件；Vitest 与 TypeScript 检查已通过。

## 运行状态与交接

- `.env` 未读取、改写或输出；用户原有未跟踪文件均保留。
- T95 没有启动或重启本地服务。此前现场比对发现旧 Match API 对 Martin Damm 返回 `741`，最新 standings 与 ATP 官方排名页均为 `106`；T92/T94 代码已修复，真实 standings 只读 smoke 也通过，但页面排名和后台健康状态尚未通过新进程/浏览器复验。用户已允许启用 API/服务，可在下一任务中执行该复验。
- T93 实现与审查修复提交 `a28b971`、`fa00f46` 已完成；本文件和 ROADMAP 的最终关闭记录随本次推送。
- T96 实现提交 `b4acb8b` 已完成；P4.5 的 T93–T96 代码审计均已关闭，只剩 T94 修复后的服务/浏览器复验。模型晋升证据链需另行设计与授权，自动下单继续 `deferred`。

## 最近变更

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-29 | `7a15254` | T116 交付市场页桌面/手机设计、三视图信息层级与状态矩阵；相对链接与暂存文档差异检查通过。用户仅授权设计，前端未实施或测试。 |
| 2026-09-29 | `1d6e4d4` | T115 修复比赛详情页预测持久化、空均价时的盘口参考价与 `GAP`/`NO_BET` 文案；TypeScript、Python AST 与 diff 检查通过，未运行测试。 |
| 2026-09-29 | `444a5fc` | T114 调查完成：当前部署 `not_promoted`；详情 prediction 读表没有运行时写入调用；规则硬门令可执行均价为空；Polymarket gap 被页面标成比赛数据中断。只读 API/UI/代码证据见上方 T114。 |
| 2026-09-29 | `f61486f` | T113 TLS 阻塞已解除；只读 `verify` 为 `6 passed / 2 skipped / 0 failed`，真实服务已在 `3100` 启动。3101 实测仍待其他 ADE 实际占用 3100 时验证。 |
| 2026-09-28 | `90ba194` / `fd22892` / `ea1d760` | T113 端口回退实现与回归已交付；获批 `init` 成功（schema `0009`，3979 players / 281 matches）。首次 `up` 被 Gamma/CLOB 自签名 TLS 证书链阻断；没有关闭 TLS 验证，也未触碰 3100 的其他 ADE。 |
