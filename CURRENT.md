# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 13:57 CST

**当前任务：** T09 — Add Thin Next.js Route Handler Proxies

**任务状态：** `in_progress`

**当前执行者 / ADE：** Claude Code（Codex Goal：完成 P1 T02–T15，顺序执行，不进 P2）

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `3146bd8`

**最后验证的产品提交：** `039d144`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T08 已完成（`039d144`）：确定性 REST——`GET /api/v1/{health,players/search,matches,matches/{id}}`；统一错误信封 `{error:{code,message,details},request_id}`；422/404/409/503/429+Retry-After 精确映射；`create_app(settings, *, provider=None, chat_orchestrator=None)`（fake/live 装配、`TENNIX_FIXED_NOW` 共享 clock、live 模式 lifespan 管理 httpx client）。P1.2/P1.3 阶段门全部关闭。
- T07（`000ca1a`）：TennisService + 时间语义。T06（`6605ecb`）：AsyncTTLCache。T05（`16a0688`）：LiveTennisProvider。T04（`20735bd`）：Protocol + Fake。T03（`5ed8a18`）：canonical models + identity。T02（`8b15efe`）：FastAPI 基础。
- 当前唯一主任务是 T09：前端薄代理——`frontend/lib/server/backend-proxy.ts` + 四个 Route Handler（`/api/players/search`、`/api/matches`、`/api/matches/[matchId]`、`/api/chat/stream`），vitest 单测（mock fetch：SSE body 流原样透传、query 复制、429/Retry-After 保留、不转发 authorization/cookie、fetch 失败→502 internal_error、响应不含 backend base URL）。chat/stream 代理先建，后端 SSE 路由属 T11。改动前端必须跑 `pnpm test:e2e --grep prototype` 确认 10 张视觉基线不受影响。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

按计划 Task 9：安装 vitest/jsdom/@testing-library 等 dev 依赖并添加 `test`/`test:watch`/`typecheck` scripts；实现可复用 `proxyBackend(request, path)`（保留 status、content-type、cache-control、retry-after、x-request-id；SSE 不读 body 直接透传；`duplex:'half'` 流式转发；`TENNIX_BACKEND_URL` 缺失→500 internal_error；fetch 异常→502 internal_error）；四个 route 模块 `runtime='nodejs'`、`dynamic='force-dynamic'`，动态段用 `encodeURIComponent(matchId)`。测试优先：先写失败的 `backend-proxy.test.ts`。

### 为什么现在做

P1.1 exit gate 要求浏览器经同源代理访问后端且 SSE smoke 通过；T12–T14 前端全部经这四个代理路由消费后端。

### 实施依据

- [P1 实施计划 — Task 9](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-9-add-thin-nextjs-route-handler-proxies)

### 预计变更范围

- `frontend/package.json`、`frontend/pnpm-lock.yaml`、`frontend/vitest.config.ts`、`frontend/vitest.setup.ts`
- `frontend/lib/server/backend-proxy.ts`、`frontend/lib/server/backend-proxy.test.ts`
- `frontend/app/api/players/search/route.ts`、`frontend/app/api/matches/route.ts`、`frontend/app/api/matches/[matchId]/route.ts`、`frontend/app/api/chat/stream/route.ts`

### 完成门

- `pnpm test -- lib/server/backend-proxy.test.ts`、`pnpm typecheck`、`pnpm build` 全部通过。
- `pnpm test:e2e --grep prototype` 10/10 视觉基线不受影响（如有 diff 必须逐张审阅，不得盲目更新基线）。
- 代理不含业务逻辑、不做响应转换、无 CORS；响应不泄漏 backend base URL。
- `ROADMAP.md` 的 T09 写入完成提交和验证证据；T10 变为 `ready`。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 9 的测试优先顺序实施，不扩大到 T10。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `039d144` | `uv run pytest tests/test_api.py -v` 16/16；全套确定性 suite 75/75 | T08 验收通过 |
| 2026-09-08 | `000ca1a` | `uv run pytest tests/test_service.py tests/test_cache.py tests/test_provider_contract.py -v` 35/35；全套确定性 suite 59/59 | T07 验收通过 |
| 2026-09-08 | `6605ecb` | `uv run pytest tests/test_cache.py -v` 8/8；全套确定性 suite 40/40 | T06 验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T08 已由 Claude Code（Codex Goal）于 2026-09-08 完成并交接（提交 `039d144`）；T09 可领取。

**交接说明：** 后端契约已冻结：错误信封、`X-Request-ID` 语义、429 `Retry-After`、DTO 字段名（snake_case）都以 `backend/tests/test_api.py` 为准。T09 的 `/api/chat/stream` 代理可先行（后端 SSE 路由 T11 才实现），vitest 用 mock fetch 即可覆盖。frontend 尚无 vitest——T09 负责装上并建 `vitest.config.ts`/`vitest.setup.ts`；注意 jsdom 环境对 `Request`/`Response`/`ReadableStream` 的支持，需要时用 Node 原生对象（vitest environment 可选 node）。视觉基线在 `frontend/e2e/__screenshots__/`，任何前端改动先跑 `pnpm test:e2e`。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | T08 完成：确定性 REST API 与错误信封 | `039d144` |
| 2026-09-08 | 领取 T08 并置为 in_progress | `3ce1b86` |
| 2026-09-08 | T07 完成：TennisService 与时间语义 | `000ca1a` |
| 2026-09-08 | 领取 T07 并置为 in_progress | `573896c` |
| 2026-09-08 | T06 完成：bounded async TTL cache | `6605ecb` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
