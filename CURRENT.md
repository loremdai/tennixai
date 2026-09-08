# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 13:45 CST

**当前任务：** T07 — Implement TennisService and Time Semantics

**任务状态：** `in_progress`

**当前执行者 / ADE：** Claude Code（Codex Goal：完成 P1 T02–T15，顺序执行，不进 P2）

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `322bbed`

**最后验证的产品提交：** `6605ecb`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T06 已完成（`6605ecb`）：`AsyncTTLCache.get_or_load(key, loader, *, ttl, stale_ttl)` → `CacheOutcome(value, is_stale, age_seconds)`；in-flight coalescing、stale fallback、LRU 上限、value-based TTL callable（空结果负缓存）。
- T05 已完成（`16a0688`）：`LiveTennisProvider`（keyword-only：client/identities/api_key/now）+ permissive vendor DTO；错误精确翻译；fixture 与 match 共用 identity 命名空间；vendor 字段零泄漏有断言；全部 MockTransport。
- T04（`20735bd`）：`TennisDataProvider` Protocol + `FakeTennisProvider`（`sinner_alcaraz` scheduled 12:30Z、`live_match` live 10:00Z Sinner vs Ruud）。T03（`5ed8a18`）：canonical models + identity。T02（`8b15efe`）：FastAPI 基础。T01：视觉基线（`c035f5a`）。
- 当前唯一主任务是 T07：实现 `backend/app/service.py`——`MatchTimeScope`、`tonight_window()`、`TennisService`（player 解析/歧义、today/tonight/next 选择、缓存策略、stale 标记、`get_match` not_found 负缓存）；测试优先写 `tests/test_service.py`（clock 控制 + provider 调用计数）。不实现 REST 路由或前端。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

实现 TennisService 与时间语义：`tonight_window(now_local)`（<06:00 用前一晚 18:00 起的窗口；06:00–17:59 用当晚；≥18:00 用进行中窗口，均为 18:00–05:59）；`_resolve_player`（精确 case-insensitive 命中优先，多候选 `ambiguous_player` 409 附 candidates，零结果 `not_found` 404，空 query `invalid_request` 422）；`list_matches(status, player_name)`（live 60s/300s、upcoming 600s/1800s、空结果 30s/0）；`find_player_matches(player_name, time_scope)`（next=最早未来非终态一场、today=澳门当地日历日、tonight=窗口内；已过 scheduled_at 且非 live 的比赛排除）；`get_match(match_id)`（live 60s/300s、非 live 600s/1800s、None 负缓存 30s 后抛 not_found）；stale 结果在 `freshness` 上标记。

### 为什么现在做

T08 REST 与 T10 业务工具都必须只消费 TennisService；时间语义是服务规则而非 prompt 指令，必须有 clock 控制的确定性测试。

### 实施依据

- [P1 实施计划 — Task 7](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-7-implement-tennisservice-and-time-semantics)

### 预计变更范围

- `backend/app/service.py`
- `backend/tests/test_service.py`

### 完成门

- `uv run pytest tests/test_service.py tests/test_cache.py tests/test_provider_contract.py -v` 通过；provider 调用计数证明每条 TTL 与负缓存规则；tonight 三个参数化边界（02:00/12:00/20:00 +08:00）通过。
- 不实现 REST 路由、chat 或前端（属 T08+）。
- `ROADMAP.md` 的 T07 写入完成提交和验证证据；T08 变为 `ready`。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 7 的测试优先顺序实施，不扩大到 T08。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `6605ecb` | `uv run pytest tests/test_cache.py -v` 8/8；全套确定性 suite 40/40 | T06 验收通过 |
| 2026-09-08 | `16a0688` | `uv run pytest tests/test_livetennis_provider.py tests/test_provider_contract.py -v` 21/21；全套确定性 suite 32/32 | T05 验收通过（MockTransport，无真实网络） |
| 2026-09-08 | `20735bd` | `uv run pytest tests/test_provider_contract.py -v` 8/8；全套确定性 suite 19/19 | T04 验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T06 已由 Claude Code（Codex Goal）于 2026-09-08 完成并交接（提交 `6605ecb`）；T07 可领取。

**交接说明：** `AsyncTTLCache` 构造为 `(max_entries, now=monotonic)`，`get_or_load` 的 ttl/stale_ttl 均可为 value-based callable——T07 的 service 直接按计划 Task 7 的代码骨架实现即可，缓存 key 约定：`players:{casefold}`、`matches:{status}:{player_id|all}`、`match:{match_id}`。`FakeTennisProvider` 构造为 `(identities=..., now=...)`，可直接注入 service 测试并用包装类计数 provider 调用。fake 数据：scheduled Sinner vs Alcaraz 12:30Z；live Sinner vs Ruud 10:00Z；Djokovic 无比赛（可用于 honest-empty 断言）。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | T06 完成：bounded async TTL cache | `6605ecb` |
| 2026-09-08 | 领取 T06 并置为 in_progress | `d4939a3` |
| 2026-09-08 | T05 完成：LiveTennisAPI adapter 与 vendor DTO 边界 | `16a0688` |
| 2026-09-08 | 领取 T05 并置为 in_progress | `5069f14` |
| 2026-09-08 | T04 完成：provider contract 与确定性 FakeTennisProvider | `20735bd` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
