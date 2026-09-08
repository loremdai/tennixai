# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 13:35 CST

**当前任务：** T05 — Implement the LiveTennisAPI Adapter

**任务状态：** `in_progress`

**当前执行者 / ADE：** Claude Code（Codex Goal：完成 P1 T02–T15，顺序执行，不进 P2）

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `fa12d8b`

**最后验证的产品提交：** `20735bd`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T04 已完成（`20735bd`）：`TennisDataProvider` 五方法 async Protocol（`backend/app/providers/base.py`）与确定性 `FakeTennisProvider`（`backend/app/providers/fake.py`）——scheduled Sinner vs Alcaraz（12:30Z，Semifinal/hard/indoor/BO3）、live Sinner vs Ruud（10:00Z，sets 6–4/4–6/4–5，points 30–15，Sinner 发球）、4 名球员可搜索、unknown ID 抛 `AppError("not_found", ..., 404)`。
- T03 已完成（`5ed8a18`）：七个 canonical models + `MatchStatus`（frozen、extra=forbid、UTC 校验）与 `MemoryIdentityRepository`（mat_/ply_/trn_，可逆，内部 ID 不含外部 ID）。
- T02 已完成（`8b15efe`）：FastAPI 基础（typed Settings、AppError、health、X-Request-ID、create_app、uv/pytest 骨架）。
- T01 已完成：10 张视觉基线入 Git（`c035f5a`），visual suite 可重复通过。
- 当前唯一主任务是 T05：实现 `LiveTennisProvider`（vendor DTO 边界 `livetennis_dtos.py` + HTTP adapter `livetennis.py`），用 `httpx.MockTransport` 与录制的 sanitized fixtures 做确定性测试；不调用真实 API（真实调用属 T15 opt-in gate）。不实现 cache、service 或路由。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

实现 LiveTennisAPI adapter：permissive vendor DTOs（`extra="ignore"`：`LivePlayerDto`、`LiveScoreDto`、`LiveMatchDto`、`LiveFixtureDto`、`ListResponse[T]`）、player-major games → `SetScore` 行转置、server `1/2` → 内部 player ID、`completed`→`finished`、`Postponed`→`postponed`、null 时间保持 `None`、`X-API-Key` 认证、精确错误翻译（404→not_found、429→rate_limited+retry_after、403→provider_unavailable 503、≥400→provider_unavailable 503）、fixture ID 映射进同一 match identity 命名空间、`/fixtures` 本地按 player 过滤。测试优先：先写 `tests/fixtures/livetennis/*.json` 与失败的 `tests/test_livetennis_provider.py`。

### 为什么现在做

P1 唯一真实数据源是 LiveTennisAPI Free；adapter 是供应商字段的终止边界，之后 service/REST/chat 只消费 canonical models。

### 实施依据

- [P1 实施计划 — Task 5](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-5-implement-the-livetennisapi-adapter)

### 预计变更范围

- `backend/app/providers/livetennis_dtos.py`、`backend/app/providers/livetennis.py`
- `backend/tests/fixtures/livetennis/{players,fixtures,matches_live,match_detail,score}.json`
- `backend/tests/test_livetennis_provider.py`

### 完成门

- `uv run pytest tests/test_livetennis_provider.py tests/test_provider_contract.py -v` 通过：含 `X-API-Key`、query 参数、转置、null、unknown-field、404/429/403 断言；不调用真实网络。
- 供应商字段（`event_key`、`event_first_player`、`score[0][1]` 等）不出现在 canonical 输出。
- 不实现 cache、service、路由或前端（属 T06+）。
- `ROADMAP.md` 的 T05 写入完成提交和验证证据；T06 变为 `ready`。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 5 的测试优先顺序实施，不扩大到 T06。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `20735bd` | `uv run pytest tests/test_provider_contract.py -v` 8/8；全套确定性 suite 19/19 | T04 验收通过 |
| 2026-09-08 | `5ed8a18` | `uv run pytest tests/test_domain.py tests/test_identity.py -v` 10/10；全套确定性 suite 11/11 | T03 验收通过 |
| 2026-09-08 | `8b15efe` | `uv run pytest tests/test_health.py -v` 1/1（health 200 + `X-Request-ID` 透传）；`Settings(_env_file=None).llm_model` 输出 `qwen3.8-max-0902` | T02 验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T04 已由 Claude Code（Codex Goal）于 2026-09-08 完成并交接（提交 `20735bd`）；T05 可领取。

**交接说明：** fake provider 的公开属性为 `sinner_alcaraz`（scheduled）与 `live_match`（live，Sinner vs Ruud）；外部 ID 命名空间为 `fake-*`。T05 的 LiveTennisProvider 构造签名：注入一个 `httpx.AsyncClient`（10 秒 timeout 在 client 构造时设置）、`MemoryIdentityRepository` 与 UTC clock；live provider 的 identity provider 名用 `"livetennis"`，fixture 与 match 必须映射进同一 match 命名空间。真实网络调用只允许出现在 `provider_live`/`end_to_end_live` 标记测试（T15），T05 全部用 `httpx.MockTransport`。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | T04 完成：provider contract 与确定性 FakeTennisProvider | `20735bd` |
| 2026-09-08 | 领取 T04 并置为 in_progress | `66c9526` |
| 2026-09-08 | T03 完成：canonical models 与进程内 identity | `5ed8a18` |
| 2026-09-08 | 领取 T03 并置为 in_progress | `5104e71` |
| 2026-09-08 | T02 完成：FastAPI 基础 | `8b15efe` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
