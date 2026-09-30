# T122 全部市场加载延迟调查

2026-09-30，北京时间。执行者 Codex / 本地 ADE / main；起始 `b9bd51d`，领取 `f22cdc6`。用户询问点击“全部市场”后等待很久的原因；本任务仅调查，不改产品代码或容器配置。

## 结论与证据强度

**当前首要瓶颈是共享 Colima 虚拟机的严重内存压力，数据库连接/访问出现长停顿；市场查询全量组装及前端允许刷新重叠进一步放大负载。** UI 能加载出行，但耗时抖动很大，不能用一次 HTTP 200 或单元测试通过证明交互足够快。

资源阻塞有直接 PSI 证据；其对具体某一次请求的贡献没有通过停止其他项目或改变 VM 配置作干预实验，因此不声称已量化每一秒的因果比例。前端重叠属于已确认代码机制；没有取得浏览器全部在途网络记录，不能声称已测出最大并发数。

## 真实测量

| 检查 | 结果 |
|---|---|
| 直连 FastAPI `/api/v1/markets?limit=50` | HTTP 200，首字节/总耗时 9.558 秒；limit 非该端点分页参数，使用默认页 |
| 同时经 Next `/api/markets?limit=50` | HTTP 200，9.588 秒；代理增量约 30ms，不能解释长等待 |
| 使用真实分页参数 `page=1&page_size=50` | 一次 30 秒客户端超时；关闭本任务复现标签后另一次 HTTP 200、18.637 秒 |
| FastAPI 基础 `/api/v1/health` | HTTP 200，2.9ms；该基础存活检查不证明 DB 延迟正常 |
| 前端已有日志中最近 15 个市场请求 | 247–909ms 与 19.5s、21.5s、50s 混合；存在明显长尾 |
| 独立真实 P3QueryService，首个请求，强制只读 DB | 14.900s；市场 overview 阶段 14.275s；八项 SQL 执行计时合计 424.9ms；后续其他阶段约 0.625s |
| 同一探针复用连接、第二次仅返回 1 行 | 524.78ms；仍处理 2497 个市场、1030 场比赛事实、2492 份报价，八项 SQL |
| 原安全参数下 asyncpg 独立连接 | 25 秒 timeout，栈停在连接协议等待；未改 ssl/认证设置 |
| `docker compose ps` | PostgreSQL/Redis 均 healthy；healthy 不代表宿主新连接没有停顿 |
| PostgreSQL 活动只读聚合 | 首次 active 1/idle 9；后续 active 2/idle 8，idle 为 ClientRead，未见 Lock wait |
| 共享 Docker 容器计数 | 56 个 running；Tennix 2 个，其他项目 54 个 |
| VM `free -m` | total 7922MiB、used 7882MiB、available 39MiB；swap 0 |
| VM memory PSI | some avg10 79.63%、full avg10 53.58%；full avg60 43.38%、avg300 55.88% |
| VM IO/CPU PSI 对照 | IO full avg10 0.45%；CPU some avg10 77.74%；系统级 CPU full 不用于判断 |

根据 [Linux Kernel PSI 官方文档](https://docs.kernel.org/accounting/psi.html)，memory full 表示所有非 idle 任务同时因内存资源停顿的时间比例，持续出现属于 thrashing。这里不是仅因 used 高就推断内存不足，而是 available 极低、零 swap、持续高 full PSI 和连接长停顿相互吻合。

Tennix PostgreSQL/Redis 容器单次快照内存约 207MiB/29MiB；共享虚拟机还有多套其他项目容器。没有停止、重启或重新配置任何项目来人为降低压力。

## 请求链路中的放大因素

1. **后端分页发生在组装之后。** `backend/app/service.py:2079` 的 `markets()` 读取全部 overview、决策、比赛事实、预测、热 book 和存储报价，为所有市场创建 DTO；直到 `:2256` 才统计 total、切出当前页。即使只返回 1 行，实测仍装载全部 2497 行及其依赖。虽然 T84 消除了 N+1，固定八项 SQL 并不等于处理量与当前页大小一致。
2. **每次报价事件重新取列表，缺少在途合并。** `frontend/components/markets/markets-state.tsx:250` 的 1 秒节流只保护待触发 timer，回调执行时即清 timer；没有等待上一次 `loadListings` 完成的锁/合并机制。请求持续 10–50 秒时，后续事件可再发请求。初次加载 `:230` 并行读取三个视图，即使只看一个选项卡；一般 stream 变化也触发全视图 refetch。
3. **加载多页后刷新成本增长。** `:155` 至 `:158` 从第一页顺序重取到已加载的最后一页，然后一起更新列表。一页长尾会累积到多页刷新；后端每页仍做全量装载。
4. **tab 本身主要是本地状态切换。** `MarketsWorkspace` 的数据 hook 在挂载时已经发请求，选项卡切换显示其结果；视觉上“点击 tab 才开始等”并不意味着 tab 按钮自身执行了慢计算。本任务独立浏览器标签复现了加载骨架，随后“全部市场”显示已加载 50/2497 行。用户原标签未导航或关闭；本任务标签已关闭。

市场读侧仅使用 DB/Redis，本次计时没有等待 Polymarket HTTP 或 LLM。不能把这次列表加载延迟归因于模型尚未晋升。

## 建议的处理顺序（未实施）

1. 先给共享 Docker VM 留出内存余量：确认哪些其他项目容器可停止，或在宿主资源允许时调整 VM 内存；配置依据 [Colima Configuration](https://colima.run/docs/configuration/)。停止其他项目与重启 VM 影响现有工作，需明确限定对象与时机。
2. 产品读侧把筛选/total/page 边界下推，只为当前页装载报价、事实和预测；保留既有排序、过滤、内部 ID、诚实 stale/gap、final/Paper 语义，先做等价结果回归。
3. 前端将事件刷新合并为一个在途请求与必要的尾随刷新，避免旧响应覆盖新结果；优先读取当前视图，保留最近可信行；只刷新已显示的资源。
4. 长期可按 [Colima Profiles](https://colima.run/docs/profiles/) 给项目独立 VM/runtime/资源，避免多套 Supabase 共享同一内存预算。新 profile 有独立 containers/volumes，不能直接切换后假设现有 DB 数据已跟随；数据保留与切换需要另行设计。

验收应同时记录点击到内容可见、API p50/p95、首次连接时间及刷新并发数，并在存在报价事件的场景验证；本任务没有实施或宣称修复通过。

## 边界与失败尝试

- 全部数据库探针设置 `default_transaction_read_only=on`，只输出时长、计数和状态；没有写 schema/数据、调用 LLM、交易、改根 `.env` 或弱化 TLS。
- 初次性能脚本错误导入 PaperLedgerRepository，修正到已有 paper_repositories 后成功运行；没有因此修改产品。
- 容器内 `time` 不存在，改为直接只读 psql 聚合；未安装工具。host 内存 sysctl 被沙盒拒绝，未依此给出宿主内存或建议具体扩容数值。
- 当前浏览器地址已变化，未操作用户标签，使用本任务独立隐藏标签复现。浏览器只读 evaluate 不暴露 Performance API，因此没有编造浏览器网络计时；API 与前端日志计时单独取得。
- API 日志尾部包含 TimeoutError/InterfaceError 信号；未将有凭据风险的原始异常 SQL/参数或完整日志写入报告。
- 只提交本调查报告与总控更新。用户 `backend/app/service.py` freshness 修改与全部既有未跟踪文件保持原样。未运行产品测试：只读调查没有产品代码变更，实际证据是请求、SQL/连接探针、资源指标与代码追踪。
