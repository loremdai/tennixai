# TennixAI P1 本地运行手册

> P1（比赛信息查询助手）的本地启动、测试与 opt-in 真实集成命令。
> 架构与边界见 `PROJECT.md`；任务证据见 `ROADMAP.md`。

## 1. 启动本地栈

```bash
cd backend && cp .env.example .env
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && cp .env.example .env.local
cd frontend && pnpm dev --port 3100
```

- `backend/.env` 只存在于本地，绝不提交；变量名前缀 `TENNIX_`。
- `TENNIX_PROVIDER_MODE=fake|live`：fake 使用确定性 `FakeTennisProvider`；live 需要 `TENNIX_LIVETENNIS_API_KEY`。
- `TENNIX_LLM_MODE=fake|openai_compatible`：openai_compatible 需要 `TENNIX_LLM_API_KEY` 与 `TENNIX_LLM_BASE_URL`（模型默认 `qwen3.8-max-0902`）。`TENNIX_LLM_TIMEOUT_SECONDS` 默认为 45 秒，限制单次工具选择或流式说明的总时长，超时会保留结构化数据并返回固定降级说明。
- `TENNIX_FIXED_NOW`（可选，ISO8601 带时区）：冻结服务时钟，用于可重复的演示与视觉测试。
- 浏览器只访问 `http://127.0.0.1:3100`；`TENNIX_BACKEND_URL` 仅存在于 frontend 服务端环境（Route Handler 代理），浏览器bundle 不含后端地址或任何凭据。

## 2. 确定性验收（默认门）

```bash
cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live"
cd frontend && pnpm test && pnpm typecheck && pnpm build && pnpm test:e2e
```

- 后端：单元/契约/服务/API/chat/验收矩阵（fake provider + fake LLM）。
- 前端：vitest 单元、tsc、生产构建、Playwright（prototype 视觉基线 + P1 flow + P1 视觉基线）。
- 视觉基线位于 `frontend/e2e/__screenshots__/{desktop,mobile}/`；更新基线必须逐张审阅 diff，确认只是获准的数据文案变化。

## 3. Opt-in 真实集成门

```bash
cd backend && uv run pytest -m llm_live
cd backend && uv run pytest -m provider_live
cd backend && uv run pytest -m end_to_end_live
cd frontend && TENNIX_E2E_REAL_LLM=1 pnpm test:e2e llm-live.spec.ts
cd frontend && TENNIX_E2E_REAL_PROVIDER=1 TENNIX_E2E_REAL_LLM=1 pnpm test:e2e end-to-end-live.spec.ts
```

模式含义：

| 门 | 网球数据 | LLM | 缺凭据行为 |
|---|---|---|---|
| `llm_live` | fake | 真实 Qwen | pytest.skip |
| `provider_live` | 真实 LiveTennisAPI | 不涉及 | pytest.skip |
| `end_to_end_live` | 真实 LiveTennisAPI | 真实 Qwen | pytest.skip |
| `llm-live.spec.ts`（浏览器） | fake | 真实 Qwen | test.skip（需 `TENNIX_E2E_REAL_LLM=1`） |
| `end-to-end-live.spec.ts`（浏览器） | 真实 | 真实 | test.skip（需两个标志） |

- 运行前在 shell 中导出 `TENNIX_LLM_API_KEY` / `TENNIX_LLM_BASE_URL`（以及 provider 门需要的 `TENNIX_LIVETENNIS_API_KEY`）；Playwright 的 backend webServer 会继承这些变量；未设置真实凭据时 webServer 自动回退 fake 模式，不会启动失败。
- 真实 provider 受 Free 配额限制（100 请求/日、30 请求/分钟）；upcoming 使用 `/matches?status=upcoming`，Home 未指定球员时只读取供应商第一页，指定球员时使用供应商 `player` 过滤，不会无界分页；P1 无自动轮询，读取仅来自初始加载、手动刷新与提问。
- provider 返回 429 时，后端保留 `Retry-After`，前端显示配额暂时用完及重试间隔；重试必须由用户手动触发。

## 4. 路由与数据边界速查

- REST：`GET /api/v1/health|players/search|matches|matches/{id}`；Chat：`POST /api/v1/chat/stream`（SSE：status/data/text_delta/done/error）。
- 前端同源代理：`/api/players/search`、`/api/matches`、`/api/matches/[matchId]`、`/api/chat/stream`。
- 生产比赛路由 `/matches/[matchId]`（内部 ID）；`/match?status=` 仅为原型视觉预览（样例数据，页内标注“仅用于原型”）。
- 历史结果查询返回 typed `unsupported`（`P1 暂不支持历史比赛结果查询。`），不猜测。
- 业务工具仅三个：`find_player_matches`、`get_live_matches`、`get_match`；单轮最多两次工具调用。

## 5. 故障排查

| 症状 | 处理 |
|---|---|
| Home 显示 `比赛数据加载失败（code）` | 后端未启动或 provider 不可用；检查 `:8000/api/v1/health` 与 `.env`；点击“重试加载” |
| Home 只有 live 或 upcoming 一侧失败 | 这是局部降级；健康的一侧仍可用，失败分区会显示自己的 code 和“重试加载”按钮；检查对应 provider 请求，不要刷新整个页面循环重试 |
| Chat 显示数据服务配额暂时用完 | 等待 `Retry-After` 指定的时间后手动重试；不要通过分页或脚本连续探测 Free API |
| Match Page 显示 `比赛不存在或已失效` | 进程重启后内部 ID 失效；从 Home 重新进入比赛 |
| 视觉测试失败 | 查看 `frontend/test-results/` 下 diff；仅当确认是获准的数据文案变化才 `--update-snapshots` 并逐张审阅 |
| live 门 skip | 缺少对应凭据；属预期行为，不代表失败 |
