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
- `init` 是一次性准备：校验配置、创建并迁移专用回环库 `tennix_live_local`（Redis DB 11）、同步目录；缺失的中文名会在这一步**一次性**调用 LLM 补全（可能消耗 LLM 配额）。
- `up` 是日常启动：拉起 runtime/api/frontend 三个受管子进程，**绝不调用 LLM、绝不自动执行 init**。
- `down` 优雅停止自有子进程与本次启动的容器，**保留全部真实数据与 paper ledger**；再次 `up` 后 ID、数据与账本原样存在。

## 2. 健康语义（一句话版）

- **fresh**：连接开放且心跳确认，数据在预期窗口内——网球比分安静时保持 fresh，沉默不等于过期。
- **degraded**：低频任务失败但既有规范数据路径仍在（保留最近成功时间与计数）。
- **stale**：超过预期窗口没有任何新数据到达。
- **gap**：流序列出现断口；系统保留最后可信状态，并在 REST 对账成功前撤销新的 BUY/SELL 决策。

## 3. 正常事实状态（不是故障）

- **没有 live 比赛**：赛程安静时段属正常；实时源诚实报告 skip，绝不伪造成通过。
- **没有已映射市场**：Polymarket 上当前没有可精确映射的网球 moneyline 属正常。
- **模型未晋升**：未晋升模型只能输出事实性的 `NO BET` / `MARKET_ONLY`，属预期行为。

## 4. 真实核验 verify（受限、只读）

```bash
./scripts/tennix-live verify             # 不触碰 LLM
./scripts/tennix-live verify --with-llm  # 显式额外做一次真实 Chat 调用（消耗 LLM 配额）
```

- 每个源至多调用一次：ATP 排名、当前比赛目录、网球 WebSocket（仅当存在 live 比赛）、市场发现、盘口、公共市场 WebSocket（仅当存在活跃已映射盘口）；每次流接收等待以 45 秒为界。
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

回放（replay）流程、专用 live 测试门与 `NO_PROXY` 注意事项见 [p2-local.md](./p2-local.md)。
