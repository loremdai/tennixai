# T121 启动恢复验收

日期：2026-09-30。执行者：Codex / 本地 ADE / main。起始提交 `3a1a7f4`，领取 `594276d`；实现 `ac97af6`、`63c671e`、`26eba0e`、`e13c0ec`、`57325c4`。

方案：[T120 官方恢复方案](./2026-09-30-tennixai-t120-official-recovery-solution.md)。计划：[T121](../superpowers/plans/2026-09-30-tennixai-t121-startup-recovery.md)。日常操作：[本地运行手册](../runbooks/local-real-runtime.md)。

## 最终行为

1. 已知 condition 显式查询 `closed=false`；只有合法空列表才查询 `closed=true`。重复、无关和非法结果拒绝。关闭市场可读取规则和最终结算，但不再读取 CLOB 报价；只有有效 final payout 才结算，包括 50/50。
2. 取消、结束、延期及 stale live 不进入报价需求；赛前窗口只用于 scheduled。报价需求排除数据库中已关闭市场，市场链接、持仓和账本保留，结算仍独立推进。
3. 单市场失败被隔离，尝试与每轮预算均有界，逐次轮转并退避。目录、旧 live fixtures 校准及结算 jobs 先执行且各自有超时；每项结束或失败都保存健康。任意恢复失败保持聚合 GAP，其他成功报价不能覆盖它。
4. 本次 runtime 的 DB/schema/Redis 就绪独立于上游健康；stale/gap/degraded 继续阻止新模拟动作。退出报价流的 pending ENTRY/EXIT 仍维护到期状态，避免遗留 intent 永久悬挂。
5. 初始化事实来自持久 PostgreSQL 记录，必须与实际及仓库 Alembic head 一致。临时 state.json 丢失后可直接 up，无 bootstrap、补名或生产迁移。专用 session advisory lock 保证同库只有一个 runtime owner；当前实例指纹阻止旧健康记录满足新启动门。

没有引入依赖、生产 schema migration、LLM、模型晋升或真实订单。

## 官方依据

- [Gamma List markets](https://docs.polymarket.com/api-reference/markets/list-markets)：默认 closed 过滤及显式查询。
- [Market Details](https://docs.polymarket.com/market-data/market-details)、[Resolution](https://docs.polymarket.com/concepts/resolution)：可交易状态与最终结算分离。
- [Realtime data](https://docs.polymarket.com/market-data/realtime-data)：关闭事件与连接保活。
- [API-Tennis REST](https://api-tennis.com/documentation)、[WebSocket](https://api-tennis.com/documentation_websocket)：live coverage 与 fixtures 校准，不假设重放终态。
- [Python asyncio timeouts](https://docs.python.org/3.12/library/asyncio-task.html#timeouts)：有界等待与取消传播。
- [PostgreSQL advisory locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)、[lock functions](https://www.postgresql.org/docs/current/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS)：session 锁独立于事务，退出时显式 unlock；不通过新增租约表解决所有权。

## 自动验证

| 门 | 实际结果 |
|---|---|
| Task 1 provider | 38 passed |
| Task 2 demand/worker | 42 passed |
| Task 3 daemon/health/launcher/worker | 171 passed |
| 最终受影响套件 | 246 passed |
| 后端单元全量，backend 工作目录，`pytest tests -m 'not infrastructure' -q`，live opt-ins 关闭 | 1425 passed、37 skipped、97 deselected，最终 21.11 秒；1 条 joblib 核心数探测警告 |
| 完整隔离 PostgreSQL/Redis 集成，`pytest tests/integration -q` | 98 passed，71.93 秒，包含延迟门及真实 advisory lock 独占/释放 |
| 真实 Playwright，`TENNIX_E2E_LOCAL_RUNTIME=1 ./node_modules/.bin/playwright test e2e/local-real-runtime.spec.ts --workers=1` | 6 passed，1.1 分钟，桌面/手机首页、球员与市场/详情流程 |
| Ruff 新诊断与基线 `594276d` 比较 | 零新增；未清理已有规则问题 |
| `git diff --check` | 通过 |

集成使用专用 `tennix_t121_test` 与 Redis DB13；现有 runtime-catalog fixture 仅重建明确保护的 scratch 数据库。没有迁移、重建或删除 live/default 数据库。真实 runtime 在隔离集成延迟门期间停止，避免并发负载改变时间结果。

新增回归先观测 RED 再 GREEN。唯一最终审查发现五项 Important、零 Critical/Minor；在一次修复阶段补齐：外层 timeout 造成轮转饥饿、scheduled 过早 stale、退订 pending intent 无人维护、旧 live 校准游标跳过尾部、标记丢失后重复 owner。全部加入回归并通过完整套件；没有通过放宽断言、重试、skip 或健康门处理这些问题。

## 真实启动与数据保留

- 最终代码 `57325c4` 下，受支持 down 完成后，将临时 state.json 备份移走；直接 `./scripts/tennix-live up` 成功。初始化记录完全不变，历史内部 ID 集合完整保留，没有再次 init 或 LLM 补名。
- 再次 `./scripts/tennix-live down` → `up` 成功；同样的只读保留断言再次通过。无 volumes 删除，无其他项目进程/容器终止。
- 验收前基线：players 5604、matches 3772、markets 2494、Paper intents/fills/positions 各 0。两次最终重启后：players 5605、matches 3772、markets 2494、Paper 各 0；正常目录同步允许新增，不要求禁止增长。旧 ID 均仍存在。
- 最终 status 为 stack running，runtime/API/frontend running，PostgreSQL/Redis healthy；前端 `http://127.0.0.1:3100`。`/api/v1/health` 与首页均 HTTP 200。最终体育、赛程、排名与 Polymarket 均 OK；排名源启动初期曾为 unknown，健康如实呈现并等待本次同步，不以旧快照补成 OK。
- 浏览器真实门要求聚合健康 OK 后执行，6/6 实际通过。无严格映射市场时，既有门允许诚实空态并不保证逐个详情被点击；这是页面验收边界，不是跳过失败。
- 服务按用户要求保持运行；paper_only、model not_promoted。根 `.env` 未修改，未输出凭据或启动 token。

## 失败尝试及纠正

1. 首次全量测试指向 legacy default DB，缺少已有 freshness 列；中止该尝试。未为通过测试迁移旧 DB，改用明确隔离测试数据库。
2. root 工作目录运行单元门有一个相对 `app/prediction/service.py` 读取失败；改为 backend 工作目录后全量通过。
3. 将隔离 DSN 全局覆盖后混跑全量有两项默认 Settings 断言失败；分开默认环境单元门与隔离集成门后全部通过。
4. runtime/模型单元基准和集成并发时，延迟门为 151 秒（门槛 60 秒）；停止 runtime、结束并发单元测试后完整隔离集成 98/98 通过。
5. 同期第一次浏览器 5/6，手机球员页仍加载中。最终正常重启后无并发 DB 测试重跑，原断言不变，6/6 通过；没有改产品或测试 timeout 来掩盖结果。
6. 新 ownership SQL 门首次自动审批误判涉及 default DB 写入；读取 scratch 名称与保护断言后给出精确说明，重试获批，真实 SQL RED→GREEN 并纳入最终 98 项集成门。当前无审批阻塞。
7. 初次只读 status 在沙盒内被 uv cache 文件访问拒绝；使用已授权的受支持启动器权限读取成功。

## 执行取舍（按作出顺序）

1. 用户 AGENTS 明确要求 main 与提交推送，因此在 main 领取后执行，不另建 worktree 或询问重复授权。若判断错，成本是共享分支协调冲突；领取已先推送。
2. DB 健康持久化失败时恢复不算完成，因为本地就绪需要可靠存储的成功记录。若判断错，成本是等待/重试，而不是数据库不可用时启动 API。
3. 计划中的 `test_runtime_catalog_repository.py` 不存在，改用已有 `tests/integration/test_runtime_catalog_postgres.py` 的隔离 fixture。若判断错，成本是错选测试门；实际 SQL round-trip 与 revision checks 已覆盖。
4. 审查者没有独立执行外部真实验收，由本任务执行受支持 up/HTTP/E2E。若判断错，成本是真实行为仅有本任务证据，没有第二位执行者重复验收。
5. 用户 freshness 改动及既有未跟踪文件不纳入本任务，保留其归属。若判断错，成本是相关任务外正确性未在本次审计。
6. 模型晋升、交易、新生产 migration 不属于启动恢复授权。若判断错，成本是不产生新的模型动作；既有 paper-only 产品边界保持。

无 deferred Minor。所有用户既有改动未暂存或提交；长期历史仍由 ROADMAP 与 Git 承担。

## 留待独立任务

T113 的 3100 被其他 ADE 占用时的真实 3101 回退、T110 私人部署、T94 指定球员排名复验及模型晋升不因本次 6/6 通用浏览器验收而自动关闭。新的上游故障仍可表现为 degraded，但不会再依赖关闭市场默认查询或临时初始化标记阻断整个启动。
