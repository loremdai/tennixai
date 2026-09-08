# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 13:50 CST

**当前任务：** T08 — Expose Deterministic REST APIs

**任务状态：** `ready`

**当前执行者 / ADE：** `unassigned`

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `unassigned`（领取任务时记录当时的 HEAD）

**最后验证的产品提交：** `000ca1a`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T07 已完成（`000ca1a`）：`TennisService`（provider, cache, now, timezone 构造）+ `MatchTimeScope` + `tonight_window()`；player 解析（精确优先/歧义 409/not_found 404/空 query 422）、today/tonight/next 规则、全部 TTL/stale/负缓存策略经 provider 调用计数证明。
- T06 已完成（`6605ecb`）：`AsyncTTLCache`。T05（`16a0688`）：`LiveTennisProvider`（client/identities/api_key/now keyword-only）。T04（`20735bd`）：Protocol + `FakeTennisProvider`。T03（`5ed8a18`）：canonical models + identity。T02（`8b15efe`）：FastAPI 基础（`create_app()` 目前只接受 `Settings`）。
- 当前唯一主任务是 T08：暴露确定性 REST——`app/api/schemas.py`（PlayerListResponse/MatchListResponse/MatchResponse/ErrorResponse 信封）、扩展 `create_app(settings, *, provider=None, chat_orchestrator=None)`（fake/live 模式装配、lifespan 管理 httpx client、`TENNIX_FIXED_NOW` 共享 clock）、`GET /players/search?q=`、`GET /matches?status=&player=`、`GET /matches/{match_id}`、AppError/RequestValidationError 异常处理器（错误信封含 request_id）。测试优先写 `tests/conftest.py` + `tests/test_api.py`。不实现 chat 路由（T11）或前端代理（T09）。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

按计划 Task 8 实现 REST：所有 P1 事实问题不经 LLM 可回答；错误统一信封 `{"error": {"code","message","details"}, "request_id"}`；`invalid_request` 422、`not_found` 404、`ambiguous_player` 409、`rate_limited` 429 + `Retry-After`、provider 错误 503；响应零供应商外部 ID/凭据泄漏；`X-Request-ID` 生成与透传；fake 模式默认 `FakeTennisProvider` + `TENNIX_FIXED_NOW` 固定时钟，live 模式 lifespan 管理单个 `httpx.AsyncClient(timeout=10.0)`。

### 为什么现在做

T09 前端薄代理与 T12 typed client 需要稳定的 REST 契约；P1.3 exit gate 要求所有事实问题可经 REST 回答且边界错误有确定性测试。

### 实施依据

- [P1 实施计划 — Task 8](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-8-expose-deterministic-rest-apis)

### 预计变更范围

- `backend/app/api/schemas.py`、`backend/app/api/routes.py`、`backend/app/main.py`
- `backend/tests/conftest.py`、`backend/tests/test_api.py`

### 完成门

- `uv run pytest -m "not llm_live and not provider_live and not end_to_end_live" -v` 全部通过；响应文本无 `external_id`、`fake-` 前缀或凭据。
- 不实现 chat/SSE（T10–T11）或前端（T09/T12+）。
- `ROADMAP.md` 的 T08 写入完成提交和验证证据；T09 变为 `ready`。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 8 的测试优先顺序实施，不扩大到 T09。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `000ca1a` | `uv run pytest tests/test_service.py tests/test_cache.py tests/test_provider_contract.py -v` 35/35；全套确定性 suite 59/59 | T07 验收通过 |
| 2026-09-08 | `6605ecb` | `uv run pytest tests/test_cache.py -v` 8/8；全套确定性 suite 40/40 | T06 验收通过 |
| 2026-09-08 | `16a0688` | `uv run pytest tests/test_livetennis_provider.py tests/test_provider_contract.py -v` 21/21；全套确定性 suite 32/32 | T05 验收通过（MockTransport） |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T07 已由 Claude Code（Codex Goal）于 2026-09-08 完成并交接（提交 `000ca1a`）；T08 可领取。

**交接说明：** `TennisService` 构造顺序为 `(provider, cache, now, timezone)`；缓存 key：`players:{casefold}`、`matches:{status}:{player_id|all}`、`match:{match_id}`。T08 装配时 fake 模式必须把同一个 clock（`TENNIX_FIXED_NOW` 或实时 UTC）同时注入 `FakeTennisProvider(identities=..., now=...)` 与 `TennisService`。`create_app` 需保持向后兼容 T02 的 `create_app(Settings(_env_file=None))` 调用（tests/test_health.py 依赖）。异常处理器要把 FastAPI `RequestValidationError` 翻译为 `invalid_request` 422 信封；`request_id` 从 `request.state.request_id` 读取。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | T07 完成：TennisService 与时间语义 | `000ca1a` |
| 2026-09-08 | 领取 T07 并置为 in_progress | `573896c` |
| 2026-09-08 | T06 完成：bounded async TTL cache | `6605ecb` |
| 2026-09-08 | 领取 T06 并置为 in_progress | `d4939a3` |
| 2026-09-08 | T05 完成：LiveTennisAPI adapter 与 vendor DTO 边界 | `16a0688` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
