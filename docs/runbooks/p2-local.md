# TennixAI P2 本地运行手册

> P2（实时比赛智能）的回放验收、真实集成门与故障排查。产品边界见 `PROJECT.md`，阶段证据见 `ROADMAP.md`。

## 1. 启动确定性 Replay

Replay 只替换上游 provider；身份归一化、PostgreSQL 快照、Redis demand/lease、reducer、SSE 和前端页面都走生产路径。fixture 是脱敏 JSONL，包含首帧、逐分、重复、统计、修正、断线、REST reconcile 和完赛事件。

先启动基础设施并完成迁移：

```bash
docker compose up -d --wait postgres redis
cd backend && uv run alembic upgrade head
```

终端一启动后端（Replay 使用独立身份 namespace，避免旧回放污染当前运行）：

```bash
cd backend
env -u NO_PROXY -u no_proxy \
  TENNIX_PROVIDER_MODE=replay \
  TENNIX_LLM_MODE=fake \
  TENNIX_REPLAY_SPEED=1 \
  TENNIX_REPLAY_IDENTITY_NAMESPACE=p2-local-$(date +%s) \
  TENNIX_REDIS_URL=redis://127.0.0.1:6379/10 \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另一终端启动前端：

```bash
cd frontend
TENNIX_BACKEND_URL=http://127.0.0.1:8000 pnpm dev --hostname 127.0.0.1 --port 3100
```

浏览器只访问 `http://127.0.0.1:3100`。根目录 `.env` 仍是唯一人工配置入口；不要创建 `backend/.env`、`frontend/.env` 或 `frontend/.env.local`。本地 compose Redis 配置为 16 个库（0–15），不要使用 16 及以上的数据库编号。

`NO_PROXY`/`no_proxy` 若含有形如 `:1` 的坏值，会让 OpenAI/httpx 初始化失败；本地命令使用上面的 `env -u`，不要把修复后的环境值写入代码或日志。

## 2. Replay Playwright 验收

功能流覆盖 Home 默认筛选、比赛页实时比分/统计/PBP、重复与修正、断线恢复、第二浏览器上下文、聊天版本过期、隐藏 60 秒释放/恢复和完赛终态；视觉流覆盖 1440×1000 与 390×844。

```bash
cd frontend
TENNIX_E2E_REPLAY=1 \
TENNIX_E2E_REDIS_URL=redis://127.0.0.1:6379/10 \
TENNIX_REPLAY_SPEED=1 \
pnpm exec playwright test p2-realtime.spec.ts

# Start a fresh Playwright process so the finite fixture starts at its first event again.
TENNIX_E2E_REPLAY=1 \
TENNIX_E2E_REDIS_URL=redis://127.0.0.1:6379/10 \
TENNIX_REPLAY_SPEED=1 \
pnpm exec playwright test p2.visual.spec.ts
```

只有确认获准的界面变化后才更新基线：

```bash
TENNIX_E2E_REPLAY=1 \
TENNIX_E2E_REDIS_URL=redis://127.0.0.1:6379/10 \
TENNIX_REPLAY_SPEED=0.25 \
pnpm exec playwright test p2.visual.spec.ts --update-snapshots --workers=1
```

更新后逐张审阅 `frontend/e2e/__screenshots__/{desktop,mobile}/p2-*.png`，并运行一次不带 `--update-snapshots` 的视觉测试。

## 3. 确定性全量门

```bash
cd backend && env -u NO_PROXY -u no_proxy uv run pytest -m "not api_tennis_live and not realtime_live and not llm_live and not end_to_end_live and not provider_live" -q
cd frontend && pnpm test && pnpm typecheck && pnpm build && pnpm test:e2e
```

Replay 专项后端门：

```bash
cd backend && env -u NO_PROXY -u no_proxy uv run pytest tests/test_replay_provider.py tests/integration/test_realtime_recovery.py tests/test_realtime_worker.py tests/test_match_stream_api.py -q
```

## 4. Opt-in 真实门

```bash
cd backend && env -u NO_PROXY -u no_proxy TENNIX_RUN_API_TENNIS_LIVE=1 \
  uv run pytest -m api_tennis_live tests/live/test_api_tennis_live.py -q
cd backend && env -u NO_PROXY -u no_proxy TENNIX_RUN_API_TENNIS_LIVE=1 \
  uv run pytest -m realtime_live tests/live/test_api_tennis_websocket_live.py -q
cd backend && env -u NO_PROXY -u no_proxy TENNIX_RUN_LLM_LIVE=1 uv run pytest -m llm_live
cd backend && env -u NO_PROXY -u no_proxy uv run pytest -m provider_live
cd backend && env -u NO_PROXY -u no_proxy uv run pytest -m end_to_end_live
cd frontend && TENNIX_E2E_REAL_LLM=1 pnpm exec playwright test llm-live.spec.ts
cd frontend && TENNIX_E2E_REAL_PROVIDER=1 TENNIX_E2E_REAL_LLM=1 pnpm exec playwright test end-to-end-live.spec.ts
```

真实门缺少凭据时按测试标记 skip；provider 或模型供应商拒绝当前账号时记录 HTTP 状态与错误码，不打印 key，也不把真实响应写入 fixture。P2 不包含赔率、预测、edge、交易或市场写入。

## 5. P2.6 球员目录本地门

基础设施与迁移同 §1；目录同步与中文 enrichment 都是**本地显式执行**的命令，真实 API 启动不会自动同步，也不存在 cron/队列/daemon。

```bash
docker compose up -d --wait postgres redis
cd backend && uv run alembic upgrade head
```

正常启动（fake 模式，确定性）：

```bash
cd backend && uv run uvicorn app.main:app --host 127.0.0.1:8000   # 根 .env 决定模式
cd frontend && TENNIX_BACKEND_URL=http://127.0.0.1:8000 pnpm dev --hostname 127.0.0.1:3100
```

真实目录同步与中文 enrichment（**配额敏感**：sync 每次调用供应商 standings 两次；enrich-zh 只对缺失中文名的成员调用 LLM，重复运行零模型调用）：

```bash
cd backend
uv run python -m app.players.cli sync
uv run python -m app.players.cli enrich-zh --batch-size 25
uv run python -m app.players.cli status
```

`status` 报告两 tour、可发布成员的英文/中文首选名覆盖率；batch 校验失败时整批零写入，重跑安全。

确定性门（含目录单测与 integration）：

```bash
cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure and not player_alias_llm_live and not player_directory_e2e_live" -q
cd backend && uv run pytest -m infrastructure -q
cd frontend && pnpm test && pnpm typecheck && pnpm build
cd frontend && pnpm test:e2e --grep "player directory"        # 功能 + 四张 v0 基线（不更新）
```

Opt-in 真实目录门（凭据缺失即 skip，不以 skip 充数）：

```bash
cd backend && TENNIX_RUN_API_TENNIS_LIVE=1 uv run pytest -m api_tennis_live -q
cd backend && TENNIX_RUN_PLAYER_ALIAS_LLM_LIVE=1 uv run pytest -m player_alias_llm_live -q
cd backend && TENNIX_RUN_PLAYER_DIRECTORY_E2E_LIVE=1 uv run pytest -m player_directory_e2e_live tests/live/test_player_directory_end_to_end_live.py -q
cd frontend && TENNIX_E2E_API_TENNIS=1 TENNIX_E2E_REAL_LLM=1 pnpm exec playwright test e2e/player-directory-live.spec.ts
```

`TENNIX_E2E_API_TENNIS=1` 会让 Playwright 以 `TENNIX_PROVIDER_MODE=api_tennis` 启动独立后端（不复用已有 fake 服务）；浏览器旅程与 payload 检查只允许内部 ID，禁止供应商 key/外部 ID 出现在网络响应中。

## 6. 故障排查

| 症状 | 处理 |
|---|---|
| Replay 首页为空 | 确认 `TENNIX_PROVIDER_MODE=replay`、fixture 路径相对 backend 根目录有效，并从 Home 重新进入比赛。 |
| Match 页请求 500，Redis 报 `DB index is out of range` | 使用 0–15 的 Redis 库；默认回放命令使用 DB 10。 |
| Match 页只有首帧没有增量 | 检查 Redis 连接是否使用 `decode_responses=True`；确认后端启动日志无 worker 异常。 |
| 页面显示“实时连接恢复中” | Replay 正在执行断线与 REST reconcile；页面保留最后可信快照，恢复后会显示已同步状态。 |
| PBP 出现“数据已校准” | 这是 fixture 的供应商修正事件，表示旧 point identity 被同一 canonical point 的新 revision 替换。 |
| 页面显示 `llm_unavailable` | Replay 手动/Playwright 应设置 `TENNIX_LLM_MODE=fake`；真实 LLM 门则记录外部 entitlement/HTTP 错误并保持凭据不外泄。 |
| 页面显示“比赛不存在或已失效” | 进程重启后应使用新的 Replay identity namespace，从 Home 重新进入，不复用旧的内部 match ID。 |
