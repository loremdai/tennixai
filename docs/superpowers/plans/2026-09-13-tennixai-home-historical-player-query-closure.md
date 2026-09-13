# TennixAI Home Historical Player Query Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完整关闭 T54：让 Home Chat 对“昨天 / 上一场 / 近期赛果 / 赛季战绩 / H2H”使用共享 PlayerResolver 和 canonical facts，稳定返回可同时展示多个球员的结构化历史结果，并以真实 API-Tennis、真实 OpenAI-compatible LLM 和真实浏览器内容断言证明目标达成。

**Architecture:** 在现有 Chat 前增加一个只控制工具可见性的确定性 history capability classifier；LLM 继续拆分自然语言并按球员调用业务工具。`TennisService` 复用 `_load_season_results()` 的五赛季按需缓存实现 result-count 语义，并从缓存 profile 直接读取赛季战绩。后端仍按每个成功工具结果发送一条 SSE `data`；前端追加保存 `dataItems`，Home 在既有回答壳中按球员渲染历史分组。

**Tech Stack:** Python 3.12、FastAPI、Pydantic 2、API-Tennis、OpenAI-compatible Chat Completions、PostgreSQL、Redis、Next.js 16、React 19、TypeScript、Tailwind CSS、Vitest、Playwright。

**Spec:** [T54 Home 历史球员问答修正设计](../specs/2026-09-13-tennixai-home-historical-player-query-closure-design.md)

## Global Constraints

- 每次接手或恢复时先完整阅读根目录 `AGENTS.md`、`PROJECT.md`、`ROADMAP.md`、`CURRENT.md`，再执行 `git fetch origin`、`git status --short --branch`、`git branch --show-current`、`git log -1 --oneline`。
- 只在 `main` 执行 T54。接手 ADE 必须先按 `CURRENT.md` 记录显式交接、执行者、起始提交和时间，单独提交并推送领取记录；任何产品代码修改不得早于领取提交。
- 保留并禁止修改、删除或提交这些既有未跟踪项：`.codex/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md`、`frontend/next-env.d.ts`。
- 根目录 `.env` 是唯一人工维护的运行配置。不得创建或使用 `backend/.env`、`frontend/.env`、`frontend/.env.local`，不得打印、复制或提交任何 API key、LLM key、供应商 ID、原始 payload 或完整 LLM 请求。
- 严格执行测试先行：先写一个能证明缺口的最小失败测试并运行到预期失败，再写最小实现，再运行局部与相关回归门；每个任务形成独立提交并推送 `origin/main`。
- 只复用现有 PlayerResolver、API-Tennis provider、五赛季按需查询与 TTL cache。不得新增数据库迁移、历史镜像、RAG、运行时翻译、第二个路由 LLM、双打、Player Chat、后台同步任务或 P3 能力。
- `Player.id` 和 `Match.id` 是公共结构化输出中的唯一身份；第三方 ID 不得进入 SSE、HTML、日志、fixture、截图或模型事实。
- 不改变 SSE wire protocol、Next.js 薄代理、首个非空 `answer_context`、既有 Match Chat 或 current/live/upcoming 行为。
- 不为通过 T54 而更新既有 Home、Match、Players 视觉基线；T54 只新增专用 history-answer 桌面与移动基线。

## Locked Interfaces

### Deterministic capability routing

Create `backend/app/chat/history.py` as the single history-intent authority:

```python
class HistoryCapability(StrEnum):
    LIMITED_RESULTS = "limited_results"
    SEASON_RECORD = "season_record"
    HEAD_TO_HEAD = "head_to_head"
    BROAD_HISTORY = "broad_history"


def classify_history_capabilities(
    text: str, *, scope: ChatScope
) -> frozenset[HistoryCapability]: ...


def is_broad_history_only(capabilities: frozenset[HistoryCapability]) -> bool:
    return capabilities == frozenset({HistoryCapability.BROAD_HISTORY})
```

The classifier controls catalog visibility only. It does not extract player names, generate tool arguments, or answer users.

### Business tools

```python
class PlayerResultsScope(StrEnum):
    YESTERDAY = "yesterday"
    LAST = "last"
    RECENT = "recent"


class GetPlayerResultsArgs(BaseModel):
    player_name: str = Field(min_length=1)
    scope: PlayerResultsScope
    limit: int = Field(default=5, ge=1, le=10)


class GetPlayerSeasonRecordArgs(BaseModel):
    player_name: str = Field(min_length=1)
    season: int | None = None
```

`last` normalizes every supplied limit to 1. `recent` defaults to 5 and accepts 1–10. `yesterday` preserves the existing Macau-calendar behavior. `season=None` selects the current Macau year; an explicit season must be within current year through current year minus four.

### Service additions

```python
async def get_latest_player_results(
    self, player_id: str, *, limit: int
) -> tuple[Match, ...]: ...


async def get_player_season_record(
    self, player_id: str, *, season: int | None = None
) -> tuple[int, PlayerSeasonRecord | None]: ...
```

`get_player_results()` uses the existing recent-provider path only for `yesterday`; it delegates `last`/`recent` to `get_latest_player_results()`. This preserves the bounded yesterday contract while removing the 30-day meaning from Chat last/recent queries.

### Typed structured result

```python
class PlayerHistoryEmptyReason(StrEnum):
    NO_RESULTS_IN_SCOPE = "no_results_in_scope"
    SEASON_RECORD_UNAVAILABLE = "season_record_unavailable"


class PlayerHistoryContext(BaseModel):
    player: Player
    scope: Literal["yesterday", "last", "recent", "season"]
    season: int | None = None
    availability: CapabilityStatus
    season_record: PlayerSeasonRecord | None = None
    empty_reason: PlayerHistoryEmptyReason | None = None


class StructuredToolResult(BaseModel):
    kind: Literal[
        "matches", "match", "intelligence", "player_resolution",
        "player_history", "unsupported"
    ]
    matches: list[Match] = Field(default_factory=list)
    packet: IntelligencePacket | None = None
    resolution: PlayerResolution | None = None
    player_history: PlayerHistoryContext | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    answer_context: AnswerContext | None = None
```

### Frontend stream state

```typescript
type PlayerHistoryContextDto = {
  player: PlayerDto
  scope: 'yesterday' | 'last' | 'recent' | 'season'
  season: number | null
  availability: CapabilityStatus
  season_record: PlayerSeasonRecordDto | null
  empty_reason: 'no_results_in_scope' | 'season_record_unavailable' | null
}

type StructuredData = {
  kind: 'matches' | 'match' | 'intelligence' | 'player_resolution' | 'player_history' | 'unsupported'
  matches: MatchDto[]
  packet?: IntelligencePacketDto | null
  resolution?: PlayerResolutionDto | null
  player_history?: PlayerHistoryContextDto | null
  metadata?: Record<string, unknown>
  answer_context?: AnswerContextDto | null
}

type ChatViewState = {
  phase: 'idle' | 'loading' | 'streaming' | 'success' | 'error'
  stage: string | null
  question: string
  text: string
  data: StructuredData | null
  dataItems: StructuredData[]
  answerContext: AnswerContextDto | null
  error: { code: string; message: string; details: Record<string, unknown> } | null
  warnings: ChatWarning[]
  progress: ChatProgress | null
}
```

## Task 1: Replace the Boolean History Gate with Capability Routing

**Outcome:** Home/Match catalogs expose only history tools relevant to the actual Chinese/English intent; broad-history-only questions still bypass model/provider calls.

**Files:**

- Create: `backend/app/chat/history.py`
- Create: `backend/tests/test_chat_history.py`
- Modify: `backend/app/chat/capabilities.py`
- Modify: `backend/app/chat/orchestrator.py`
- Modify: `backend/app/chat/tools.py`
- Modify: `backend/tests/test_chat_tools.py`
- Modify: `backend/tests/test_chat_orchestrator.py`

- [ ] **Step 1: Write and run the failing phrase matrix**

Cover `昨天/昨日/yesterday`, `上一场/上一次比赛/上场比赛/last match/previous match`, `最近/近期/最近赛果/赛果/recent results`, `本赛季/这个赛季/当前赛季/今年/赛季战绩/season record`, `交手/对战/H2H/head-to-head`, `全部历史/完整历史/生涯战绩/all-time`, bare `结果`, and Home `球员名 + 比赛结果`. Assert Match-scope bare `结果` does not expose player history.

```bash
cd backend
uv run pytest tests/test_chat_history.py tests/test_chat_tools.py -q
```

Expected red state: variants such as `上一次`, bare `赛果`, and `赛季战绩` are not represented by the current boolean gate.

- [ ] **Step 2: Implement the pure classifier**

Keep phrase groups private in `history.py`, normalize case and Unicode-compatible whitespace/punctuation, and return a set of capabilities. Avoid importing service/provider/database code.

- [ ] **Step 3: Map optional tools to required capabilities**

Add `get_player_season_record` to `_CAPABILITIES`. Change `allowed_tool_names()` to accept `history_capabilities: frozenset[HistoryCapability]`; expose `get_player_results`, `get_player_season_record`, and `get_head_to_head` only for `LIMITED_RESULTS`, `SEASON_RECORD`, and `HEAD_TO_HEAD` respectively. Core tool availability remains unchanged.

- [ ] **Step 4: Replace orchestrator guards**

Compute capabilities once from the latest user message and scope. Return typed unsupported before model/provider access only when `is_broad_history_only()` is true. Mixed broad + supported capability proceeds to the supported tool catalog and keeps the unsupported portion in the synthesis instruction.

- [ ] **Step 5: Run routing regressions**

```bash
cd backend
uv run pytest tests/test_chat_history.py tests/test_chat_tools.py tests/test_chat_orchestrator.py tests/test_p1_acceptance.py -q
```

- [ ] **Step 6: Commit and push**

```text
feat(chat): route bounded player history capabilities
```

## Task 2: Implement Five-season Latest Results and Profile-only Season Records

**Outcome:** `last` and `recent` use result-count semantics across year boundaries; season records do not trigger live/upcoming requests.

**Files:**

- Modify: `backend/app/service.py`
- Modify: `backend/tests/test_player_profile_service.py`
- Modify: `backend/tests/test_chat_tools.py`

- [ ] **Step 1: Add failing service tests**

Using `ProfileProvider` call counters and a fixed Macau-aware clock, prove:

- latest result older than 30 days is returned;
- `limit=1` queries only the newest season when it has a finished match;
- a requested count spanning December/January loads two seasons and returns deterministic descending order;
- duplicate canonical IDs are emitted once;
- live, scheduled, cancelled, postponed, unknown, and undated matches are excluded;
- same timestamp ties sort by internal match ID;
- exhausting current plus four prior seasons stops at exactly five loads and returns empty success;
- invalid limits fail before provider access;
- season defaults to current Macau year, rejects outside the five-year window, and calls profile once through cache;
- season record lookup makes zero live/upcoming calls;
- a supplied zero-match record remains non-null while an absent record remains unavailable.

```bash
cd backend
uv run pytest tests/test_player_profile_service.py -q
```

Expected red state: no latest-results or profile-only season-record method exists.

- [ ] **Step 2: Implement deterministic latest-result collection**

Loop from current Macau year through current year minus four, call `_load_season_results()` newest first, filter only `MatchStatus.FINISHED` with non-null `scheduled_at`, deduplicate by `match.id`, sort by `(scheduled_at, match.id)` descending, and stop loading seasons as soon as the requested count is available.

- [ ] **Step 3: Extend Chat result scopes without changing provider protocol**

Add `LAST` to `PlayerResultsScope`. Keep `_fetch_recent_history()` for `YESTERDAY`; make `LAST` normalize to one and make `RECENT` call `get_latest_player_results()`. Do not add an API-Tennis endpoint or repository write.

- [ ] **Step 4: Add profile-only season record lookup**

Validate the selected year before `_load_profile()`, select the exact supplier-provided `PlayerSeasonRecord`, and return `(selected_year, record_or_none)`. Do not call `get_player_profile_view()`.

- [ ] **Step 5: Run service/provider regressions**

```bash
cd backend
uv run pytest tests/test_player_profile_service.py tests/test_service.py tests/test_api_tennis_provider.py tests/test_provider_contract.py -q
```

- [ ] **Step 6: Commit and push**

```text
feat(service): add bounded latest player history semantics
```

## Task 3: Emit Typed Player-history Facts Through Chat

**Outcome:** result and season tools resolve names once, return `kind="player_history"`, preserve recoverable resolution outcomes, and give the synthesizer the same bounded facts sent to the UI.

**Files:**

- Modify: `backend/app/chat/models.py`
- Modify: `backend/app/chat/tools.py`
- Modify: `backend/app/chat/client.py`
- Modify: `backend/app/chat/orchestrator.py`
- Modify: `backend/tests/test_chat_tools.py`
- Modify: `backend/tests/test_chat_orchestrator.py`
- Modify: `backend/tests/test_chat_api.py`
- Modify: `backend/tests/test_p1_acceptance.py`
- Modify: `backend/tests/live/test_llm_live.py`

- [ ] **Step 1: Write failing model/tool tests**

Assert exact JSON schema for `get_player_results` and `get_player_season_record`; `last` forces one result; result contexts contain resolved English-primary/Chinese-secondary player identity; season context contains the selected year and supplier record; empty results set the correct typed `empty_reason`; no result relies on metadata for scope/player identity.

- [ ] **Step 2: Implement typed models and tool execution**

Add `PlayerHistoryEmptyReason`, `PlayerHistoryContext`, `GetPlayerSeasonRecordArgs`, the new result kind/field, description, schema registration, and executor branch. Resolve through the shared resolver first, then query service by internal ID. Keep ambiguous/not-found behavior as `player_resolution` plus SSE `done`.

- [ ] **Step 3: Update fake and real model guidance**

State exact scope semantics, bare `赛果 → recent`, season defaults/range, and one call per requested player in tool descriptions/system prompt. Extend `FakeChatModel` just enough for deterministic yesterday/last/recent/season tests; it remains a test double, not a second production router.

- [ ] **Step 4: Preserve every distinct backend outcome**

Verify a two-player model turn emits two ordered `data` events before synthesis. Cover non-empty + empty, different scopes in one question, one optional failure + one success warning behavior, and duplicate call suppression.

- [ ] **Step 5: Compact the same typed facts for synthesis**

Extend `_model_tool_result()` with player, scope, season, availability, season record, empty reason, and bounded canonical matches. Add assertions that prose cannot be prompted with empty facts when the structured result contains matches/record and that compact facts contain no provider fields, URLs, credentials, or external IDs.

- [ ] **Step 6: Run Chat regressions**

```bash
cd backend
uv run pytest tests/test_chat_tools.py tests/test_chat_orchestrator.py tests/test_chat_api.py tests/test_p1_acceptance.py -q
```

- [ ] **Step 7: Commit and push**

```text
feat(chat): stream typed player history results
```

## Task 4: Accumulate Multiple Structured SSE Results in the Frontend

**Outcome:** the hook retains all distinct data events in order while preserving the latest `data` and first `answerContext` compatibility contracts.

**Files:**

- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/hooks/use-chat-stream.ts`
- Modify: `frontend/hooks/use-chat-stream.test.tsx`
- Modify: `frontend/lib/chat-answer.ts`
- Modify: `frontend/lib/chat-answer.test.ts`

- [ ] **Step 1: Write failing accumulation/reset tests**

Send two `data` frames with different players and assert `dataItems` preserves both in order, `data` equals the second payload, and `answerContext` remains the first non-null context. Assert a new send and `reset()` clear `dataItems`; cancellation after one frame preserves that frame.

```bash
cd frontend
pnpm test -- hooks/use-chat-stream.test.tsx lib/chat-answer.test.ts
```

Expected red state: `ChatViewState` has no `dataItems`, and each frame overwrites the only structured payload.

- [ ] **Step 2: Add exact DTOs and state transitions**

Add `PlayerHistoryContextDto`, extend `StructuredData.kind`, and add optional `player_history`. Initialize/reset `dataItems: []`; on `data`, append using the functional state setter and retain current first-context behavior.

- [ ] **Step 3: Add the history answer label**

Map `player_history` to a truthful structured-answer label without changing existing labels.

- [ ] **Step 4: Run frontend type and hook regressions**

```bash
cd frontend
pnpm test -- hooks/use-chat-stream.test.tsx lib/chat-answer.test.ts
pnpm typecheck
```

- [ ] **Step 5: Commit and push**

```text
feat(frontend): retain multiple chat data results
```

## Task 5: Render Home Player-history Sections and Add Dedicated Visual States

**Outcome:** Home shows one or multiple player-history sections, season summaries, result cards, and per-player empty messages in the existing approved visual language.

**Files:**

- Create: `frontend/components/home/home-match-result-card.tsx`
- Create: `frontend/components/home/home-player-history.tsx`
- Modify: `frontend/components/home/home-assistant.tsx`
- Modify: `frontend/components/home-page.test.tsx`
- Create: `frontend/e2e/home-history.spec.ts`
- Create: approved T54 screenshots under `frontend/e2e/__screenshots__/{desktop,mobile}/`

- [ ] **Step 1: Write failing component tests**

Update the local stream fixture helper to accept an ordered array of `StructuredData`. Assert:

- one result title is `<English（中文）> · <scope label>`;
- multiple results title is `球员赛果与战绩`;
- scopes render as `昨日赛果`, `上一场比赛`, `近期赛果`, or `<year> 赛季战绩`;
- finished matches link to `/matches/<internal-id>`;
- season wins/losses/win rate/titles and only non-null surfaces render;
- mixed empty/non-empty sections both remain visible;
- empty copies are exactly `该范围暂无赛果信息` and `该赛季战绩暂不可用`;
- no history state renders `没有符合条件的比赛`;
- current match, unsupported, resolution, warning, retry, Markdown, and follow-up behavior remain unchanged.

```bash
cd frontend
pnpm test -- components/home-page.test.tsx
```

- [ ] **Step 2: Extract the existing match card without visual changes**

Move `MatchResultCard` and its status mapping into `home-match-result-card.tsx` with the same DOM, classes, labels, link, and callback contract. First run the existing Home tests to prove extraction-only compatibility.

- [ ] **Step 3: Implement player-history grouping**

Filter `chat.dataItems` for `kind === 'player_history'`, render in emission order, and keep current-match cards driven by their existing structured payloads. Compute win rate from supplied wins/losses only when denominator is non-zero. English is heading-primary; Chinese is secondary.

- [ ] **Step 4: Add deterministic browser functional coverage**

In `home-history.spec.ts`, intercept the Home Chat SSE route with deterministic multi-frame payloads. Assert two sections are simultaneously visible, one can be empty without hiding the other, finished links use internal IDs, no generic current-match empty title appears, and there are no page/console errors.

- [ ] **Step 5: Capture only two new T54 visual baselines**

Use a representative two-player response at desktop `1440×1000` and mobile `390×844`. Review both PNGs for hierarchy, overflow, clipping, readable secondary Chinese names, card links, empty copy, and preservation of the existing Home shell.

```bash
cd frontend
pnpm exec playwright test e2e/home-history.spec.ts --update-snapshots
pnpm exec playwright test e2e/home-history.spec.ts
pnpm exec playwright test e2e/prototype.visual.spec.ts e2e/player-directory.visual.spec.ts
```

Existing baseline PNGs must remain byte-unchanged.

- [ ] **Step 6: Run frontend regression gates**

```bash
cd frontend
pnpm test
pnpm typecheck
pnpm build
pnpm test:e2e
```

- [ ] **Step 7: Commit and push**

```text
feat(home): render grouped player history answers
```

## Task 6: Upgrade Real API, LLM, and Browser Gates to Factual Assertions

**Outcome:** real gates compare Chat output with canonical provider/service facts captured in the same run and fail on the original false-empty behavior.

**Files:**

- Modify: `backend/tests/live/test_llm_live.py`
- Modify: `backend/tests/live/test_player_directory_end_to_end_live.py`
- Modify: `frontend/e2e/player-directory-live.spec.ts`
- Modify: `docs/runbooks/p2-local.md`

- [ ] **Step 1: Strengthen deterministic-provider + real-LLM tests**

For Chinese and English prompts, assert the selected tool, scope, resolved internal player, `player_history` payload, ordered finished matches/season record, and `done` without terminal error. Include `辛纳上一次比赛是什么时候？郑钦文赛果如何？` and require two tool calls/data events.

- [ ] **Step 2: Add one same-run real API + real LLM backend flow**

Extend the existing `player_directory_e2e_live` gate rather than adding a new marker. Probe canonical service facts first, then send the matching Chat query and compare invariants: internal player identity, scope, count, all-finished status, descending order, and non-null season record when the probe has one. Do not freeze opponent names or dates.

- [ ] **Step 3: Strengthen real browser content assertions**

Make the Playwright watcher inspect Chat request/response payloads as well as `/api/players`. Test the first five real-service scenarios from the spec; the sixth controlled mixed empty/non-empty scenario remains in deterministic `home-history.spec.ts`. Assert visible player headings, scope labels, simultaneous sections, no `没有符合条件的比赛` for history, SSE `done`, no terminal error/console error, and no public supplier ID/key leakage.

- [ ] **Step 4: Update the local runbook**

Document exact prerequisites, root `.env` flags, service startup, probes, expected content assertions, and safe failure interpretation. Keep secrets represented only by variable names.

- [ ] **Step 5: Run focused real gates**

```bash
docker compose up -d --wait postgres redis
cd backend
uv run alembic upgrade head
TENNIX_RUN_LLM_LIVE=1 uv run pytest -m llm_live tests/live/test_llm_live.py -q
TENNIX_RUN_PLAYER_DIRECTORY_E2E_LIVE=1 uv run pytest -m player_directory_e2e_live tests/live/test_player_directory_end_to_end_live.py -q
cd ../frontend
TENNIX_E2E_API_TENNIS=1 TENNIX_E2E_REAL_LLM=1 pnpm exec playwright test e2e/player-directory-live.spec.ts
```

If a credential or upstream service is unavailable, record the exact blocker in `CURRENT.md`; do not mark T54 complete or replace the gate with weaker prose-only assertions.

- [ ] **Step 6: Commit and push**

```text
test(history): enforce real factual chat outcomes
```

## Task 7: Run the Full Closure Gate and Update the Three Controls

**Outcome:** all deterministic, infrastructure, real-service, browser, leakage, and visual gates pass; T54/P2.6/P2 are truthfully closed and P3 becomes ready for design but does not begin.

**Files:**

- Modify: `PROJECT.md`
- Modify: `ROADMAP.md`
- Modify: `CURRENT.md`

- [ ] **Step 1: Synchronize and verify the final candidate**

```bash
git fetch origin
git status --short --branch
git branch --show-current
git log -1 --oneline
git rev-list --left-right --count main...origin/main
```

Require `main`, no unexplained tracked changes, and only the protected untracked items listed in Global Constraints.

- [ ] **Step 2: Run all deterministic and infrastructure gates**

```bash
docker compose up -d --wait postgres redis
cd backend
uv run alembic upgrade head
uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure and not player_alias_llm_live and not player_directory_e2e_live" -q
uv run pytest -m infrastructure -q
cd ../frontend
pnpm test
pnpm typecheck
pnpm build
pnpm test:e2e
```

- [ ] **Step 3: Run all affected real gates**

```bash
cd backend
TENNIX_RUN_API_TENNIS_LIVE=1 uv run pytest -m api_tennis_live -q
TENNIX_RUN_LLM_LIVE=1 uv run pytest -m llm_live -q
TENNIX_RUN_PLAYER_DIRECTORY_E2E_LIVE=1 uv run pytest -m player_directory_e2e_live tests/live/test_player_directory_end_to_end_live.py -q
cd ../frontend
TENNIX_E2E_API_TENNIS=1 TENNIX_E2E_REAL_LLM=1 pnpm exec playwright test e2e/player-directory-live.spec.ts
```

- [ ] **Step 4: Review visuals and scan boundaries**

Inspect both new T54 screenshots and verify no existing baseline changed. Run repository searches for provider field names, external-ID shapes, credential values, nested env files, accidental P3 terms in the task diff, and untracked-file inclusion. Use only variable names in command output; never place actual secret values in search arguments.

```bash
git diff --check
git diff --name-status 831459b..HEAD
git status --short
```

- [ ] **Step 5: Update controls with exact evidence**

In `PROJECT.md`, record the stable closed behavior and P3 readiness. In `ROADMAP.md`, mark T54, P2.6, and P2 `done`, attach exact product commits and actual pass counts/commands, and leave P3 `planned` / ready for design. In `CURRENT.md`, set T54 `done`, record final commit set, real/deterministic/browser/visual/leakage evidence, and state that no P3 design task is claimed.

- [ ] **Step 6: Create and push a control-only closure commit**

```text
docs: close T54 and restore P3 readiness
```

After pushing, require `git rev-list --left-right --count main...origin/main` to print `0 0` and `git status --short` to contain only the five protected untracked items.

## Completion Definition

T54 is complete only when all seven tasks are committed and pushed, every actual gate above passes, Home displays correct simultaneous historical facts for the approved Chinese/English scenarios, real tests assert content rather than mere prose/completion, existing visual baselines are preserved, and all three controls point to exact evidence. P3 remains unimplemented and requires a new explicit user-authorized design task.
