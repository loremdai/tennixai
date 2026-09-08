# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 13:41 CST

**当前任务：** T06 — Add the Bounded Async TTL Cache

**任务状态：** `in_progress`

**当前执行者 / ADE：** Claude Code（Codex Goal：完成 P1 T02–T15，顺序执行，不进 P2）

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `2ac24dd`

**最后验证的产品提交：** `16a0688`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T05 已完成（`16a0688`）：`LiveTennisProvider` + vendor DTO 边界（`livetennis_dtos.py` 全部 `extra="ignore"`）。player-major games → `SetScore` 转置、server 1/2 → 内部 ID、`upcoming/completed/cancelled/live` 与 `event_status` Postponed/Cancelled 映射、404/429(retry_after)/403/500 精确翻译、fixture 与 match 共用 identity 命名空间、null player ID 用 `fixture:{id}:p1|p2` 兜底、vendor 字段零泄漏有测试断言。全部确定性测试用 `httpx.MockTransport`，未调用真实 API。
- T04 已完成（`20735bd`）：五方法 `TennisDataProvider` Protocol 与 `FakeTennisProvider`（公开属性 `sinner_alcaraz` scheduled、`live_match` live Sinner vs Ruud）。
- T03 已完成（`5ed8a18`）：canonical models + `MemoryIdentityRepository`。T02 已完成（`8b15efe`）：FastAPI 基础。T01：10 张视觉基线（`c035f5a`）。
- 当前唯一主任务是 T06：实现 `backend/app/cache.py` 的 `AsyncTTLCache`（`CacheOutcome`、fresh/stale TTL 支持 value-based callable、in-flight coalescing、LRU 上限、注入 monotonic clock）；测试优先写 `tests/test_cache.py`。不实现 service、路由或前端。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

实现有界异步 TTL cache：`AsyncTTLCache.get_or_load(key, loader, *, ttl, stale_ttl)` 返回 `CacheOutcome(value, is_stale, age_seconds)`。行为：fresh 命中不触发 loader；并发相同 key 只调用一次 loader（coalescing）；loader 异常时若 `age <= stale_ttl` 返回标记 stale 的旧值，否则 re-raise；ttl/stale_ttl 支持按值 callable（空结果负缓存 30 秒）；超过 `max_entries` 时 LRU 驱逐。测试优先，注入数字 clock，不允许长 sleep。

### 为什么现在做

T07 TennisService 的全部缓存策略（live 60s/300s、upcoming 600s/1800s、player 3600s、空结果 30s）都构建在该 cache 之上；Free 供应商 100 次/日配额使请求行为成为正确性的一部分。

### 实施依据

- [P1 实施计划 — Task 6](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-6-add-the-bounded-async-ttl-cache)

### 预计变更范围

- `backend/app/cache.py`
- `backend/tests/test_cache.py`

### 完成门

- `uv run pytest tests/test_cache.py -v` 通过：fresh 命中、coalescing（并发 3 个请求仅 1 次 loader 调用）、stale fallback 与过期 re-raise、LRU 第 257 个 key 驱逐最旧、value-based TTL callable。
- 不实现 service、REST 路由、chat 或前端（属 T07+）。
- `ROADMAP.md` 的 T06 写入完成提交和验证证据；T07 变为 `ready`。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 6 的测试优先顺序实施，不扩大到 T07。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `16a0688` | `uv run pytest tests/test_livetennis_provider.py tests/test_provider_contract.py -v` 21/21；全套确定性 suite 32/32 | T05 验收通过（MockTransport，无真实网络） |
| 2026-09-08 | `20735bd` | `uv run pytest tests/test_provider_contract.py -v` 8/8；全套确定性 suite 19/19 | T04 验收通过 |
| 2026-09-08 | `5ed8a18` | `uv run pytest tests/test_domain.py tests/test_identity.py -v` 10/10；全套确定性 suite 11/11 | T03 验收通过 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T05 已由 Claude Code（Codex Goal）于 2026-09-08 完成并交接（提交 `16a0688`）；T06 可领取。

**交接说明：** `LiveTennisProvider` 构造为 keyword-only：`client`（httpx.AsyncClient，timeout 在 client 构造时设置）、`identities`、`api_key`、`now`。`get_score` 在缺少 match 上下文时会额外调用一次 `get_match` 填充 player 映射（T07/T08 注意配额影响）。`get_score` 对无 score 的 match 由 canonical 层处理；vendor DTO 解析失败统一翻译为 `provider_unavailable` 503。T06 的 cache 不依赖 provider，任何 loader 异常语义以计划 Task 6 代码为准（`asyncio.shield` + stale fallback）。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | T05 完成：LiveTennisAPI adapter 与 vendor DTO 边界 | `16a0688` |
| 2026-09-08 | 领取 T05 并置为 in_progress | `5069f14` |
| 2026-09-08 | T04 完成：provider contract 与确定性 FakeTennisProvider | `20735bd` |
| 2026-09-08 | 领取 T04 并置为 in_progress | `66c9526` |
| 2026-09-08 | T03 完成：canonical models 与进程内 identity | `5ed8a18` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
