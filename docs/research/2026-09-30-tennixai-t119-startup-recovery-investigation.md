# T119 隔夜启动失败只读调查

日期：2026-09-30（北京时间）。起始 HEAD：`b2e27d9`，领取：`9c84d11`。用户要求先调查原因；本任务不实施修复。

## 结论

本次应用启动失败的具体阻塞对象是 Petra Marcinko 对 Magdalena Frech 的已取消比赛（内部 `mat_f881a00ef60d42d0a2b88877c2b46034`），对应已关闭市场 `mkt_0f6485bd361648c2b592d789f6c7e8f7`。

本地 market→match 链接仍为 active。TrackingDemand 未排除取消等终态，凡有开赛时间、进入两小时窗口便加入跟踪；也未检查市场已经 closed。MarketWorker 从排序后的第一个市场读取 REST baseline，这个市场的 Gamma condition 查询返回 HTTP 200 + 空列表，适配器抛出 `not_found`。异常未在单市场启动边界隔离，传播到整个 recovery 和 tick；目录同步任务排在 demand reconciliation 后，因此无法执行。全局首次健康门一直不满足，180 秒后启动器停止 runtime，API/frontend 从未启动。

## 为什么昨天能启动

| 北京时间 | 已验证事实 |
|---|---|
| 09-29 10:49:04 | 该市场链接建立，当前仍 active（`linked_at`）。 |
| 09-29 10:52:17 | `f61486f` 提交记录昨日受支持启动成功。 |
| 09-29 19:51:23 | 该市场本地记录变为 closed（当前 `updated_at`）。 |
| 09-30 08:43:20 | 本机内核启动时间；今天发生过系统重启。 |
| 09-30 09:00–11:00 | 比赛原定 11:00，进入默认两小时跟踪窗口。 |
| 09-30 09:20 | 冻结该时刻调用实际 TrackingDemand，取消市场仍在需求集合，且按 ID 排序为第一个。 |

昨天上午，这场原定今天 11:00 的比赛未进入两小时窗口；此后市场关闭、上游默认查询不再返回该资源。T120 官方文档与显式过滤核验确认资源仍存在：Gamma `/markets` 默认 `closed=false`，显式 `closed=true` 可查到该市场。今天启动时，终态过滤、查询语义与失败隔离缺陷被这组时间/数据条件触发。无需代码发生新变化也会出现这种差异。

昨天成功启动提交 `f61486f` 到调查 HEAD，runtime/realtime/markets/API-Tennis 恢复路径无代码变更；DecisionWorker 唯一相关差异为 T115 的 `save_prediction()` 接线，它不参与本次失败的 Gamma baseline 查找。T117 为前端改版。已有用户 service.py 差异只改变 Paper 查询展示时间，未改恢复路径。

系统重启解释原进程消失。启动器标记存放 OS 临时目录（launcher.py:200），今天首次检查标记缺失；重启/临时文件生命周期与此吻合，但没有证据确认具体是谁或哪个机制删除了标记。此项使启动器先要求 init；T118 已成功 init，因此它不是后续 `NOT_FOUND` 的原因。

## 实际证据

1. PostgreSQL SELECT：比赛 `cancelled`、原定 `2026-09-30T03:00Z`；市场 `closed`；链接 `active`；全库未结 Paper position 数为 0。没有持仓要求保留该市场的盘口订阅。
2. 本地持久健康：`recovery=degraded/NOT_FOUND`、`daemon_tick=degraded/NOT_FOUND`；sports 与 Polymarket 均 `gap/STARTUP_RECOVERY`；目录/排名源未完成首轮同步。
3. 有界真实只读请求：失败市场 Gamma `/markets` 查询 HTTP 200、payload 为 list、长度 0。调用栈为 PolymarketProvider.get_order_book → _gamma_market_by_condition → AppError(not_found)。没有 HTTP 404 或 TLS/认证错误。
4. 两个同批对照市场正常：各为 Gamma HTTP 200 + 双边 CLOB book HTTP 200。成都旧 live 比赛的 API-Tennis fixtures 查询有 1 行、livescore 为 0 行；它不是已证实的本次 `not_found` 对象。
5. 以实际 TrackingDemand 冻结 09:20 时刻，返回 9 个需求市场，取消市场在首位。
6. 隔离复现使用实际 TrackingDemand、MarketWorker、PolymarketProvider、LocalRuntimeDaemon，HTTP MockTransport 返回已观测的 `200 []`，其余依赖为内存替身。结果：`cancelled_in_demand=true`、`recovered=false`、recovery `NOT_FOUND`、tick 抛 `not_found`、后续 pump/jobs 调用列表为空。没有数据库/Redis/网络写入。
7. T120 补充核验：同一 condition 的默认查询与显式 `closed=false` 均为 HTTP 200、0 行；显式 `closed=true` 为 HTTP 200、1 行，`active=true / closed=true / acceptingOrders=false / umaResolutionStatus=resolved`。资源没有删除；`active=true` 单独不能判断可交易。官方依据与方案见 [T120](./2026-09-30-tennixai-t120-official-recovery-solution.md)。

真实 probe 数据库连接设置 `default_transaction_read_only=on`。输出仅内部 ID、聚合状态、HTTP 状态及脱敏代码栈；凭据和上游原始 payload 未输出。脚本在 `/tmp`，没有修改产品代码或测试文件。

## 代码机制

- `backend/app/decision/worker.py:72`：TrackingDemand 从未结持仓及 active links 构造集合；94–97 行对有开赛时间的所有状态应用窗口，未先排除 CANCELLED/FINISHED 等终态。
- `backend/app/persistence/market_repositories.py:600`：active links 只过滤链接状态。目录扫描退役逻辑（348–362 行）将市场设为 closed，不会同时停用该链接。
- `backend/app/markets/worker.py:132`：按排序逐项 `_start`，没有单市场异常隔离。211 行先取 REST book。
- `backend/app/markets/polymarket.py:205`：Gamma 空列表转为 `not_found`。
- `backend/app/runtime/daemon.py:522`：recovery 捕获后仅标 degraded，未完成恢复；457–461 行 tick 先订阅后同步，订阅失败使同步无法执行。
- `backend/app/runtime/launcher.py:206`：首次健康门要求 tennis_live/polymarket/live_catalog 全部 OK。

## 修复方向（未实施）

优先修复不含未结持仓的终态需求筛选，并在单市场 baseline/订阅失败时隔离错误，允许其他市场及低频目录任务继续推进。Gamma 元数据查询必须显式区分开放与关闭市场；`get_resolution()` 复用当前默认查询且把 not_found 返回为 None，存在关闭市场结算被遗漏的潜在问题（当前零未结持仓，未观察到实际账本损害）。未结持仓的最终结算不得被终态过滤误删；关闭市场可停止盘口跟踪但仍应保留结算查询。不要删除历史比赛、市场链接或 Paper 数据，也不要跳过启动健康门。

启动标记的临时目录持久性是另一个已暴露的问题，应独立评估，不能用重跑 init 掩盖这次运行时恢复缺陷。

## 结论边界

已确认本次具体请求、代码传播机制及隔离复现；T120 已纠正“上游资源消失”的推断，资源仍可通过关闭市场查询获取。没有昨天的逐请求历史，不能确定供应商状态切换的精确时间，也不能证明所有其他市场永远没有独立问题。未修改 `.env`、数据库/Redis 数据、产品代码；未启停服务、未调用 LLM、未执行完整测试套件或浏览器门。当前应用仍停止。
