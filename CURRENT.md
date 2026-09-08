# TennixAI 当前进展

> 本文件是唯一执行面板，回答“现在只做什么、由谁做、从哪里继续、怎样算完成”。
> 项目定位见 [PROJECT.md](./PROJECT.md)，全局路线见 [ROADMAP.md](./ROADMAP.md)。

**最后更新：** 2026-09-08 13:31 CST

**当前任务：** T04 — Add the Provider Contract and Deterministic Fake

**任务状态：** `in_progress`

**当前执行者 / ADE：** Claude Code（Codex Goal：完成 P1 T02–T15，顺序执行，不进 P2）

**工作分支：** `main`（P1 默认唯一执行与同步分支）

**任务起始提交：** `c025b9b`

**最后验证的产品提交：** `5ed8a18`

**远程：** `origin` → `https://github.com/loremdai/tennixai.git`

## 60 秒恢复

- T03 已完成（`5ed8a18`）：`backend/app/domain.py` 七个 canonical models + `MatchStatus` 枚举（frozen、extra=forbid、UTC 校验），`backend/app/identity.py` 进程内 `MemoryIdentityRepository`（mat_/ply_/trn_ 前缀，可逆映射，内部 ID 不含外部 ID）。
- T02 已完成（`8b15efe`）：FastAPI 基础——typed `Settings`、`AppError`、`GET /api/v1/health`、`X-Request-ID` 中间件、`create_app()` 工厂、uv/pytest 骨架。
- T01 已完成：Home 与 Match 三态在桌面/移动视口的 10 张视觉基线已入 Git（最终版 `c035f5a`），visual suite 可重复通过。历史提醒：首版基线 `d13d6dd` 混入 Next dev overlay，done 曾于 `c37ad36` 回退；最终版隐藏 `nextjs-portal` 后重建。
- 当前唯一主任务是 T04：定义 `TennisDataProvider` 五方法 async protocol（`backend/app/providers/base.py`）与确定性 `FakeTennisProvider`（`backend/app/providers/fake.py`），先写失败的 contract 测试。不实现 LiveTennisAPI adapter、cache、service 或路由。
- 当前没有产品阻塞项。
- 未跟踪文件：`.codex/skills/ui-ux-pro-max/SKILL.md`（任务外）、`frontend/AGENTS.md` 与 `frontend/CLAUDE.md`（next dev 自动生成的 agent 提示文件）、`frontend/next-env.d.ts`（Next 工具链生成）；一律保留，不得顺手提交或删除。

## 当前任务

### 目标

建立 provider contract 与确定性 fake：`TennisDataProvider` Protocol（`get_live_matches`、`get_fixtures`、`search_players`、`get_match`、`get_score`）与 `FakeTennisProvider`（固定 Sinner/Alcaraz/Djokovic/Ruud 数据：一场 2026-09-08T12:30Z scheduled、一场 10:00Z live 6–4/4–6/4–5、points 30–15、Sinner 发球；大小写不敏感子串搜索；unknown ID 抛 `AppError("not_found", ..., 404)`）。测试优先：先写失败的 `tests/test_provider_contract.py`。

### 为什么现在做

T05 live adapter 与 T07 service 都以该 protocol 为唯一 provider 边界；fake 是之后所有确定性测试与 E2E 的数据来源。

### 实施依据

- [P1 实施计划 — Task 4](./docs/superpowers/plans/2026-09-08-tennixai-p1-implementation.md#task-4-add-the-provider-contract-and-deterministic-fake)

### 预计变更范围

- `backend/app/providers/__init__.py`、`backend/app/providers/base.py`、`backend/app/providers/fake.py`
- `backend/tests/test_provider_contract.py`

### 完成门

- `uv run pytest tests/test_provider_contract.py -v` 通过：五个 protocol 方法全部被行使，返回值均为 canonical models，公共 ID 不含 `fake-` 外部 ID。
- 不实现 LiveTennisAPI adapter、cache、service、路由或前端（属 T05+）。
- `ROADMAP.md` 的 T04 写入完成提交和验证证据；T05 变为 `ready`。

## 下一步操作

1. 执行者先运行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`，确认本文件与仓库一致。
2. 保持在 `main`，写入执行者/ADE、任务起始 HEAD 和更新时间，将状态改为 `in_progress`。
3. 仅提交并推送该次任务领取更新到 `origin/main`；不要包含现有未跟踪的 `.codex/` 与 next 生成文件。
4. 按 Task 4 的测试优先顺序实施，不扩大到 T05。

## 最近验证

| 日期 | 提交 | 验证 | 结果 |
|---|---|---|---|
| 2026-09-08 | `5ed8a18` | `uv run pytest tests/test_domain.py tests/test_identity.py -v` 10/10；全套确定性 suite 11/11 | T03 验收通过 |
| 2026-09-08 | `8b15efe` | `uv run pytest tests/test_health.py -v` 1/1（health 200 + `X-Request-ID` 透传）；`Settings(_env_file=None).llm_model` 输出 `qwen3.8-max-0902` | T02 验收通过 |
| 2026-09-08 | `c035f5a` | `pnpm test:e2e:update` 10/10 重建基线 → 连续两次 plain `pnpm test:e2e` 各 10/10；`pnpm build` exit 0；10 张 PNG 逐张审阅 | T01 验收通过：基线可重复 |

任务完成前必须把实际运行的命令、结果和对应提交补充到这里。未运行或失败的验收不能写成通过。

## 最近交接

**状态：** T03 已由 Claude Code（Codex Goal）于 2026-09-08 完成并交接（提交 `5ed8a18`）；T04 可领取。

**交接说明：** 领域模型全部 frozen + `extra="forbid"`，`Match.players` 是 `tuple[Player, Player]`，`MatchScore.sets` 是 `tuple[SetScore, ...]`；fake provider 构造数据时必须提供 timezone-aware datetime。`MemoryIdentityRepository.get_or_create(entity, provider, external_id)` 的 entity 仅支持 `match`/`player`/`tournament`。`create_app()` 仍只接受 `Settings`，T08 才扩展注入参数。

**已知本地状态：** 未跟踪的 `.codex/skills/ui-ux-pro-max/SKILL.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`（next dev 生成）、`frontend/next-env.d.ts`（Next 工具链生成），保留原样。

**阻塞：** 无。

## 近期变更（最多 5 条）

| 日期 | 变更 | 提交 |
|---|---|---|
| 2026-09-08 | T03 完成：canonical models 与进程内 identity | `5ed8a18` |
| 2026-09-08 | 领取 T03 并置为 in_progress | `5104e71` |
| 2026-09-08 | T02 完成：FastAPI 基础（settings/errors/health/request-ID/app 工厂/pytest 骨架） | `8b15efe` |
| 2026-09-08 | 领取 T02 并置为 in_progress | `3686444` |
| 2026-09-08 | 排除 dev overlay 并重建最终视觉基线，T01 完成交接 | `c035f5a` |

## 接手与更新规则

- 同时只允许一个 `in_progress` 主任务。
- P1 默认直接在 `main` 领取、执行和交接。只有用户明确批准隔离实验或并行工作时才创建分支，并且必须先把分支信息提交到 `origin/main`。
- 当前任务占用不自动过期；接手必须先核对 Git、保留已有成果并显式改写执行者与交接说明。
- 有任务内未提交改动时不得跨 ADE 接手；无法确认改动归属时停下询问用户。
- 开始、完成可验证节点、阻塞或交接时更新本文件。
- 完成、阻塞或交接时，提交并推送全部任务内已验证成果与总控更新；不得顺带提交任务外改动。
- 本文件只保留当前任务、最近一次交接和最多 5 条近期变更；长期证据进入 `ROADMAP.md`，完整历史由 Git 保存。
