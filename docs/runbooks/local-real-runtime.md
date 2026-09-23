# TennixAI 本地真实运行手册（Local Real Runtime）

> P4.1 起，本地真实数据运行的唯一用户界面是仓库根目录的 `./scripts/tennix-live`。本手册覆盖日常启动、真实核验（verify）、浏览器验收与故障语义。回放（replay）验收与专用 live 测试门仍见 [p2-local.md](./p2-local.md)。

## 1. 用户流程

```text
1. Copy .env.example to .env and fill only the named real credentials.
2. Set provider mode to api_tennis and P3 mode to paper.
3. ./scripts/tennix-live init        # one-time preparation; may spend LLM quota for missing Chinese names
4. ./scripts/tennix-live up          # normal daily start; does not call the LLM
5. ./scripts/tennix-live status
6. ./scripts/tennix-live down        # preserves real data and paper ledger
```

- **只使用仓库根目录 `.env`**：不得创建或读取 `backend/.env`、`frontend/.env`、`frontend/.env.local`；凭据绝不提交、绝不写入日志。
- `init` 是一次性准备：校验配置、创建并迁移专用回环库 `tennix_live_local`（Redis DB 11）、同步目录；缺失的中文名会在这一步**一次性**调用 LLM 补全。该补全按 25 条一批循环到不再缺失，只要根 `.env` 配了 LLM 凭据就无法跳过，实测可能持续数十分钟并消耗可观配额——因此即使只是为了补一次 schema 迁移，也请把这一步的耗时与配额计入计划（`up` 会在库落后于已初始化 schema 时以 `LOCAL_SCHEMA_BEHIND` 拒绝启动，`init` 是唯一受支持的迁移入口）。
- `up` 是日常启动：拉起 runtime/api/frontend 三个受管子进程，**绝不调用 LLM、绝不自动执行 init**。
- `up` 直接运行仓库已安装的 `frontend/node_modules/.bin/next`；启动过程不调用 pnpm，也不会尝试重装或清理 `node_modules`。如果该文件不存在或不可执行，启动器会在拉起其他子进程前明确拒绝并提示先安装前端依赖。
- `down` 优雅停止自有子进程与本次启动的容器，**保留全部真实数据与 paper ledger**；再次 `up` 后 ID、数据与账本原样存在。

## 1.1 两条市场数据车道（P4.3）

| 车道 | 覆盖范围 | 数据来源 | 能做什么 |
|---|---|---|---|
| A — 全目录展示报价 | 全部活跃网球胜者 listing（`open`/`scheduled`，含未识别球员名/双打） | 一条独立只读市场 WebSocket 接收 `best_bid_ask`；REST `POST /books` 做启动/重连基线及每 120 秒校准 | 只更新页面展示报价与状态；不要求或伪造球员 ID；**绝不**触发预测、决策或 paper |
| B — 实时决策 | 严格映射 + ATP/WTA 主巡单打 + 在 tracking window 内（或已有未结持仓） | 公开市场 WebSocket + REST 对账 | 驱动 Prediction → Decision → paper ledger 与 Match 工作台 |

- 两条车道共享同一份 latest-quote projection 与同一条优先级规则（新值优先；同一时刻只允许实时车道覆盖快照车道，绝不反向）。
- 浏览器是否打开**不影响**后台采集：车道 A 由 runtime 进程按周期执行。
- 车道 A 的有界配置（根 `.env`）：

```text
TENNIX_LOCAL_RUNTIME_MARKET_SNAPSHOT_SECONDS=120        # 60–900
TENNIX_LOCAL_RUNTIME_MARKET_SNAPSHOT_MAX_MARKETS=500     # 1–500
TENNIX_LOCAL_RUNTIME_MARKET_SNAPSHOT_TOKEN_BATCH_SIZE=500 # 2–500（每批私有 token 数；CLOB 官方上限）
TENNIX_LOCAL_RUNTIME_MARKET_QUOTE_FRESH_SECONDS=300      # 120–1800（快照→过期阈值）
```

- 页面可见的报价状态（`/markets` 全部市场；`—` 只是某个缺失字段，从不是状态本身）：

| 状态 | 含义 |
|---|---|
| `realtime` | 实时盘口（fresh WebSocket 热盘口） |
| `snapshot` | 快照报价 · N 分钟前 |
| `partial` | 部分报价 · N 分钟前（仅一侧有可显示档位） |
| `no_liquidity` | 暂无挂单（响应可信但两侧都没有可显示档位） |
| `unavailable` | 报价暂不可用（本轮请求/解析失败且无可用旧值） |
| `stale` | 最后可信报价已过期 |
| `limited` | 覆盖受限 · 等待下一轮（受保护上限未轮到，保留上次报价与时间） |

## 2. 健康语义（一句话版）

- **fresh**：连接开放且心跳确认，数据在预期窗口内——网球比分安静时保持 fresh，沉默不等于过期。
- **degraded**：低频任务失败但既有规范数据路径仍在（保留最近成功时间与计数）。
- **stale**：超过预期窗口没有任何新数据到达。
- **gap**：流序列出现断口；系统保留最后可信状态，并在 REST 对账成功前撤销新的 BUY/SELL 决策。
- **market coverage**：`runtime/health` 的 `market_coverage` 只含聚合数字——candidate/attempted、各报价状态计数、batch_failures、rate_limited/retry_after_until 与 last_successful_batch_at；不含 token、URL 或 provider ID。

## 3. 正常事实状态（不是故障）

- **没有 live 比赛**：赛程安静时段属正常；实时源诚实报告 skip，绝不伪造成通过。
- **没有已映射市场**：Polymarket 上当前没有可精确映射的网球 moneyline 属正常。
- **模型未晋升**：未晋升模型只能输出事实性的 `NO BET` / `MARKET_ONLY`，属预期行为；`/markets` 的「机会」会明确说明「模型尚未完成验证，当前不生成 BUY / WAIT」，而不是把空标签页伪装成故障。
- **低级别市场**（Challenger/ITF）：展示真实报价，但不带「模型未覆盖」之类的负向标签，也不进入模型建议。
- **没有挂单**：真实市场在冷门时段可以两侧皆无挂单（`no_liquidity`），这是有效结果。
- **429 / 退避**：CLOB 限流时本轮标记 degraded 并尊重 `Retry-After`；`market_coverage.rate_limited` 与 `retry_after_until` 会如实反映，不忙等重试。

## 4. 真实核验 verify（受限、只读）

```bash
./scripts/tennix-live verify             # 不触碰 LLM
./scripts/tennix-live verify --with-llm  # 显式额外做一次真实 Chat 调用（消耗 LLM 配额）
```

- 每个源至多调用一次：ATP 排名、当前比赛目录、网球 WebSocket（仅当存在 live 比赛）、市场发现、盘口、公共市场 WebSocket（仅当存在活跃已映射盘口）、批量报价快照（`market_quote_snapshot`，至多 2 个已映射市场的私有 token 组成**一次** `POST /books`）；每次流接收等待以 45 秒为界。
- `market_quote_snapshot` 的诚实结果：无已映射 token → `skipped · NO_QUOTE_TARGETS`；批量响应无可解析盘口 → `skipped · EMPTY_RESULT`；限流/网络失败 → `failed` + 稳定 reason code（如 `RATE_LIMITED`）。
- 输出只含名称/状态/稳定 reason code，绝不含 provider ID、密钥、URL query 或原始载荷。
- 退出码：任一源 `failed` → 非零；全部 `passed` 或 `passed`+`skipped` 混合 → 0，且 skip 会逐条明确打印。**安静窗口的 skip 永远不算通过。**
- verify 绝不写入比赛 fixture、绝不下单、绝不动 paper ledger；没有 `--with-llm` 时甚至不构造 LLM 客户端。
- 配置不完整时以稳定的前置条件码退出（如 `LOCAL_P3_MODE_INVALID`），不会打印任何秘密值。

对应的自动化门（默认全部跳过，零外部配额）：

```bash
cd backend
TENNIX_RUN_LOCAL_RUNTIME_VERIFY=1 uv run pytest -m local_runtime_live \
  tests/live/test_local_runtime_verify.py -v
# 额外真实 LLM 门需同时设置 TENNIX_RUN_LLM_LIVE=1
```

## 5. 浏览器验收（opt-in）

前置：`./scripts/tennix-live up` 已在运行（默认前端 `http://127.0.0.1:3100`）。

```bash
cd frontend
TENNIX_E2E_LOCAL_RUNTIME=1 pnpm exec playwright test e2e/local-real-runtime.spec.ts
# 前端不在默认端口时：
TENNIX_E2E_LOCAL_RUNTIME=1 \
TENNIX_E2E_LOCAL_RUNTIME_URL=http://127.0.0.1:3100 \
  pnpm exec playwright test e2e/local-real-runtime.spec.ts
```

验收内容：Home 呈现真实目录数据或获批的诚实空态；Players 呈现英文主名/中文副名或诚实覆盖状态；比赛与市场页面不含任何预览原型文案；Decision Workbench 保持 paper-only、无交易 CTA；DOM 与同源 JSON 响应不含 provider 外部 ID/token/密钥模式。不假设存在 live 比赛或 BUY 动作。

## 6. 故障排查

| 现象 | 处理 |
|---|---|
| `verify` 以前置条件码退出 | 按提示补全根 `.env`（provider mode、P3 mode、凭据、`TENNIX_LOCAL_RUNTIME_*`），重跑 `init` |
| `verify` 某源 `failed` | reason code 即稳定分类；先查 `./scripts/tennix-live logs runtime`，再确认网络与凭据 |
| 全部源 `skipped` | 多为安静窗口（无 live 比赛/无映射市场），属诚实结果；换个时间重跑 |
| 浏览器验收失败于 preview 标记 | 确认访问的是无 `?preview=` 参数的生产页面且前端由 launcher 启动 |
| 数据库连不上 | 确认 compose 的 postgres 在跑且已执行过 `./scripts/tennix-live init` |
| `up refused: LOCAL_SCHEMA_BEHIND` / `LOCAL_NOT_INITIALIZED` | 库或 launcher 状态落后于已初始化 schema：重跑 `init`（含上面的 LLM 补名，见 §1）。中断过 `init` 时状态文件可能被重置，`status` 会同时显示两者 |

回放（replay）流程与专用 live 测试门见 [p2-local.md](./p2-local.md)。
