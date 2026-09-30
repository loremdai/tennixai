# TennixAI 当前任务与交接

> 产品与稳定架构见 [PROJECT.md](./PROJECT.md)；长期路线、任务证据与历史记录见 [ROADMAP.md](./ROADMAP.md)，完整审计由 Git 历史承担。

**最后更新：** 2026-09-30 21:57（北京时间）

**当前主任务：** T126 只读调查 `/markets` 当前报价未更新的原因（`in_progress`）。

**最近执行者 / ADE / 分支：** Codex / 本地 ADE / `main`；T126 起始提交 `fc04021`，调查范围仅读取运行状态/API/代码及有界只读验证。既有用户改动保留且未纳入任务提交。

## 当前执行：T126 只读调查市场报价未更新

- **领取：** 2026-09-30 21:51（北京时间）；Codex / 本地 ADE / `main`；起始提交 `fc04021`。
- **范围：** 确认 `/markets` 当前报价停更的位置及现时数据源状态；先调查，不改产品代码、不重启服务、不触碰根 `.env` 或既有用户改动。
- **调查结论：** 21:49 初查时全部 409 个报价候选均已 stale，最新成功快照停在 10:15 UTC；市场流/批量快照报 `PROVIDER_UNAVAILABLE` / `MARKET_SNAPSHOT_BATCH_FAILED`。未重启服务，运行时随后自行恢复。
- **美国出口实测：** Polymarket `GET /api/geoblock` 返回 `blocked=true, country=US`（只保留国家/地区结论，不记录 IP）。同一出口运行 `./scripts/tennix-live verify` 为 6 passed、2 skipped、0 failed；`market_discovery`、`market_book`、`market_websocket`、`market_quote_snapshot` 均 passed。结论：美国出口可读公开目录/盘口并连市场 WebSocket；地区检查限制下单，不是当前停更原因，无需换香港 IP。
- **恢复证据：** 21:54 UTC 覆盖扫描 309 个候选全部尝试，281 fresh snapshot、27 no-liquidity、1 unavailable、0 stale、0 batch failures；21:56 UTC `/markets` ATP/WTA 第 1 页 50/196，其中 19 场 open/scheduled 和 1 场 open/live 报价新鲜，22 条 stale 都属于 `closed` 市场。无产品代码修改、服务重启或 LLM 调用。

## 最近完成任务：T125 按最终确认示意图实施市场页前端优化（`done`）

- **领取：** 2026-09-30 16:27（北京时间）；Codex / 本地 ADE / `main`；起始提交 `73a501d`（T124 已完成并推送）。
- **授权与范围：** 用户明确表示“嗯呢，就按照这个做”，授权将最终示意图落实到生产 `/markets` 前端。只优化视觉层级与用户明确要求的筛选/排序默认值；保留现有三个视图、真实 DTO/API、T124 数据库 50 行分页及 P3/Paper 业务语义。最终参考图位于 `docs/mockups/2026-09-30-markets-home-style.png`（由已确认的左对齐 Tab 修订图归档）。
- **设计约束：** 页头沿用首页近黑底、荧光黄绿；“机会 / 全部市场 / 模拟记录”采用靠左紧凑 Tab，当前项绿字+下划线及整行分隔线；市场卡保留圆形球员头像、英文主名/中文辅名、报价胶囊、每行右侧真实报价状态和箭头。默认 ATP+WTA、性别/阶段全部；赛事级别优先，阶段按 `进行中 → 赛前 → 已结束`。
- **实现提交与推送：** 后端多级别数据库过滤和排序 `a9dd266`；市场页及比分上下文实现 `71c3584`；完成记录 `1e0ea1a`。这三项已推送；在该次推送后复核时，`origin/main` 与 HEAD 同为 `1e0ea1a`。保留三视图、真实 DTO/API、每页 50 行分页和 Paper 语义；`?preview=p3` 与预览 fixture 未改。
- **验证证据：** `backend/.venv/bin/pytest tests/test_p3_api.py tests/integration/test_p3_query_service.py -q`：30 passed；`ruff check app/api/schemas.py app/service.py tests/test_p3_api.py tests/integration/test_p3_query_service.py`、`git diff --check` 通过。`frontend/node_modules/.bin/vitest run --reporter=dot`：42 files / 553 passed；`tsc --noEmit`、隔离临时副本的 `next build --webpack` 通过；市场页桌面/手机 Playwright 20 passed。最终截图：[市场页运行预览](/private/tmp/t125-markets-viewport.png)。
- **准确性保护：** 实时盘数只在比赛确为 live、快照连接在线且 60 秒内时展示；最终比分按市场球员顺序映射，且只为已结束比赛展示。无效比分和超界盘数会省略该可选细节，不影响市场列表。
- **保护边界：** `backend/app/service.py` 中既有的 Paper 报价 freshness 改动仍留在工作区、未暂存或提交。未跟踪 `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 均保留且未纳入任务提交。

## 上一交接：T124 释放内存并修复全部市场分页（`done`）

- **领取与提交：** 2026-09-30 15:20（北京时间）；Codex / 本地 ADE / `main`；起始提交 `270e531`，领取提交 `86de925`，实现及调查证据提交 `0b1e9d1`。
- **容器清理：** 清理前 82 个容器中，54 个其他项目运行中容器获最多 45 秒正常停止时间，26 个已停止容器随后移除；只保留 Tennix PostgreSQL/Redis 两个 healthy 容器。未删除 volume 或 image，未运行 system prune；两个 Tennix 数据卷仍存在。Colima 可用内存由 40 MiB 升至 7,113 MiB，memory PSI `full avg10` 由 64.57% 降为 0.00%，swap 保持为 0。
- **分页修复：** SQL 查询按现有级别、性别和阶段筛选，稳定排序后用 `LIMIT/OFFSET` 返回至多 50 个市场，并按同样条件统计 `total`；比赛资料、决策观测、预测和报价依赖仅按当前页批量读取。实测第一页默认 50/总计 2,497、第二页无重复、ATP 筛选 50/总计 100 且本页均为 ATP；Next 代理也返回 HTTP 200 与 50 行。单次第一页样本约 95 ms，不作为基准承诺。
- **验证与运行状态：** 四个修改的 Python 文件通过 AST 解析和 Ruff，`git diff --check` 通过；没有新增测试文件或运行测试套件。受支持 `down`/`up` 成功，API/市场页可访问，数据库/Redis healthy；最终状态复核中 sports stream、schedule、Polymarket 为 `ok`，排名上游仍为 `TIMEOUT_ERROR`。完整记录见 [T124 调查与验收](docs/research/2026-09-30-tennixai-t124-container-memory-and-market-pagination.md)。

## 上一交接：T123 首页风格统一市场页设计图（`done`）

- **授权与范围：** 用户要求以首页为准统一市场页设计语言并优先提高可读性；只交付设计图，不实现前端。
- **交付与完成提交：** [市场页设计图](docs/mockups/2026-09-30-markets-home-style.png)，`7e428ee`；沿用近黑底、荧光黄绿、双语球员身份、实时报价胶囊；仅设计，未实施前端代码。

## 保护的用户改动

- `backend/app/service.py`：既有 P3 查询 freshness 修改；未覆盖、暂存或提交。
- 既有未跟踪 `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 全部保留。
- 根 `.env` 不改写，不输出凭据、供应商 token 或启动所有权 token。

## 候选后续（未领取）

- T113 仍 `blocked`：3100 实际被其他 ADE 占用时的 3101 回退实测尚未完成；不为制造冲突占用端口或停止他人进程。
- T110 私人测试服务器部署仍 `blocked`；不属于本次本地启动恢复范围。
- T94 特定球员排名的运行服务/浏览器一致性复验仍未完成；初始化授权已在 T113 获得并执行，不再记录为等待初始化。T121 通用 6/6 浏览器门不替代该专项证据。
- 模型晋升证据链需独立排期和授权，自动下单继续 `deferred`。T117 市场页实现 `ed6f6a7` 等历史完成证据见 ROADMAP。

## 最近变更（最多五条）

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-30 | `a9dd266` / `71c3584` / `1e0ea1a` | T125 已推送完成：市场页采用首页视觉语言和靠左 Tab；默认 ATP/WTA，报价/身份/阶段清晰呈现；实时盘数检查新鲜度，完赛比分按市场选手顺序显示。后端 30 passed，前端 553 passed、类型检查/生产构建通过，桌面和手机 Playwright 20 passed。`?preview=p3` 未改。 |
| 2026-09-30 | `0b1e9d1` | T124 按 SQL 页取数并只装载当前页关联数据；移除 80 个非 Tennix 容器，保留数据卷；Colima 可用内存由 40 MiB 升至 7,113 MiB。实际第一页、第二页、ATP 筛选和 Next 代理请求均返回至多 50 行；Ruff、AST、差异检查通过。排名上游仍超时，sports stream、schedule 和 Polymarket 为 `ok`，详见验收报告。 |
| 2026-09-30 | `7e428ee` | T123 最终市场页设计图：沿用首页视觉，加入双语球员身份、报价胶囊与每场实时报价状态；筛选默认 ATP/WTA，排序为级别优先及进行中→赛前→已结束。仅设计，未实施前端。 |
| 2026-09-30 | `a812b73` | T122 只读定位市场加载长尾：共享 VM 内存阻塞、连接超时，全量查询与重叠刷新放大负载；未实施修复。 |
| 2026-09-30 | `57325c4` | T121 全部实现与审查修复完成；临时标记丢失及正常重启均通过，单元 1425、隔离集成 98、真实浏览器 6；T118 启动阻塞解决，服务保持 3100 运行。 |
