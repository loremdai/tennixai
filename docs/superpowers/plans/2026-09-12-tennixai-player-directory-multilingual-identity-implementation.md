# TennixAI Player Directory and Multilingual Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建成 ATP/WTA 单打 Top 200 排名页、可搜索全部已知球员的中英文身份层、球员详情与五赛季历史赛果，并让 Home/Match Chat 通过同一个确定性 resolver 正确处理全名、缩写、姓氏和中文名。

**Architecture:** API-Tennis 继续提供排名、档案、赛程和赛果；PostgreSQL 保存内部球员主数据、外部 ID、别名和有限排名快照。离线命令负责同步目录与批量生成缺失中文名，运行时 `PlayerResolver` 只查询本地 alias 并输出 `resolved | ambiguous | not_found`，随后 TennisService 才按内部 ID 调用 provider。浏览器只通过 Next.js Route Handler 访问 FastAPI。

**Tech Stack:** Python 3.12、FastAPI、Pydantic 2、httpx、OpenAI-compatible Chat Completions、SQLAlchemy async、Alembic、PostgreSQL 16、Next.js 16、React 19、TypeScript、Tailwind CSS、Vitest、Playwright。

**Spec:** [球员目录、多语言身份与历史赛果设计规格](../specs/2026-09-12-tennixai-player-directory-multilingual-identity-design.md)

## Global Constraints

- 开始每个任务前完整阅读根目录 `PROJECT.md`、`ROADMAP.md`、`CURRENT.md`，核对 `main`、HEAD、远程和工作区；按 `AGENTS.md` 领取唯一当前任务并先提交、推送领取记录。
- 根目录 `.env` 是 backend、frontend、Playwright 和真实测试的唯一人工配置入口；不得新建 `backend/.env`、`frontend/.env` 或 `frontend/.env.local`。
- API key、LLM key、供应商外部 ID、原始 payload、完整 LLM 请求不得进入公共 DTO、前端、截图、fixture、文档、日志或 Git。
- `Player.id` 是跨 UI、Chat、Service 和 Provider 的唯一公共身份；供应商 ID 只存在于 adapter/identity persistence 内部。
- 现有 `Player.name` 和 JSON `name` 始终表示首选英文名；新增可选 `localized_name` 表示首选简体中文名。
- 页面显示英文为主、中文为辅；正式目录发布门要求纳入目录的首选英文名和中文名覆盖率均为 100%。
- `/players` 无查询时只展示 ATP/WTA 单打 Top 200，官方名次升序、每页 50；有查询时搜索全部本地已知单打球员。
- 球员历史默认当前赛季，可选择当前及前四赛季，每页 20，只筛 season、tier、W/L；不增加 surface filter。
- 不实现双打、Player Chat、运行时翻译 LLM、RAG、Vector DB、Elasticsearch、全量供应商历史镜像、Sportradar 依赖或 P3 能力。
- API-Tennis 的运行时球员查询必须是 `alias → internal player_id → provider player_key`，不得继续扫描 live/三日 fixtures 后按名字过滤。
- `ambiguous` 和 `not_found` 是可恢复领域结果；Chat 必须正常生成澄清文案并以 SSE `done` 结束。只有基础设施/供应商故障可以进入终止错误路径。
- v0 输出是 `/players` 和 `/players/[playerId]` 的视觉真相；ADE 只接真实数据与状态，不自行重设计。Home/Match 既有原型不得被顺手改版。
- 原始供应商 payload 保留 14 天；球员 identity、active aliases、排名快照和既有 canonical observations 不受该清理影响。
- 每个任务先写失败测试、确认预期失败，再写最小实现；只提交任务内文件，完成后把实际命令和结果写回三份总控并推送 `origin/main`。

## Planned File Structure

### Backend player domain

- `backend/app/players/__init__.py`：只导出稳定 public player types。
- `backend/app/players/models.py`：tour、ranking、alias、resolution、profile、season record、result page 的 canonical Pydantic models。
- `backend/app/players/providers.py`：排名目录、详细档案和赛季赛果所需的窄 provider protocols。
- `backend/app/players/repository.py`：`PlayerDirectoryRepository` protocol；不包含 SQLAlchemy 查询。
- `backend/app/players/normalization.py`：唯一名称归一化和确定性 alias 派生函数。
- `backend/app/players/sync.py`：`PlayerDirectorySync`，只做目录/排名同步和英文 alias 派生。
- `backend/app/players/enrichment.py`：中文名称 translator protocol、OpenAI-compatible adapter、严格 batch validator 和事务写入编排。
- `backend/app/players/resolver.py`：运行时 `PlayerResolver`，不导入 LLM 或 API-Tennis adapter。
- `backend/app/players/cli.py`：`sync`、`enrich-zh`、`status` 三个显式本地子命令。
- `backend/app/persistence/player_directory.py`：PostgreSQL repository 实现。

### Existing backend files changed in place

- `backend/app/domain.py`：只给现有轻量 `Player` 增加 `localized_name`，不搬迁既有 Match domain。
- `backend/app/persistence/models.py`：扩展 `players`，增加 alias/ranking rows。
- `backend/migrations/versions/20260912_0003_player_directory.py`：兼容迁移。
- `backend/app/providers/api_tennis_dtos.py`、`backend/app/providers/api_tennis.py`：standings、profile、season result 能力。
- `backend/app/providers/fake.py`：确定性排名/profile/history fixture 能力。
- `backend/app/service.py`：按 ID 查询、目录/profile/result page orchestration；保留 P1/P2 时间与缓存语义。
- `backend/app/api/schemas.py`、`backend/app/api/routes.py`：四个 player APIs。
- `backend/app/chat/models.py`、`backend/app/chat/tools.py`、`backend/app/chat/executor.py`、`backend/app/chat/orchestrator.py`：resolution 领域结果和双语回答事实。
- `backend/app/main.py`：repository/resolver/service 依赖装配；离线 enrichment 不装入 web runtime。

### Frontend

- `frontend/app/players/page.tsx`：rankings/search 路由入口。
- `frontend/app/players/[playerId]/page.tsx`：profile 路由入口。
- `frontend/app/api/players/rankings/route.ts`、`frontend/app/api/players/[playerId]/route.ts`、`frontend/app/api/players/[playerId]/results/route.ts`：同源代理；现有 search proxy 保留。
- `frontend/components/players/players-page.tsx`：页面状态与 URL query orchestration。
- `frontend/components/players/rankings-table.tsx`：v0 排名表视觉组件。
- `frontend/components/players/player-search-results.tsx`：全目录搜索结果。
- `frontend/components/players/player-profile-page.tsx`：profile 状态与 composition。
- `frontend/components/players/player-profile-header.tsx`、`player-season-summary.tsx`、`player-current-status.tsx`、`player-results.tsx`：v0 视觉子组件。
- `frontend/components/players/player-preview-data.ts`：只供 preview/visual baseline 的确定性样例。
- `frontend/lib/api/types.ts`、`frontend/lib/api/client.ts`：player DTO 与四个 client calls。
- `frontend/lib/player-view-models.ts`：英文主/中文辅、ranking movement、season 和 empty copy 映射。
- `frontend/components/match/match-header.tsx`：`球员` 导航从 `/#players` 改为 `/players`。
- `frontend/e2e/player-directory.spec.ts`、`frontend/e2e/player-directory.visual.spec.ts`：功能与视觉门。

---

### T43: Generate, Import, and Freeze the v0 Player Pages as Visual Truth

**Outcome:** 用户提供的 v0 `/players` 与 `/players/[playerId]` 设计被整理成仓库内 preview 页面和桌面/移动视觉基线；不接真实 API。

**Input gate:** 使用 [v0 球员页面交付提示](../../v0/2026-09-12-player-pages-prompt.md) 生成并导出代码。若仓库中没有用户确认的 v0 输出或可访问的 v0 项目，本任务必须保持 `ready` 并在 `CURRENT.md` 记录这一项外部输入，不得由 ADE 自行发明视觉稿。

**Files:**

- Create: `frontend/app/players/page.tsx`
- Create: `frontend/app/players/[playerId]/page.tsx`
- Create: `frontend/components/players/players-page.tsx`
- Create: `frontend/components/players/rankings-table.tsx`
- Create: `frontend/components/players/player-search-results.tsx`
- Create: `frontend/components/players/player-profile-page.tsx`
- Create: `frontend/components/players/player-profile-header.tsx`
- Create: `frontend/components/players/player-season-summary.tsx`
- Create: `frontend/components/players/player-current-status.tsx`
- Create: `frontend/components/players/player-results.tsx`
- Create: `frontend/components/players/player-preview-data.ts`
- Create: `frontend/components/players/players-page.test.tsx`
- Create: `frontend/components/players/player-profile-page.test.tsx`
- Create: `frontend/e2e/player-directory.visual.spec.ts`
- Create: approved screenshots under `frontend/e2e/__screenshots__/{desktop,mobile}/`
- Modify: `frontend/components/match/match-header.tsx`

**Interfaces:**

- Consumes: v0 exported component structure and the approved design DTO shape only as fixture types.
- Produces preview components with explicit props; no component may call `fetch` in T43.

```ts
type PlayersPageProps = {
  initialTour?: 'ATP' | 'WTA'
  initialQuery?: string
  preview: true
  previewData: PlayerDirectoryPreviewData
}

type PlayerProfilePageProps = {
  playerId?: string
  preview: true
  previewData: PlayerProfilePreviewData
}
```

- [ ] **Step 1: Verify and record the exact v0 input commit/export**

Place only the user-approved export in the task diff. Record its source/export date in `CURRENT.md`; do not copy package manifests or overwrite established shadcn components blindly.

- [ ] **Step 2: Claim T43 and normalize imports without redesigning**

Reuse existing `ProductHeader`, `PlayerCountry`, shadcn primitives, colors and fonts where they are visually equivalent. Preserve v0 layout/spacing/content hierarchy. Change the header's `球员` link to `/players` and set `active="players"` on both player routes.

- [ ] **Step 3: Write component behavior tests before cleanup**

Assert ATP/WTA switching, 50-row pagination labels, country/China filters, search mode outside Top 200, row/profile links, season/tier/W-L controls, 20-result pagination and exact empty text `暂无比赛信息`.

```tsx
expect(screen.getByRole('heading', { name: 'Ben Shelton' })).toBeVisible()
expect(screen.getByText('本·谢尔顿')).toBeVisible()
expect(screen.getByText('暂无比赛信息')).toBeVisible()
```

- [ ] **Step 4: Prove tests fail against the raw export where behavior is incomplete**

```bash
cd frontend
pnpm test -- components/players/players-page.test.tsx components/players/player-profile-page.test.tsx
```

- [ ] **Step 5: Add deterministic preview data and complete interaction-only gaps**

Preview data must include ATP/WTA, China/non-China, rank 200/rank 201/no rank, movement directions, profile with/without image, live/next/empty status, five seasons and enough results for pagination. Keep data isolated in `player-preview-data.ts`; production props remain unimplemented until T51.

- [ ] **Step 6: Capture and inspect four visual baselines**

```bash
cd frontend
pnpm test:e2e:update --grep "player directory visual"
pnpm test:e2e --grep "player directory visual"
```

Required: players desktop/mobile and profile desktop/mobile at `1440×1000` and `390×844`. Inspect every PNG for clipping, overflow, unreadable bilingual hierarchy, broken mobile filters and accidental dev overlays.

- [ ] **Step 7: Run existing prototype/visual regressions**

```bash
cd frontend
pnpm test
pnpm typecheck
pnpm build
pnpm test:e2e --grep "prototype|visual"
```

Existing Home/Match baselines must not change unless the only pixel delta is the approved `/players` navigation href/active state and no screenshot captures it differently.

- [ ] **Step 8: Commit and close T43**

Commit preview components and reviewed baselines, name the source as v0 in controls, mark T44 ready and push.

---

### T44: Add Canonical Ranking Models and the API-Tennis Standings Adapter

**Outcome:** provider 可以把 ATP/WTA standings 映射成零供应商字段的 canonical ranking entries；现有 Match/Player API 保持兼容。

**Files:**

- Create: `backend/app/players/__init__.py`
- Create: `backend/app/players/models.py`
- Create: `backend/app/players/providers.py`
- Create: `backend/tests/fixtures/api_tennis/standings.json`
- Create: `backend/tests/test_player_ranking_provider.py`
- Modify: `backend/app/domain.py` (`Player`)
- Modify: `backend/app/providers/api_tennis_dtos.py` (`StandingDto`)
- Modify: `backend/app/providers/api_tennis.py` (`ApiTennisProvider.get_rankings`)
- Modify: `backend/app/providers/fake.py` (`get_rankings` deterministic data)
- Modify: `backend/tests/live/test_api_tennis_live.py` (opt-in standings smoke)
- Modify: `backend/tests/test_domain.py`

**Interfaces:**

- Produces:

```python
class Tour(StrEnum):
    ATP = "ATP"
    WTA = "WTA"

class RankingMovement(StrEnum):
    UP = "up"
    DOWN = "down"
    SAME = "same"
    UNKNOWN = "unknown"

class RankingEntry(FrozenModel):
    player: Player
    tour: Tour
    rank: int = Field(ge=1)
    points: int = Field(ge=0)
    movement: RankingMovement
    ranking_date: date
    fetched_at: datetime

class PlayerCatalogProvider(Protocol):
    async def get_rankings(self, tour: Tour) -> tuple[RankingEntry, ...]: ...
```

- Changes `Player` compatibly:

```python
class Player(FrozenModel):
    id: str
    name: str
    localized_name: str | None = None
    country_code: str | None = None
    ranking: int | None = None
```

- Consumed by T45/T46: `RankingEntry.player.id` is already an internal `ply_` ID created through `IdentityRepository`; `StandingDto.player_key` never escapes the adapter.

- [ ] **Step 1: Claim T44 in the control plane**

Update T44 to `in_progress` in `ROADMAP.md` and replace the current task in `CURRENT.md` with executor, branch `main`, starting commit and timestamp. Commit and push only those control files.

```bash
git add ROADMAP.md CURRENT.md
git commit -m "docs: claim T44 ranking adapter"
git push origin main
```

- [ ] **Step 2: Add failing domain and provider tests**

Write tests proving timezone-aware `fetched_at`, positive ranks, non-negative points, `localized_name=None` backward compatibility, ATP/WTA parameter mapping, movement fallback, invalid numeric rows skipped, internal IDs only, and no API key/vendor tokens in serialized entries.

```python
async def test_get_rankings_maps_standings_to_internal_entries(provider, seen):
    entries = await provider.get_rankings(Tour.ATP)
    assert seen[-1].url.params["method"] == "get_standings"
    assert seen[-1].url.params["event_type"] == "ATP"
    assert entries[0].player.id.startswith("ply_")
    assert entries[0].player.name == "Jannik Sinner"
    assert entries[0].rank == 1
    assert entries[0].points >= 0
    assert "player_key" not in entries[0].model_dump_json()
```

- [ ] **Step 3: Confirm the focused tests fail for missing types/methods**

Run:

```bash
cd backend
uv run pytest tests/test_domain.py tests/test_player_ranking_provider.py -v
```

Expected: collection or assertion failure because `Tour`, `RankingEntry`, `StandingDto` and `get_rankings()` do not exist.

- [ ] **Step 4: Implement the canonical types and permissive vendor DTO**

Add the exact interfaces above. `StandingDto` must tolerate unknown fields and contain only the documented wire fields:

```python
class StandingDto(VendorModel):
    place: int | str | None = None
    player: str | None = None
    player_key: int | str | None = None
    league: str | None = None
    movement: str | None = None
    country: str | None = None
    points: int | str | None = None
```

- [ ] **Step 5: Implement `ApiTennisProvider.get_rankings()`**

Call `_request("get_standings", {"event_type": tour.value})`, validate `ApiTennisResponse[list[StandingDto]]`, reject rows missing a usable key/name/rank, map country through `country_code_from_name`, create internal IDs through existing identity, sort by `(rank, player.id)`, and use `self._now().date()`/`self._now()` for snapshot timestamps. Do not add standings to `TennisDataProvider`; concrete API/Fake providers satisfy the narrow `PlayerCatalogProvider` structurally.

- [ ] **Step 6: Make the fake provider deterministic**

Return at least six entries spanning ATP/WTA, China, unchanged/up/down ranking states, one Top 200 boundary and one rank outside 200. Reuse fake players' internal IDs; do not introduce hard-coded `api_tennis` IDs.

- [ ] **Step 7: Run focused and regression tests**

```bash
cd backend
uv run pytest tests/test_domain.py tests/test_player_ranking_provider.py tests/test_provider_contract.py tests/test_api_tennis_provider.py -v
uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live" -q
```

Expected: all selected tests pass; no existing Player serialization assertion breaks.

- [ ] **Step 8: Run the opt-in real standings smoke**

```bash
cd backend
TENNIX_RUN_API_TENNIS_LIVE=1 uv run pytest -m api_tennis_live tests/live/test_api_tennis_live.py -v
```

The smoke must assert both `ATP` and `WTA` calls authenticate, return sorted canonical entries when data exists, and never print response bodies or the key. A supplier-declared empty tour may skip only that tour after authentication; 403/429 is a truthful failure, not a pass.

- [ ] **Step 9: Commit implementation and close T44**

```bash
git add backend/app/domain.py backend/app/players backend/app/providers backend/tests
git commit -m "feat: add canonical player rankings adapter"
```

Record the product commit and exact test counts in all three controls, mark T44 `done`, T45 `ready`, then commit/push controls separately.

---

### T45: Persist the Player Directory, Aliases, and Ranking Snapshots

**Outcome:** PostgreSQL 成为 player master data 和 aliases 的事实源，现有 player external IDs 与 Match snapshots 无损兼容。

**Files:**

- Create: `backend/app/players/repository.py`
- Create: `backend/app/persistence/player_directory.py`
- Create: `backend/migrations/versions/20260912_0003_player_directory.py`
- Create: `backend/tests/test_player_directory_repository.py`
- Create: `backend/tests/integration/test_player_directory_postgres.py`
- Modify: `backend/app/players/models.py`
- Modify: `backend/app/persistence/models.py`
- Modify: `backend/app/persistence/repositories.py` (`MatchSnapshotRepository.player_or_placeholder`)
- Modify: `backend/tests/test_persistence_models.py`

**Interfaces:**

- Produces:

```python
class PlayerAliasKind(StrEnum):
    PREFERRED = "preferred"
    FULL = "full"
    SURNAME = "surname"
    REORDERED = "reordered"
    ABBREVIATED = "abbreviated"
    PROVIDER = "provider"
    TRANSLITERATED = "transliterated"

class PlayerAliasSource(StrEnum):
    PROVIDER = "provider"
    TRUSTED_EXTERNAL = "trusted_external"
    LLM = "llm"
    DERIVED = "derived"

class PlayerAlias(FrozenModel):
    player_id: str
    locale: str
    alias: str
    normalized_alias: str
    kind: PlayerAliasKind
    source: PlayerAliasSource
    source_ref: str | None = None
    model: str | None = None
    prompt_version: str | None = None

class DirectoryPlayer(FrozenModel):
    player: Player
    gender: Gender
    birth_date: date | None = None
    image_url: str | None = None

class AliasMatch(FrozenModel):
    player: DirectoryPlayer
    alias: PlayerAlias
    current_rank: int | None = None

class LocalizedNameUpdate(FrozenModel):
    player_id: str
    localized_name: str
    aliases: tuple[PlayerAlias, ...]

class PlayerDirectoryRepository(Protocol):
    async def save_ranking_snapshot(self, entries: tuple[RankingEntry, ...]) -> None: ...
    async def upsert_aliases(self, aliases: tuple[PlayerAlias, ...]) -> int: ...
    async def save_localized_names(self, updates: tuple[LocalizedNameUpdate, ...]) -> int: ...
    async def get_player(self, player_id: str) -> DirectoryPlayer | None: ...
    async def get_rankings(self, tour: Tour, *, page: int, page_size: int, country_code: str | None) -> tuple[tuple[RankingEntry, ...], int]: ...
    async def find_aliases(self, normalized_query: str, *, limit: int) -> tuple[AliasMatch, ...]: ...
    async def list_players_missing_localized_name(self, *, limit: int) -> tuple[DirectoryPlayer, ...]: ...
    async def list_players_for_alias_sync(self, *, limit: int, after_id: str | None = None) -> tuple[DirectoryPlayer, ...]: ...
    async def prune_ranking_snapshots(self, *, keep_per_tour: int = 8) -> int: ...
    async def directory_counts(self) -> dict[str, int]: ...

class MemoryPlayerDirectoryRepository:
    """Deterministic fake/test implementation of the same protocol."""
    ...
```

- Consumes: T44 `RankingEntry`, `Tour`, existing `Database` and `PlayerExternalIdRow`.

- [ ] **Step 1: Claim T45 and write migration/repository failure tests**

Tests must assert schema constraints, duplicate alias idempotency, same alias across two players, latest ranking snapshot selection, country filtering, 50-row pagination, concurrent external-ID preservation and snapshot reconstruction with `localized_name`.

```python
async def test_same_normalized_alias_can_return_two_players(repository):
    await repository.upsert_aliases((alias_for("ply_a", "zh-Hans", "王"),))
    await repository.upsert_aliases((alias_for("ply_b", "zh-Hans", "王"),))
    matches = await repository.find_aliases("王", limit=10)
    assert {item.player.player.id for item in matches} == {"ply_a", "ply_b"}
```

- [ ] **Step 2: Confirm tests fail before the migration and repository exist**

```bash
cd backend
uv run pytest tests/test_player_directory_repository.py tests/test_persistence_models.py -v
uv run pytest -m infrastructure tests/integration/test_player_directory_postgres.py -v
```

Expected: import/table failures naming the missing repository and rows.

- [ ] **Step 3: Add migration `0003` without replacing identity tables**

Alter existing `players` with nullable `localized_name`, `gender`, `birth_date`, `image_url`, `first_seen_at`, `last_seen_at`; keep `name`, `country_code`, `ranking`, `created_at`, `updated_at`. Backfill `first_seen_at/last_seen_at` from `created_at/updated_at` before making the two seen columns non-null.

Create `player_aliases` with the fields from the spec and unique constraint `(player_id, locale, normalized_alias, kind)`. Add a non-unique B-tree index on `normalized_alias`; do not install `pg_trgm` or `unaccent` in this task.

Create `player_rankings` with unique constraints `(tour, ranking_date, rank)` and `(tour, ranking_date, player_id)`, plus lookup indexes `(tour, ranking_date, rank)` and `player_id`. Downgrade drops only new ranking/alias tables and new player columns; it must not drop `players` or `player_external_ids`.

- [ ] **Step 4: Add SQLAlchemy rows and repository queries**

Implement all methods in the interface. `save_ranking_snapshot()` uses one transaction to upsert player display fields, upsert ranking rows, and update the compatibility `players.ranking`. `save_localized_names()` validates every referenced player before one transaction updates the whole batch and its aliases. `find_aliases()` joins latest ranking through a subquery and orders by alias kind priority, null-rank-last, rank, player ID. Add `MemoryPlayerDirectoryRepository` for deterministic fake/unit use; it must implement identical duplicate, ambiguity, pagination, atomic batch and ordering semantics.

- [ ] **Step 5: Preserve Match snapshot behavior**

`MatchSnapshotRepository.player_or_placeholder()` must map both names:

```python
return Player(
    id=player_id or "ply_unknown",
    name=(row.name if row and row.name else "Unknown player"),
    localized_name=row.localized_name if row else None,
    country_code=row.country_code if row else None,
    ranking=row.ranking if row else None,
)
```

- [ ] **Step 6: Run Alembic round-trip and concurrency gates**

```bash
cd backend
uv run alembic upgrade head
uv run pytest -m infrastructure tests/integration/test_player_directory_postgres.py tests/integration/test_postgres_repositories.py -v
uv run alembic downgrade 0002
uv run alembic upgrade head
uv run pytest -m infrastructure tests/integration/test_player_directory_postgres.py -v
```

Expected: all tests pass; rows created before `0003` retain name/external ID; downgrade leaves core P2 tables intact.

- [ ] **Step 7: Run deterministic backend regression and commit**

```bash
cd backend
uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure" -q
```

Commit product code, then update controls with exact migration/test evidence, mark T45 done and T46 ready, commit/push both commits.

---

### T46: Build Idempotent Directory Sync and English Alias Derivation

**Outcome:** 一个显式本地命令可以同步 ATP/WTA rankings、更新 player master data，并为所有已知单打球员生成一致的英文 full/surname/reordered/abbreviated/provider aliases。

**Files:**

- Create: `backend/app/players/normalization.py`
- Create: `backend/app/players/sync.py`
- Create: `backend/app/players/cli.py`
- Create: `backend/tests/test_player_name_normalization.py`
- Create: `backend/tests/test_player_directory_sync.py`
- Modify: `backend/app/players/repository.py`
- Modify: `backend/app/persistence/player_directory.py`

**Interfaces:**

- Produces:

```python
NORMALIZATION_VERSION = "player-name-v1"

def normalize_player_name(value: str) -> str: ...
def derive_english_aliases(player: DirectoryPlayer, provider_names: tuple[str, ...] = ()) -> tuple[PlayerAlias, ...]: ...

class PlayerDirectorySync:
    def __init__(self, provider: PlayerCatalogProvider, repository: PlayerDirectoryRepository, *, now: Callable[[], datetime]) -> None: ...
    async def sync_rankings(self) -> DirectorySyncReport: ...
    async def sync_known_player_aliases(self, *, batch_size: int = 500) -> DirectorySyncReport: ...

class DirectorySyncReport(FrozenModel):
    discovered: int
    updated: int
    aliases_inserted: int
    skipped: int
    failed: int
```

- Consumes: T44 provider and T45 repository.

- [ ] **Step 1: Claim T46 and write table-driven normalization failures**

Use exact cases:

```python
@pytest.mark.parametrize(("raw", "normalized"), [
    (" B.  Shelton ", "b shelton"),
    ("BEN-SHELTON", "ben shelton"),
    ("Lehečka, Jiří", "lehecka jiri"),
    ("本·谢尔顿", "本谢尔顿"),
    ("郑 钦文", "郑钦文"),
])
def test_normalize_player_name(raw, normalized):
    assert normalize_player_name(raw) == normalized
```

Add alias assertions for `Ben Shelton`, `Shelton`, `B. Shelton`, `Shelton Ben` and accented/unaccented names. Composite names containing `/`, `&` or ` vs ` must be excluded from the singles directory alias builder.

- [ ] **Step 2: Confirm focused tests fail**

```bash
cd backend
uv run pytest tests/test_player_name_normalization.py tests/test_player_directory_sync.py -v
```

Expected: missing module/type failures.

- [ ] **Step 3: Implement one normalization function**

Use `unicodedata.normalize("NFKC", value)`, `casefold()`, Unicode decomposition for a separate Latin unaccent path, and regexes that remove punctuation/whitespace without dropping CJK characters. Every repository query and alias write must call this same function; no second normalizer is allowed in service or frontend.

- [ ] **Step 4: Implement deterministic alias derivation**

The function emits de-duplicated aliases with explicit `kind/source`. It may derive surname and initial forms only when tokenization is unambiguous; it preserves the original accented display alias while storing the unaccented normalized form. It never infers that two players are the same.

- [ ] **Step 5: Implement `PlayerDirectorySync`**

Fetch ATP and WTA standings sequentially to stay within the trial quota, persist each complete snapshot atomically, then page through known nonblank `players.name` rows to derive aliases. After both tour writes succeed, call `prune_ranking_snapshots(keep_per_tour=8)` so ranking persistence remains bounded. A tour failure leaves the last successful snapshot intact and increments `failed`; it must not replace that tour with an empty snapshot or prune its last good data.

- [ ] **Step 6: Add the local CLI**

Supported invocations are exact:

```bash
cd backend
uv run python -m app.players.cli sync
uv run python -m app.players.cli status
```

The command builds `Settings`, `Database`, `PostgresIdentityRepository`, `ApiTennisProvider`, and `PostgresPlayerDirectoryRepository`, closes HTTP/database resources in `finally`, prints only aggregate counts, and exits non-zero when either tour fails.

- [ ] **Step 7: Prove idempotency and failure preservation**

Run the sync tests twice against the same repository and assert the second report inserts zero aliases/duplicate rankings. Inject WTA failure after a successful snapshot and prove the prior WTA rows remain available.

```bash
cd backend
uv run pytest tests/test_player_name_normalization.py tests/test_player_directory_sync.py -v
uv run pytest -m infrastructure tests/integration/test_player_directory_postgres.py -v
```

- [ ] **Step 8: Run one real local sync and inspect counts only**

```bash
cd backend
uv run alembic upgrade head
uv run python -m app.players.cli sync
uv run python -m app.players.cli status
```

Verify non-zero ATP/WTA counts, Top 200 availability, no secrets/external IDs in stdout, and rerun `sync` to prove stable counts.

- [ ] **Step 9: Commit and close T46**

Commit implementation, record real aggregate counts and deterministic/infrastructure results in controls, mark T47 ready, push product and control commits.

---

### T47: Add Offline LLM Chinese-Name Enrichment

**Outcome:** 缺失中文名的球员可通过严格批量协议离线补齐；重复运行不重复消费，错误 batch 零写入，web runtime 不持有 translator。

**Files:**

- Create: `backend/app/players/enrichment.py`
- Create: `backend/tests/test_player_alias_enrichment.py`
- Create: `backend/tests/live/test_player_alias_enrichment_live.py`
- Modify: `backend/app/players/cli.py`
- Modify: `backend/app/players/models.py`
- Modify: `backend/app/players/repository.py`
- Modify: `backend/app/persistence/player_directory.py`
- Modify: `backend/pyproject.toml` (register `player_alias_llm_live` marker)

**Interfaces:**

- Produces:

```python
PLAYER_NAME_PROMPT_VERSION = "zh-Hans-player-name-v1"

class PlayerNameInput(FrozenModel):
    player_id: str
    name: str
    country_code: str | None = None
    birth_date: date | None = None
    gender: Gender = Gender.UNKNOWN

class PlayerNameTranslation(FrozenModel):
    player_id: str
    localized_name: str = Field(min_length=1, max_length=80)
    aliases: tuple[str, ...] = ()

class PlayerNameTranslator(Protocol):
    async def translate(self, players: tuple[PlayerNameInput, ...]) -> tuple[PlayerNameTranslation, ...]: ...

class PlayerAliasEnricher:
    async def enrich_missing(self, *, batch_size: int = 25, max_batches: int | None = None) -> EnrichmentReport: ...
```

- Consumes: existing root `.env` LLM settings and T45 atomic `save_localized_names()`.

- [ ] **Step 1: Claim T47 and write strict validation failures**

Tests cover valid batch, unknown returned ID, duplicate returned ID, omitted input ID, extra ID, blank name, malformed JSON, translator error, atomic zero-write, rerun skip, Chinese alias derivation (`本·谢尔顿`/`本谢尔顿`/`谢尔顿`) and provenance fields.

```python
async def test_malformed_batch_writes_nothing(repository, translator):
    translator.response = '[{"player_id":"ply_unknown","localized_name":"未知"}]'
    with pytest.raises(AppError, match="translation batch"):
        await PlayerAliasEnricher(repository, translator).enrich_missing(batch_size=2)
    assert await repository.directory_counts() == {
        "players": 2,
        "localized": 0,
        "aliases": 0,
        "ranked_atp": 0,
        "ranked_wta": 0,
    }
```

- [ ] **Step 2: Confirm tests fail**

```bash
cd backend
uv run pytest tests/test_player_alias_enrichment.py -v
```

Expected: missing enrichment types.

- [ ] **Step 3: Implement the translator adapter**

Use `AsyncOpenAI` with existing `llm_api_key`, `llm_base_url`, `llm_model`, timeout and `extra_body={"enable_thinking": False}`. Send one system instruction and one compact JSON user payload. Require a single JSON object shaped as `{"players": [...]}`; strip only a surrounding Markdown fence before `json.loads`, then validate with Pydantic. Do not retry malformed semantic output inside the same command.

- [ ] **Step 4: Implement batch identity validation and Chinese aliases**

Before any write, require returned IDs to equal input IDs exactly. Validate all translations, derive `preferred/full/surname` aliases through `normalize_player_name`, stamp `source=llm`, configured model and `PLAYER_NAME_PROMPT_VERSION`, build one `LocalizedNameUpdate` per input, then call `save_localized_names()` exactly once for the complete batch.

- [ ] **Step 5: Extend the CLI**

```bash
cd backend
uv run python -m app.players.cli enrich-zh --batch-size 25
uv run python -m app.players.cli enrich-zh --batch-size 5 --max-batches 1
uv run python -m app.players.cli status
```

Reject batch sizes outside `1..50`. stdout contains only translated/skipped/failed counts and coverage percentages.

- [ ] **Step 6: Run deterministic and real LLM gates**

```bash
cd backend
uv run pytest tests/test_player_alias_enrichment.py -v
TENNIX_RUN_PLAYER_ALIAS_LLM_LIVE=1 uv run pytest -m player_alias_llm_live tests/live/test_player_alias_enrichment_live.py -v
```

The real test uses a rollback transaction or dedicated fixture players, sends no external IDs/API payloads, asserts valid Chinese output for a bounded 2-player batch, then runs the same enrichment twice to prove the second call makes no model request.

- [ ] **Step 7: Enrich the local directory and enforce coverage**

Run `enrich-zh` until `status` reports `localized == players` for the publishable singles directory. If a batch fails, fix the parser/prompt with a deterministic regression before rerunning; do not manually mark untranslated rows complete.

- [ ] **Step 8: Prove the web runtime does not instantiate the translator**

Add an import/constructor spy around `create_app()` and assert no `AsyncOpenAI` or `PlayerNameTranslator` is constructed for fake, replay or api_tennis web modes.

- [ ] **Step 9: Commit and close T47**

Commit code/tests, record model name but no request content or key, record coverage counts, mark T48 ready and push both product/control commits.

---

### T48: Add the Deterministic PlayerResolver and Cut Runtime Queries to Internal IDs

**Outcome:** 英文全名、姓氏、供应商缩写、中文名、姓名倒序及重音变体解析为统一内部 ID；API-Tennis 查询不再扫描比赛按名字匹配。

**Files:**

- Create: `backend/app/players/resolver.py`
- Create: `backend/tests/test_player_resolver.py`
- Modify: `backend/app/players/models.py`
- Modify: `backend/app/service.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/providers/api_tennis.py`
- Modify: `backend/tests/test_service.py`
- Modify: `backend/tests/test_api_tennis_provider.py`
- Modify: `backend/tests/test_p1_acceptance.py`

**Interfaces:**

- Produces:

```python
class PlayerResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"

class PlayerCandidate(FrozenModel):
    player: Player
    matched_alias: str
    alias_kind: PlayerAliasKind
    current_rank: int | None = None

class PlayerResolution(FrozenModel):
    status: PlayerResolutionStatus
    query: str
    player: Player | None = None
    candidates: tuple[PlayerCandidate, ...] = ()

class PlayerResolver:
    async def resolve(
        self,
        query: str,
        *,
        context_player_ids: tuple[str, ...] = (),
        limit: int = 5,
    ) -> PlayerResolution: ...
```

- `TennisService` additions:

```python
async def resolve_player(self, query: str, *, context_player_ids: tuple[str, ...] = ()) -> PlayerResolution: ...
async def list_matches_by_player_id(self, status: str, player_id: str) -> list[Match]: ...
async def find_player_matches_by_id(self, player_id: str, time_scope: MatchTimeScope) -> list[Match]: ...
```

- Consumes: T45 repository, T46 normalizer. Does not consume T47 translator.

- [ ] **Step 1: Claim T48 and write resolver acceptance tests**

Parameterize the three approved identity groups and all normalization variants. Add two `Wang` candidates for Home ambiguity and a match context containing one candidate for unique resolution.

```python
@pytest.mark.parametrize("query", [
    "Ben Shelton", "Shelton", "B. Shelton", "本·谢尔顿", "谢尔顿",
])
async def test_shelton_aliases_resolve_same_player(resolver, query):
    result = await resolver.resolve(query)
    assert result.status is PlayerResolutionStatus.RESOLVED
    assert result.player.id == "ply_shelton"
```

Assert an empty query raises `invalid_request`, while unknown non-empty text returns `NOT_FOUND` without provider calls.

- [ ] **Step 2: Write provider/service regression failures**

Assert `find_player_matches("Ben Shelton", NEXT)` resolves local alias then calls provider with `ply_shelton`; assert the API-Tennis adapter request contains `player_key` but never calls `get_livescore`/unfiltered `get_fixtures` for identity discovery. Add a call recorder proving runtime resolution makes zero LLM calls.

- [ ] **Step 3: Confirm tests fail**

```bash
cd backend
uv run pytest tests/test_player_resolver.py tests/test_service.py tests/test_api_tennis_provider.py -v
```

Expected: missing resolver and current Ben/full-name regression failure.

- [ ] **Step 4: Implement resolver ordering and context rules**

Normalize once, fetch exact alias matches, de-duplicate by player ID, order kinds as `preferred/full/provider → reordered/abbreviated/transliterated → surname`, then rank/null-rank/internal-ID. Return resolved only for one candidate or exactly one candidate in `context_player_ids`; otherwise return all bounded candidates as ambiguous. Ranking orders candidates but never merges them.

- [ ] **Step 5: Split name resolution from match retrieval in TennisService**

Move the existing time-window logic into `find_player_matches_by_id()`. Name-based public methods call `resolve_player()` and translate ambiguous/not_found to existing typed REST errors only where an endpoint expects exceptions. Keep a legacy provider-search fallback only when no resolver is injected, so old LiveTennis/fake unit contracts remain operable during migration; `create_app` must inject the repository resolver for `api_tennis`.

- [ ] **Step 6: Remove API-Tennis runtime scan from `search_players()`**

The API-Tennis adapter method must no longer request unfiltered live/upcoming windows. Inject `PlayerDirectoryRepository` into `ApiTennisProvider`; `search_players()` delegates to that local repository when present and raises typed `unsupported` when absent. Production `TennisService.search_players()` uses the same repository through `PlayerResolver`. Delete constants used only by the three-day scan and update tests to assert no such requests occur.

In `create_app`, use `PostgresPlayerDirectoryRepository` for `api_tennis`, `MemoryPlayerDirectoryRepository` for `fake`, and the legacy provider-search fallback for `livetennis`/`replay`. During fake app lifespan only, run one in-memory standings/alias sync so Playwright has deterministic player pages; real API-Tennis startup must never auto-sync or consume quota.

- [ ] **Step 7: Run focused, P1 and full deterministic regressions**

```bash
cd backend
uv run pytest tests/test_player_resolver.py tests/test_service.py tests/test_api_tennis_provider.py tests/test_p1_acceptance.py -v
uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure and not player_alias_llm_live" -q
```

- [ ] **Step 8: Run a real provider query by alias**

With the local directory already synced/enriched, resolve `Ben Shelton`, `B. Shelton`, `谢尔顿` and assert one internal ID, then call next/live provider paths by that ID. Log only internal ID and result counts.

- [ ] **Step 9: Commit and close T48**

Record the exact aliases and no-scan evidence in controls, mark T49 ready and push.

---

### T49: Expose Rankings, Profile, and Five-Season Result APIs

**Outcome:** FastAPI 提供稳定的 rankings/search/profile/results DTO，支持 Top 200、全目录搜索、赛季详情和分页筛选，并保持历史按需查询。

**Files:**

- Create: `backend/tests/test_player_api.py`
- Create: `backend/tests/test_player_profile_service.py`
- Modify: `backend/app/players/models.py`
- Modify: `backend/app/players/providers.py`
- Modify: `backend/app/providers/api_tennis_dtos.py`
- Modify: `backend/app/providers/api_tennis.py`
- Modify: `backend/app/providers/fake.py`
- Modify: `backend/app/service.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/fixtures/api_tennis/players.json`
- Modify: `backend/tests/test_api_tennis_provider.py`
- Modify: `backend/tests/test_api.py`
- Modify: `backend/tests/test_p2_api.py`

**Interfaces:**

- Produces canonical models:

```python
class ResultOutcome(StrEnum):
    ALL = "all"
    WON = "won"
    LOST = "lost"

class SurfaceRecord(FrozenModel):
    won: int = Field(ge=0)
    lost: int = Field(ge=0)

class PlayerSeasonRecord(FrozenModel):
    season: int
    matches_won: int = Field(ge=0)
    matches_lost: int = Field(ge=0)
    titles: int = Field(ge=0)
    hard: SurfaceRecord | None = None
    clay: SurfaceRecord | None = None
    grass: SurfaceRecord | None = None

class PlayerProfileData(FrozenModel):
    player: Player
    birth_date: date | None = None
    image_url: str | None = None
    seasons: tuple[PlayerSeasonRecord, ...] = ()

class PlayerProfileView(FrozenModel):
    profile: PlayerProfileData
    selected_season: int
    season_record: PlayerSeasonRecord | None
    current_match: Match | None = None

class RankingPage(FrozenModel):
    tour: Tour
    page: int
    page_size: int
    total: int
    entries: tuple[RankingEntry, ...]
    as_of: datetime
    availability: CapabilityStatus

class PlayerResultPage(FrozenModel):
    player: Player
    season: int
    tiers: tuple[CircuitTier, ...]
    outcome: ResultOutcome
    page: int
    page_size: int
    total: int
    matches: tuple[Match, ...]
    availability: CapabilityStatus
```

- Provider additions:

```python
class PlayerProfileProvider(Protocol):
    async def get_player_profile(self, player_id: str) -> PlayerProfileData: ...
    async def get_player_results_for_period(self, player_id: str, *, start: date, end: date) -> tuple[Match, ...]: ...
```

- API endpoints:

```text
GET /api/v1/players/rankings?tour=ATP&page=1&page_size=50&country=CHN
GET /api/v1/players/search?q=谢尔顿&limit=10
GET /api/v1/players/{player_id}?season=2026
GET /api/v1/players/{player_id}/results?season=2026&tier=ATP&outcome=won&page=1&page_size=20
```

- [ ] **Step 1: Claim T49 and write failing route/service tests**

Test static route precedence, tour enum, fixed page sizes, page bounds, Top 200 cap, China filter, outside-rank search, unknown ID, optional profile fields, selected season, live-over-next priority, exact empty copy represented by `current_match=None`, five-year boundary, tier/outcome filters, result total/page and no surface parameter.

```python
async def test_rankings_are_top_200_official_order(client):
    response = await client.get("/api/v1/players/rankings", params={"tour": "ATP", "page": 4, "page_size": 50})
    assert response.status_code == 200
    ranks = [item["rank"] for item in response.json()["data"]["entries"]]
    assert ranks == list(range(151, 201))
```

- [ ] **Step 2: Confirm tests fail before endpoints/models exist**

```bash
cd backend
uv run pytest tests/test_player_profile_service.py tests/test_player_api.py -v
```

- [ ] **Step 3: Expand API-Tennis profile DTOs**

Add `player_logo` and the documented `hard_won/hard_lost/clay_won/clay_lost/grass_won/grass_lost` fields. Parse only `type == singles`, preserve unavailable surfaces as `None`, and compute no values from blanks. Profile returns full English name when available, otherwise provider name; local directory remains the source for Chinese name.

- [ ] **Step 4: Add bounded season result retrieval**

Convert `season` to `[Jan 1, Dec 31]`, call `get_fixtures` with `player_key`, `date_start`, `date_stop`, map finished singles matches, sort newest first and return all rows for that bounded year. Service applies canonical tier/outcome filters and slices page 20. Do not persist these fetched pages or call `get_draw` merely to obtain surface.

- [ ] **Step 5: Implement service composition and cache policy**

Rankings read PostgreSQL directly. Profile fetch is cached 1 hour with 60-second negative cache; live/next reuse existing match caches. One-season raw result set is cached 10 minutes, empty/unavailable 60 seconds. `current_match` selects live first, else earliest future scheduled, else `None`.

- [ ] **Step 6: Add response schemas and routes**

Register `/players/rankings` and `/players/search` before `/players/{player_id}`. Fix `page_size` with `Literal[50]` for rankings and `Literal[20]` for results. Search returns a `PlayerResolution` data envelope for resolved/ambiguous/not_found, never supplier IDs.

- [ ] **Step 7: Run focused and full backend gates**

```bash
cd backend
uv run pytest tests/test_player_api.py tests/test_player_profile_service.py tests/test_api_tennis_provider.py tests/test_p2_api.py -v
uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure and not player_alias_llm_live" -q
```

- [ ] **Step 8: Run real profile/history smoke**

Exercise one Top 200 and one locally known outside-Top-200 player. Assert profile mapping and at least one bounded season request completes or returns honest unavailable; never claim a nonempty history if the supplier returns none.

- [ ] **Step 9: Commit and close T49**

Record endpoints, cache bounds, real smoke result and test counts; mark T50 ready and push.

---

### T50: Route Home and Match Chat Through the Shared Resolver

**Outcome:** 所有按名字的 Chat 工具共用 PlayerResolver；消歧/未找到会自然追问并以 `done` 完成，不再出现“查询失败（not_found）”。

**Files:**

- Modify: `backend/app/chat/models.py`
- Modify: `backend/app/chat/tools.py`
- Modify: `backend/app/chat/executor.py`
- Modify: `backend/app/chat/orchestrator.py`
- Modify: `backend/app/service.py`
- Modify: `backend/tests/test_chat_tools.py`
- Modify: `backend/tests/test_chat_orchestrator.py`
- Modify: `backend/tests/test_chat_api.py`
- Modify: `backend/tests/live/test_llm_live.py`
- Modify: `frontend/lib/api/types.ts` (`StructuredData.resolution`)
- Modify: `frontend/hooks/use-chat-stream.ts` if its type narrowing rejects the new result kind
- Modify: `frontend/components/home/home-assistant.tsx` (compact ambiguity candidate list)

**Interfaces:**

- Extend tool data without breaking match cards:

```python
class StructuredToolResult(BaseModel):
    kind: Literal["matches", "match", "intelligence", "player_resolution", "unsupported"]
    matches: list[Match] = Field(default_factory=list)
    packet: IntelligencePacket | None = None
    resolution: PlayerResolution | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    answer_context: AnswerContext | None = None
```

- `BusinessTools` helper behavior:

```python
async def _resolve_player_query(self, query: str, context: ChatContext) -> Player | StructuredToolResult:
    context_ids = tuple(player.id for player in context.snapshot.match.players) if context.snapshot else ()
    result = await self._service.resolve_player(query, context_player_ids=context_ids)
    if result.status is PlayerResolutionStatus.RESOLVED:
        return result.player
    return StructuredToolResult(kind="player_resolution", resolution=result)
```

- [ ] **Step 1: Claim T50 and write failing tool/SSE tests**

Cover each name-bearing tool: `find_player_matches`, filtered `get_live_matches`, `get_player_results`, both sides of `get_head_to_head`. Prove Match context uniquely resolves a surname and Home ambiguity returns candidates.

```python
async def test_not_found_is_recoverable_and_stream_ends_done(orchestrator):
    events = [event async for event in orchestrator.stream(request("不存在的球员下一场？"))]
    assert any(e.type is ChatEventType.DATA and e.payload["kind"] == "player_resolution" for e in events)
    assert not any(e.type is ChatEventType.ERROR for e in events)
    assert events[-1].type is ChatEventType.DONE
```

- [ ] **Step 2: Confirm current behavior fails**

```bash
cd backend
uv run pytest tests/test_chat_tools.py tests/test_chat_orchestrator.py tests/test_chat_api.py -v
```

Expected: current `not_found` is unavailable/error and Chinese aliases do not execute the target service call.

- [ ] **Step 3: Implement one resolver helper in BusinessTools**

Delete `_context_player()`'s independent regex identity logic. Every name-bearing branch must call `_resolve_player_query()` and stop with a `player_resolution` result when unresolved. Resolved branches call only by-ID service methods.

- [ ] **Step 4: Make executor/orchestrator treat resolution as success**

`ToolBatchExecutor` keeps `player_resolution` as `SUCCESS`. `_model_tool_result()` includes only public candidate fields. Add system guidance: when status is ambiguous, ask the user to choose from candidates; when not_found, request full English/Chinese name, country or event. The synthesis path still emits data before text and always emits `done` unless an actual infrastructure failure occurs.

- [ ] **Step 5: Preserve bilingual answer style**

When a resolved `Player` has `localized_name`, model facts contain display name `English（中文）` for first mention. Do not inject provenance or translation-method wording. Existing match cards remain sourced from structured matches.

- [ ] **Step 6: Update frontend stream types conservatively**

Add `PlayerResolutionDto` and keep the existing Home answer layout. Render ambiguous candidates as a compact list of English name, Chinese name, country and rank; clicking a candidate links to `/players/{internal_id}`. Unknown names render prose/empty state, not the red infrastructure error panel.

- [ ] **Step 7: Run deterministic and real LLM gates**

```bash
cd backend
uv run pytest tests/test_chat_tools.py tests/test_chat_orchestrator.py tests/test_chat_api.py tests/test_p1_acceptance.py -v
uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure and not player_alias_llm_live" -q
TENNIX_RUN_LLM_LIVE=1 uv run pytest -m llm_live tests/live/test_llm_live.py -v
```

Real cases: `Ben Shelton`, `Shelton`, `谢尔顿`, `郑钦文`; one ambiguous fixture and one unknown name must end `done` with natural clarification.

- [ ] **Step 8: Run frontend regression and commit**

```bash
cd frontend
pnpm test
pnpm typecheck
pnpm build
```

Commit backend/frontend changes, record real SSE event order and test counts, mark T51 ready and push.

---

### T51: Connect the v0 Player Pages to Real Structured APIs

**Outcome:** v0 页面在 production routes 消费 FastAPI 真实数据，完整支持 loading/empty/partial/error/stale、筛选分页和内部 ID 导航，视觉保持 T43 基线。

**Files:**

- Create: `frontend/app/api/players/rankings/route.ts`
- Create: `frontend/app/api/players/[playerId]/route.ts`
- Create: `frontend/app/api/players/[playerId]/results/route.ts`
- Create: `frontend/lib/player-view-models.ts`
- Create: `frontend/lib/player-view-models.test.ts`
- Create: `frontend/e2e/player-directory.spec.ts`
- Modify: `frontend/app/api/players/search/route.ts` (forward the new resolution response unchanged)
- Modify: `frontend/app/players/page.tsx`
- Modify: `frontend/app/players/[playerId]/page.tsx`
- Modify: all T43 player components to accept production data/state without changing visual structure
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/api/client.ts`
- Modify: `frontend/lib/api/client.test.ts`
- Modify: `frontend/lib/server/backend-proxy.test.ts`

**Interfaces:**

- Produces client calls:

```ts
getPlayerRankings(params: { tour: 'ATP' | 'WTA'; page: number; country?: string }, signal?: AbortSignal): Promise<RankingPageDto>
searchPlayerDirectory(query: string, limit?: number, signal?: AbortSignal): Promise<PlayerResolutionDto>
getPlayerProfile(playerId: string, season?: number, signal?: AbortSignal): Promise<PlayerProfileViewDto>
getPlayerResults(playerId: string, params: { season: number; tiers: CircuitTier[]; outcome: 'all' | 'won' | 'lost'; page: number }, signal?: AbortSignal): Promise<PlayerResultPageDto>
```

- [ ] **Step 1: Claim T51 and write failing API/client/view-model tests**

Test exact query forwarding, encoded IDs, no auth/cookies forwarded, backend failures mapped through existing `ApiError`, English-primary display, optional Chinese fallback, `暂无当前排名`, movement labels, age from birth date, win rate with zero matches and exact empty copy.

- [ ] **Step 2: Confirm tests fail**

```bash
cd frontend
pnpm test -- lib/api/client.test.ts lib/player-view-models.test.ts components/players/players-page.test.tsx components/players/player-profile-page.test.tsx
```

- [ ] **Step 3: Add DTOs, clients and thin Route Handlers**

Each route is `runtime='nodejs'`, `dynamic='force-dynamic'` and one `proxyBackend()` call. Never read API-Tennis or LLM env vars in frontend. Client methods use `URLSearchParams`, repeat `tier` values, and preserve AbortError behavior.

- [ ] **Step 4: Connect rankings/search state without visual changes**

URL query is the restorable state: `tour`, `page`, `country`, `q`. No `q` fetches rankings; nonempty `q` fetches directory search and may show outside-Top-200 candidates. A changed tab/filter/query resets page to 1 and aborts the prior request.

- [ ] **Step 5: Connect profile/results state**

Fetch profile and selected results in parallel. Season/tier/outcome/page changes refetch only results unless season also changes the profile summary. Show live/next card from `current_match`; `null` renders exact `暂无比赛信息`. Finished rows link to `/matches/{internalMatchId}`.

- [ ] **Step 6: Implement truthful state handling**

- loading keeps v0 skeleton geometry;
- stale keeps data visible with stale badge;
- partial keeps data visible with a concise availability notice;
- not_found uses page-level empty state;
- backend/provider failure uses retry panel;
- an empty filtered result never silently broadens filters.

- [ ] **Step 7: Run frontend unit/type/build gates**

```bash
cd frontend
pnpm test
pnpm typecheck
pnpm build
```

- [ ] **Step 8: Run deterministic functional and visual Playwright**

```bash
cd frontend
pnpm test:e2e --grep "player directory"
pnpm test:e2e --grep "player directory visual"
```

Both viewports must cover ATP→WTA, China filter, Chinese search, outside-rank result, profile, season/filter/page, Finished Match navigation and empty current status. T43 visual baselines must pass without update.

- [ ] **Step 9: Run existing Home/Match regression and commit**

```bash
cd frontend
pnpm test:e2e --grep "P1|P2|prototype"
```

Commit frontend integration, record exact pass/fail baseline and known unrelated failures truthfully, mark T52 ready and push.

---

### T52: Run the P2.6 Real-Service Completion Gate and Close the Milestone

**Outcome:** 数据、resolver、Chat、API、v0 视觉和真实浏览器链路全部通过；三份总控可让下一 ADE 从 P3 设计开始。

**Files:**

- Create: `backend/tests/live/test_player_directory_end_to_end_live.py`
- Create: `frontend/e2e/player-directory-live.spec.ts`
- Modify: `docs/runbooks/p2-local.md`
- Modify: `.env.example` (document `TENNIX_RUN_PLAYER_ALIAS_LLM_LIVE` and `TENNIX_RUN_PLAYER_DIRECTORY_E2E_LIVE` as disabled opt-in flags; never add a credential value)
- Modify: `backend/pyproject.toml` (register `player_directory_e2e_live` marker)
- Modify: `frontend/playwright.config.ts` (add explicit `TENNIX_E2E_API_TENNIS=1` provider selection for the bounded live spec)
- Modify: `PROJECT.md`
- Modify: `ROADMAP.md`
- Modify: `CURRENT.md`
- Modify: task-relevant test files only when the completion gate exposes a reproducible defect

**Completion matrix:**

```text
directory sync → Chinese enrichment → alias resolution
       ↓                    ↓
rankings/profile/results    Home + Match Chat
       ↓                    ↓
Next Route Handlers → v0 player pages → Finished Match
```

- [ ] **Step 1: Claim T52 and add one automated end-to-end live test**

The backend live test reads root `.env`, requires explicit `TENNIX_RUN_PLAYER_DIRECTORY_E2E_LIVE=1`, performs bounded real calls, logs only internal IDs/counts, and asserts:

```python
assert_same_id("Ben Shelton", "B. Shelton", "Shelton", "本·谢尔顿", "谢尔顿")
assert_same_id("Qinwen Zheng", "Zheng Qinwen", "Q. Zheng", "郑钦文")
assert_same_id("Novak Djokovic", "N. Djokovic", "Djokovic", "德约科维奇")
```

It also validates one profile and one season result page without requiring a nonempty supplier response.

- [ ] **Step 2: Run migration, sync, enrichment and coverage gates from a clean local database**

```bash
docker compose up -d postgres redis
cd backend
uv run alembic upgrade head
uv run python -m app.players.cli sync
uv run python -m app.players.cli enrich-zh --batch-size 25
uv run python -m app.players.cli status
```

Required report: both tours present; publishable players have 100% English/Chinese preferred-name coverage; rerunning sync/enrich changes no identities and makes zero unnecessary LLM calls.

- [ ] **Step 3: Run all backend gates**

```bash
cd backend
uv run pytest -m "not llm_live and not provider_live and not end_to_end_live and not api_tennis_live and not realtime_live and not infrastructure and not player_alias_llm_live and not player_directory_e2e_live" -q
uv run pytest -m infrastructure -v
TENNIX_RUN_API_TENNIS_LIVE=1 uv run pytest -m api_tennis_live -v
TENNIX_RUN_LLM_LIVE=1 uv run pytest -m llm_live -v
TENNIX_RUN_PLAYER_DIRECTORY_E2E_LIVE=1 uv run pytest -m player_directory_e2e_live tests/live/test_player_directory_end_to_end_live.py -v
```

Every invoked suite must have an actual result; skipped credentials or quota failures are not completion evidence for their respective real gate.

- [ ] **Step 4: Run all frontend and browser gates**

```bash
cd frontend
pnpm test
pnpm typecheck
pnpm build
pnpm test:e2e
TENNIX_E2E_API_TENNIS=1 TENNIX_E2E_REAL_LLM=1 pnpm exec playwright test e2e/player-directory-live.spec.ts
```

No visual snapshots may be updated in T52. Resolve task-caused failures at the narrowest layer; preserve unrelated user files.

- [ ] **Step 5: Run the real browser journey at both viewports**

With `TENNIX_PROVIDER_MODE=api_tennis` and real LLM enabled, verify:

1. `/players` ATP ranking and WTA switch;
2. country + China quick filter;
3. `谢尔顿` search resolves Ben Shelton and opens profile;
4. season/tier/W-L filters and pagination;
5. historical result opens Finished Match;
6. Home questions `Ben Shelton 下一场什么时候？`、`Shelton 今天有比赛吗？`、`谢尔顿现在比分多少？`、`郑钦文这个赛季战绩如何？`；
7. Match questions `谢尔顿这场一发怎么样？`、`Shelton 现在在发球吗？`；
8. ambiguous and unknown inputs end with `done`, candidate/helpful clarification and no red infrastructure error.

Wait for every Chat stream to finish before judging. Browser console must contain no task-caused error/warning; network payloads must contain no external IDs or secrets.

- [ ] **Step 6: Run leakage and repository hygiene checks**

```bash
git diff --check
git grep -nE 'player_key|first_player_key|second_player_key|APIkey' -- ':!backend/app/providers/**' ':!backend/tests/**' ':!docs/**'
git status --short --branch
git log -1 --oneline
```

Review every hit. Expected production business/API/frontend hit count for supplier fields is zero. Confirm pre-existing untracked files were neither added nor modified.

- [ ] **Step 7: Update the local runbook**

Document exact infrastructure start, migration, directory sync, Chinese enrichment, normal app start, deterministic tests and opt-in real gates. Explicitly state quota-sensitive commands and that `enrich-zh` only processes missing rows.

- [ ] **Step 8: Commit final fixes/runbook and close P2.6**

Commit any final task-scoped product/runbook changes. Then update:

- `PROJECT.md`: P2.6 delivered capability and stable identity/search contract;
- `ROADMAP.md`: T52 and P2.6 `done`, exact completion commits/evidence, P3 remains `planned`;
- `CURRENT.md`: no active implementation, latest verified product commit, all real and deterministic gate results, next action is P3 design only after user authorization.

Commit the final control update separately and push `origin/main`. Verify local `main`, remote `origin/main`, controls and HEAD agree.

## Final P2.6 Completion Gate

P2.6 may be marked `done` only when all statements are true:

1. ATP/WTA standings sync is real, bounded and idempotent.
2. `/players` displays official Top 200 order, 50 rows/page, ATP/WTA, country and China filters.
3. Search covers the full local singles directory, including Top 200 outside/no-rank cases.
4. Every publishable player has preferred English and Chinese names; English is primary in UI.
5. Existing translations are not regenerated; malformed batches write nothing.
6. Runtime PlayerResolver makes no translation LLM call and no supplier text-search call.
7. Approved Shelton/Zheng/Djokovic alias matrices resolve to stable internal IDs.
8. Ambiguous surnames return candidates; Match context resolves only a unique participant.
9. Profile exposes only available supplier fields and never guesses missing values.
10. Results cover current plus four prior seasons, 20/page, tier and W/L; no surface filter.
11. Historical data remains on-demand; no full supplier history mirror exists.
12. Home/Match Chat use the same resolver and unresolved names end with SSE `done`.
13. Public REST/SSE/HTML contain no supplier IDs, keys or alias provenance.
14. `/players` and profile preserve approved v0 desktop/mobile visuals.
15. Finished result navigation reuses the existing Match Page.
16. Deterministic backend, infrastructure, frontend, typecheck, build and full Playwright pass.
17. Real API-Tennis, real LLM, directory E2E and real browser journeys actually ran and passed.
18. Home/Match P1/P2 functionality and visual baselines have no task-caused regression.
19. `PROJECT.md`、`ROADMAP.md`、`CURRENT.md`、Git HEAD 和 `origin/main` 一致。
20. P3、双打、Player Chat、运行时翻译/RAG 和云调度仍未被提前实现。
