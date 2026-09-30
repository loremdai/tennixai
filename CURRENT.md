# TennixAI 当前任务与交接

> 产品与稳定架构见 [PROJECT.md](./PROJECT.md)；长期路线、任务证据与历史记录见 [ROADMAP.md](./ROADMAP.md)，完整审计由 Git 历史承担。

**最后更新：** 2026-09-30 14:38（北京时间）

**当前主任务：** T123 首页风格统一市场页设计图（`in_progress`）。用户已明确要求等 T122 完成后再出图；本任务只交付以首页视觉语言为准的新设计图，不实施前端代码。

**最近执行者 / ADE / 分支：** Codex / 本地 ADE / `main`；T123 起始提交 `e348bba`，领取记录先推送；用户既有改动保留且未纳入任务提交。

## 当前任务：T123 首页风格统一市场页设计图（`in_progress`）

- **领取：** 2026-09-30 14:38（北京时间）；Codex / 本地 ADE / `main`；起始提交 `e348bba`。T122 `a812b73` 已完成并推送，main 与 origin/main 同步。
- **授权与范围：** 用户要求结合首页设计特色重新绘制市场页，让两边视觉语言一致，并以首页为准；先前已选“信息更清晰、扫读更快”，并要求等 T122 完成后再做设计图。本次只检查首页/市场页并交付新设计图；不改前端实现。
- **完成门：** 交付可查看的市场页设计图，清楚复用首页配色、背景、组件和排版特征，同时让机会/全部市场/Paper 三视图易于扫读；完成后记录图像路径与实际检查证据。
- **保护边界：** 保留 T122 已提交调查成果及全部既有未提交用户改动；领取提交仅包含 `CURRENT.md`。

## 最近交接：T122 全部市场加载延迟调查（`done`）

- **领取：** 2026-09-30 14:16（北京时间）；Codex / 本地 ADE / `main`；起始提交 `b9bd51d`。已 fetch，main 与 origin/main 同步，用户已知修改与保护清单一致。
- **授权与范围：** 用户询问点击“全部市场”刷新等待很久的原因。只读测量页面请求与直接 API 耗时，追踪现有查询、批量装载和刷新路径；保留运行栈、数据与所有用户改动，不调用 LLM、不修改产品代码。
- **完成提交与证据：** `a812b73`，[T122 调查报告](docs/research/2026-09-30-tennixai-t122-all-markets-latency-investigation.md)。直接/代理市场 API 9.558/9.588 秒，后续曾 30 秒超时；独立首查询 14.900 秒、复用连接 0.525 秒；VM available 39MiB/total 7922MiB、swap 0，memory PSI full avg10 53.58%。共享 56 个容器中 Tennix 2 个。每页仍处理全部 2497 市场，前端事件刷新没有在途合并，多页刷新顺序重取。未改产品、容器或环境，未停止其他项目。
- **限制与交接：** 已确认资源阻塞与代码放大机制，但没有停止他人工作作减负干预或测得浏览器全部请求并发数。下一步需明确资源调整范围及实施授权；T121 单元/启动门不代表列表延迟门。当前进程保留运行，基础 API HTTP 200；上游/DB 可能受资源压力产生 degraded，勿将 T121 历史健康当成本时刻性能证据。

## 上一任务：T121（`done`）

- **授权与范围：** 用户“开始实施”，随后“继续”；按 [T120 官方方案](docs/research/2026-09-30-tennixai-t120-official-recovery-solution.md) 与 [T121 计划](docs/superpowers/plans/2026-09-30-tennixai-t121-startup-recovery.md) 完成恢复修复与真实启动验收。
- **实现提交：** `ac97af6` 已知关闭市场查询/结算；`63c671e` 终态需求与单市场隔离；`26eba0e` 独立维护和本地就绪；`e13c0ec` 持久初始化；`57325c4` 专用 DB 所有权、实例指纹、轮转推进及退订 intent 维护。五项 Important 审查发现已 RED→GREEN，无 deferred Minor。
- **实际验证：** 最终 backend 单元 `1425 passed / 37 skipped / 97 deselected`；完整隔离 PostgreSQL/Redis 集成 `98 passed`（含延迟与 advisory lock）；受影响套件 `246 passed`；真实桌面/手机浏览器 `6 passed`。Ruff 对基线零新增诊断；`git diff --check` 通过。详细命令、失败尝试及纠正见 [T121 验收报告](docs/research/2026-09-30-tennixai-t121-startup-recovery-validation.md)。
- **真实重启：** 停止后移走临时 state.json，直接 up 成功；再 down/up 成功。两次初始化记录完全不变、旧内部 ID 全部保留。无重新 init、LLM、生产 migration、历史/账本删除或真实订单。
- **最终现场：** stack running，runtime/API/frontend running，PostgreSQL/Redis healthy（external）；sports_stream、schedule、rankings、Polymarket 均 OK；`paper_only`、`model not_promoted`。前端 [3100](http://127.0.0.1:3100)，API health 与首页 HTTP 200。服务按用户要求保持运行。
- **运行入口：** `./scripts/tennix-live up/status/down`；临时标记仅为进程缓存，持久初始化记录、schema 及当前 DB/Redis 就绪决定是否可启动。上游 degraded 不阻断本地服务，但仍阻止新模拟动作。见 [运行手册](docs/runbooks/local-real-runtime.md)。

## 保护的用户改动

- `backend/app/service.py`：既有 P3 查询 freshness 修改；未覆盖、暂存或提交。
- 既有未跟踪 `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`backend/tests/test_p3_query_freshness.py`、`frontend/next-env.d.ts` 全部保留。本任务只清理其自身的执行计划临时目录。
- 根 `.env` 不改写，不输出凭据、供应商 token 或启动所有权 token。

## 候选后续（未领取）

- T113 仍 `blocked`：3100 实际被其他 ADE 占用时的 3101 回退实测尚未完成；不为制造冲突占用端口或停止他人进程。
- T110 私人测试服务器部署仍 `blocked`；不属于本次本地启动恢复范围。
- T94 特定球员排名的运行服务/浏览器一致性复验仍未完成；初始化授权已在 T113 获得并执行，不再记录为等待初始化。T121 通用 6/6 浏览器门不替代该专项证据。
- 模型晋升证据链需独立排期和授权，自动下单继续 `deferred`。T117 市场页实现 `ed6f6a7` 等历史完成证据见 ROADMAP。

## 最近变更（最多五条）

| 日期 | 提交 | 事实 |
|---|---|---|
| 2026-09-30 | `a812b73` | T122 只读定位市场加载长尾：共享 VM 内存阻塞、连接超时，全量查询与重叠刷新放大负载；未实施修复。 |
| 2026-09-30 | `57325c4` | T121 全部实现与审查修复完成；临时标记丢失及正常重启均通过，单元 1425、隔离集成 98、真实浏览器 6；T118 启动阻塞解决，服务保持 3100 运行。 |
| 2026-09-30 | `df73500` | T120 官方文档和只读查询确认 Gamma 默认过滤关闭市场，资源仍存在；提交恢复方案并纠正 T119 推断。 |
| 2026-09-30 | `763f42b` | T119 定位取消比赛/关闭市场进入需求、单市场恢复错误传播及 jobs 饥饿。 |
| 2026-09-29 | `ed6f6a7` | T117 按批准示意图完成市场页改版，保留全站背景与真实报价/Paper 语义。 |
