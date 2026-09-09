# TennixAI P2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在本地交付 API-Tennis 驱动的 Live Match Intelligence：高级别优先的 Home、按需 WebSocket 实时比赛、PBP、技术统计、近期控制指数、轻量历史/H2H 和带版本的上下文 Chat。

**Architecture:** FastAPI 与独立 Realtime Worker 共享 canonical domain 和 repository contracts。Worker 将 API-Tennis REST/WebSocket 归并为版本化状态，PostgreSQL 保存长期事实，Redis 保存租约、热状态和 pub/sub；浏览器只经 Next.js Route Handlers 获取 REST、Chat SSE 和 Match SSE。

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, httpx, SQLAlchemy async, asyncpg, Alembic, redis-py asyncio, websockets, PostgreSQL, Redis, pytest, Next.js 16, TypeScript 5.7, React 19, Tailwind CSS 4, Vitest, Playwright Chromium, pnpm, uv, Docker Compose

**Spec:** `docs/superpowers/specs/2026-09-09-tennixai-p2-live-match-intelligence-design.md`

## Global Constraints

- P2 完成目标是本地完整运行和私人测试；不得加入云部署、认证、账户或正式公网基础设施。
- API-Tennis 是 P2 默认 REST/live provider；`LiveTennisProvider` 保留为备用 adapter。
- 正常 live 更新使用 API-Tennis WebSocket；REST 只用于初始 snapshot、重连 reconcile 和受限 fallback。
- 浏览器只访问 Next.js 同源 `/api/*`；供应商、PostgreSQL、Redis 和 LLM 凭据只存在于服务端。
- 任何日志、异常、fixture、raw payload、文档、SSE 或 Git 提交都不得包含 API key 或带 key 的 URL。
- 供应商字段止于 adapter；公共模型和业务逻辑不得出现 `event_key`、`event_first_player` 等 vendor 字段。
- PostgreSQL 保存 identity、canonical live/PBP/statistics/control/quality；Redis 只保存租约、热状态和 pub/sub。
- Raw provider payload 保留 14 天；on-demand history/H2H 不做本地完整镜像。
- `live_odds`、预测、市场、edge、confidence 和交易属于 P3，P2 代码、DTO、UI、数据库都不得出现这些能力。
- Home 默认 `ATP + WTA / 全部性别 / 单打`，排序为 `ATP/WTA → Challenger → ITF → other`。
- Recent Control Index 是描述性指标；必须做发球校正、版本化校准和 EWMA，不使用关键分固定倍率。
- PBP/statistics 缺失不等于零；只能展示供应商提供或从 PBP 严格证明的事实。
- 旧 Chat 回答固定生成时的 `state_version/as_of`；每个新 point 不自动调用 LLM。
- 原型 `/match?status=...` 是视觉真源；生产页面增量替换 P2 占位，不进行无关重设计。
- 默认测试确定且离线；Replay 为主要实时验收，真实 API/LLM 测试 opt-in，并允许在没有 live match 时如实 skip。
- 每个任务先在 `CURRENT.md` 领取并推送领取记录；完成后更新三份总控、提交并推送，任务外未跟踪文件保持原样。

## Planned File Structure

### Backend shared domain and provider

- `backend/app/domain.py`: P2 enums、MatchSnapshot、PointEvent、MatchStatistic、MomentumObservation、DataQuality。
- `backend/app/identity.py`: async identity protocol 与内存实现。
- `backend/app/providers/base.py`: REST query contract 与 `TennisLiveFeedProvider`。
- `backend/app/providers/api_tennis_dtos.py`: permissive vendor-only REST/WebSocket DTO。
- `backend/app/providers/api_tennis_classification.py`: event type 到 canonical facets 的唯一映射。
- `backend/app/providers/api_tennis.py`: API-Tennis REST adapter。
- `backend/app/providers/api_tennis_live.py`: API-Tennis per-match WebSocket adapter。
- `backend/app/providers/replay.py`: 测试专用 deterministic live feed。

### Backend persistence and realtime

- `backend/app/persistence/database.py`: async engine/session factory。
- `backend/app/persistence/models.py`: SQLAlchemy tables。
- `backend/app/persistence/repositories.py`: identity、snapshot、observation 和 raw event repositories。
- `backend/alembic.ini`, `backend/migrations/`: schema migrations。
- `backend/app/realtime/models.py`: reducer input/output 与 typed realtime events。
- `backend/app/realtime/reducer.py`: full-snapshot diff、point append/correction、version advance。
- `backend/app/realtime/leases.py`: Redis viewer leases、demand index 和 grace semantics。
- `backend/app/realtime/publisher.py`: Redis hot snapshot 与 pub/sub。
- `backend/app/realtime/worker.py`: subscription supervisor、REST reconcile、WebSocket、fallback、retention cleanup。

### Backend service, intelligence and API

- `backend/app/service.py`: filtered match catalog、history/H2H、snapshot reads。
- `backend/app/intelligence.py`: compact fact packet builder。
- `backend/app/momentum/calibration.py`: offline calibration command。
- `backend/app/momentum/engine.py`: deterministic Recent Control v1。
- `backend/app/momentum/calibration.v1.json`: committed aggregate parameters and provenance, no raw history。
- `backend/app/api/schemas.py`, `backend/app/api/routes.py`: P2 REST and Match SSE contract。
- `backend/app/chat/models.py`, `backend/app/chat/tools.py`, `backend/app/chat/orchestrator.py`: P2 business tools and immutable answer metadata。
- `backend/app/config.py`, `backend/app/main.py`: settings and process wiring。

### Local runtime

- `compose.yaml`: PostgreSQL and Redis only。
- `backend/.env.example`, `frontend/.env.example`: safe variable names。
- `docs/runbooks/p2-local.md`: migrations、five-part startup、test and recovery commands。

### Frontend

- `frontend/app/api/matches/[matchId]/stream/route.ts`: thin Match SSE proxy。
- `frontend/app/api/players/[playerId]/results/route.ts`, `frontend/app/api/head-to-head/route.ts`: thin history proxies。
- `frontend/lib/api/types.ts`, `frontend/lib/api/client.ts`: P2 DTO、REST 和 SSE parser。
- `frontend/lib/match-filters.ts`: facet state、counts、compatibility 和 deterministic sort。
- `frontend/hooks/use-match-stream.ts`: initial snapshot、versioned delta、visibility lease lifecycle 和 reconcile。
- `frontend/components/home/match-filters.tsx`: stackable Home facets。
- `frontend/components/match/match-statistics.tsx`: grouped available/partial statistics。
- `frontend/components/match/match-points.tsx`: Set→Game→Point disclosure and new-point behavior。
- `frontend/components/match/match-momentum.tsx`: control chart、provisional state 和 key-point annotations。
- `frontend/components/match-page.tsx`, `frontend/components/match/match-main.tsx`: production P2 composition while preserving preview。
- `frontend/e2e/p2-realtime.spec.ts`, `frontend/e2e/p2.visual.spec.ts`: replay-driven functional and visual acceptance。

---

### T21: Extend the Canonical Domain and Provider Contracts

**Files:**
- Modify: `backend/app/domain.py`
- Modify: `backend/app/identity.py`
- Modify: `backend/app/providers/base.py`
- Modify: `backend/app/providers/fake.py`
- Modify: `backend/app/providers/livetennis.py`
- Test: `backend/tests/test_p2_domain.py`
- Test: `backend/tests/test_provider_contract.py`
- Test: `backend/tests/test_livetennis_provider.py`

**Interfaces:**
- Consumes: P1 `Match`, `LiveMatchState`, `TennisDataProvider`, `MemoryIdentityRepository`。
- Produces: `CircuitTier`, `Gender`, `Discipline`, `ConnectionStatus`, `CapabilityStatus`, `PointEvent`, `MatchStatistic`, `MomentumObservation`, `DataQuality`, `HeadToHead`, `MatchSnapshot`, `ProviderLiveEnvelope`, async `IdentityRepository`, extended query provider and live-feed protocol。

- [ ] **Step 1: Write failing canonical model tests**

Add tests that instantiate a complete snapshot and reject invalid state:

```python
def test_match_snapshot_requires_matching_version(match):
    versioned_match = match.model_copy(update={
        "live_state": LiveMatchState(state_version=3, connection_status="live")
    })
    with pytest.raises(ValidationError):
        MatchSnapshot(
            match=versioned_match,
            points=(),
            statistics=(),
            momentum=(),
            quality=(),
            state_version=2,
            as_of=match.freshness.observed_at,
        )


def test_missing_statistic_is_not_zero():
    quality = DataQuality(
        capability="aces",
        status=CapabilityStatus.UNAVAILABLE,
        provider="fake",
        reason="not_reported",
        observed_at=FIXED_NOW,
    )
    assert quality.status is CapabilityStatus.UNAVAILABLE
    assert not hasattr(quality, "value")
```

Run: `cd backend && uv run pytest tests/test_p2_domain.py -v`
Expected: FAIL because P2 models do not exist.

- [ ] **Step 2: Add the exact canonical enums and frozen models**

Keep all datetimes timezone-aware and all public models `extra="forbid"`. `MatchSnapshot` validates that its own version equals `live_state.state_version`; `PointEvent.sequence >= 1`, `revision >= 1`; `MomentumObservation.value` is bounded `-100..100`.

```python
class CircuitTier(StrEnum):
    ATP = "atp"
    WTA = "wta"
    CHALLENGER = "challenger"
    ITF = "itf"
    OTHER = "other"


class TennisLiveFeedProvider(Protocol):
    def stream_match(self, external_match_id: str) -> AsyncIterator[ProviderLiveEnvelope]:
        raise NotImplementedError
```

Add `circuit`, `gender`, and `discipline` to `Tournament`, and add version/connection fields to `LiveMatchState` with backward-compatible defaults for existing P1 fixtures. `MatchSnapshot` uses `match.live_state` as its single live-state source and rejects a top-level `state_version` that differs from it. Preserve `get_match() -> Match` for P1 and add `get_match_snapshot() -> MatchSnapshot` for P2.

- [ ] **Step 3: Make identity access async without changing public IDs**

Define:

```python
class IdentityRepository(Protocol):
    async def get_or_create(self, entity: str, provider: str, external_id: str) -> str:
        raise NotImplementedError

    async def external_id(self, entity: str, provider: str, internal_id: str) -> str | None:
        raise NotImplementedError
```

Convert `MemoryIdentityRepository`, Fake provider and LiveTennis adapter mapping paths to await the contract. Preserve `mat_`, `ply_`, `trn_` and zero vendor-ID leakage.

- [ ] **Step 4: Run domain and compatibility tests**

Run: `cd backend && uv run pytest tests/test_p2_domain.py tests/test_domain.py tests/test_identity.py tests/test_provider_contract.py tests/test_livetennis_provider.py -v`
Expected: PASS, including all former P1 identity/provider assertions.

- [ ] **Step 5: Update governance, commit, and push**

Record actual counts in `CURRENT.md`/`ROADMAP.md`, preserve task-external files, then:

```bash
git add backend/app/domain.py backend/app/identity.py backend/app/providers/base.py backend/app/providers/fake.py backend/app/providers/livetennis.py backend/tests/test_p2_domain.py backend/tests/test_provider_contract.py backend/tests/test_livetennis_provider.py PROJECT.md ROADMAP.md CURRENT.md
git commit -m "feat: extend the P2 canonical domain"
git push origin main
```

### T22: Add PostgreSQL, Redis, Migrations, and Durable Identity

**Files:**
- Create: `compose.yaml`
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`
- Modify: `backend/.env.example`
- Modify: `backend/app/config.py`
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/20260909_0001_p2_core.py`
- Create: `backend/app/persistence/__init__.py`
- Create: `backend/app/persistence/database.py`
- Create: `backend/app/persistence/models.py`
- Create: `backend/app/persistence/repositories.py`
- Test: `backend/tests/test_persistence_models.py`
- Test: `backend/tests/integration/test_postgres_repositories.py`

**Interfaces:**
- Consumes: T21 async `IdentityRepository` and canonical observation models。
- Produces: `Database`, `PostgresIdentityRepository`, `MatchSnapshotRepository`, `RawProviderEventRepository`, and migration-managed P2 schema。

- [ ] **Step 1: Add dependencies and failing schema tests**

Run:

```bash
cd backend
uv add sqlalchemy asyncpg alembic redis websockets
```

Register pytest markers `infrastructure`, `api_tennis_live`, and `realtime_live`. Write tests asserting unique `(provider, external_id)`, point `(match_id, sequence)` identity, revision append, and raw-event cutoff behavior.

Run: `cd backend && uv run pytest tests/test_persistence_models.py -v`
Expected: FAIL because persistence models do not exist.

- [ ] **Step 2: Define local infrastructure and typed settings**

`compose.yaml` contains only `postgres:16` and `redis:7`, named volumes, localhost-bound ports, and healthchecks. Add settings with safe defaults:

```python
database_url: str = "postgresql+asyncpg://tennix:tennix@127.0.0.1:5432/tennix"
redis_url: str = "redis://127.0.0.1:6379/0"
raw_payload_retention_days: int = Field(default=14, ge=1, le=90)
max_live_subscriptions: int = Field(default=8, ge=1, le=100)
viewer_lease_seconds: int = Field(default=45, ge=30, le=120)
subscription_grace_seconds: int = Field(default=60, ge=0, le=300)
```

The compose file contains no provider or LLM credentials.

- [ ] **Step 3: Implement schema and repositories**

Use SQLAlchemy 2 async sessions and explicit repository methods. `PostgresIdentityRepository.get_or_create` uses an insert-on-conflict/read transaction so concurrent processes obtain the same internal ID. Implement focused repositories for identity lookup, current snapshot reads, raw event append/read and retention deletion. The cross-table `save_reduction` transaction is deliberately added in T26 after `LiveReduction` exists. `purge_raw_events(before)` targets only `raw_provider_events.observed_at < before`.

- [ ] **Step 4: Apply and verify migrations against Docker services**

Run:

```bash
docker compose up -d --wait postgres redis
cd backend
uv run alembic upgrade head
uv run pytest -m infrastructure tests/integration/test_postgres_repositories.py -v
uv run alembic downgrade base
uv run alembic upgrade head
```

Expected: repository tests PASS and downgrade/upgrade both exit 0 without touching unrelated databases.

- [ ] **Step 5: Commit and push**

```bash
git add compose.yaml backend/pyproject.toml backend/uv.lock backend/.env.example backend/app/config.py backend/alembic.ini backend/migrations backend/app/persistence backend/tests/test_persistence_models.py backend/tests/integration/test_postgres_repositories.py PROJECT.md ROADMAP.md CURRENT.md
git commit -m "feat: add P2 persistence foundations"
git push origin main
```

### T23: Implement the API-Tennis REST Adapter

**Files:**
- Create: `backend/app/providers/api_tennis_dtos.py`
- Create: `backend/app/providers/api_tennis_classification.py`
- Create: `backend/app/providers/api_tennis.py`
- Modify: `backend/app/providers/__init__.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/.env.example`
- Create: `backend/tests/fixtures/api_tennis/events.json`
- Create: `backend/tests/fixtures/api_tennis/livescore.json`
- Create: `backend/tests/fixtures/api_tennis/fixtures.json`
- Create: `backend/tests/fixtures/api_tennis/h2h.json`
- Create: `backend/tests/fixtures/api_tennis/players.json`
- Test: `backend/tests/test_api_tennis_provider.py`
- Test: `backend/tests/live/test_api_tennis_live.py`

**Interfaces:**
- Consumes: T21 provider contract and T22 durable identity。
- Produces: `ApiTennisProvider` supporting live, fixtures, player, match snapshot, recent results and H2H with canonical output only。

- [ ] **Step 1: Write adapter contract tests from sanitized fixtures**

Tests must assert exact request methods/parameters, UTC conversion, status/server/winner mapping, 22-stat catalog, PBP flags, broad event classification, unknown field tolerance, empty arrays, `success=0`, HTTP/network failure, and no provider field names in serialized canonical output.

```python
@pytest.mark.parametrize(
    ("event_type", "circuit", "gender", "discipline"),
    [
        ("Atp Singles", "atp", "men", "singles"),
        ("Wta Doubles", "wta", "women", "doubles"),
        ("Challenger Men Singles", "challenger", "men", "singles"),
        ("Itf Women Doubles", "itf", "women", "doubles"),
    ],
)
def test_classifies_reliable_event_types(event_type, circuit, gender, discipline):
    assert classify_event_type(event_type) == (
        CircuitTier(circuit), Gender(gender), Discipline(discipline)
    )
```

Run: `cd backend && uv run pytest tests/test_api_tennis_provider.py -v`
Expected: FAIL because the adapter does not exist.

- [ ] **Step 2: Implement permissive vendor DTOs and classification**

Vendor DTOs use aliases matching API-Tennis and `extra="ignore"`; they are imported only by the adapter. Unknown event types map to `other/unknown/unknown`. Do not infer exact ATP 250/500/1000 or Grand Slam grade from tournament names.

- [ ] **Step 3: Implement REST requests and canonical mapping**

Use one `_request(method, params)` path with `APIkey` injected after safe diagnostic metadata is created. Errors expose method and status only, never the full URL. `get_livescore` and `get_fixtures` map inline score/PBP/statistics in one response. `get_H2H` is bounded by service-provided limits.

Wire provider modes as `fake | livetennis | api_tennis`; API-Tennis becomes the documented P2 live default but tests remain fake by default.

- [ ] **Step 4: Run deterministic and opt-in live gates**

Run:

```bash
cd backend
uv run pytest tests/test_api_tennis_provider.py tests/test_provider_contract.py -v
TENNIX_RUN_API_TENNIS_LIVE=1 uv run pytest -m api_tennis_live tests/live/test_api_tennis_live.py -v
```

Expected: fixture tests PASS; live smoke validates REST capability without printing response bodies or secrets.

- [ ] **Step 5: Commit and push**

```bash
git add backend/app/providers/api_tennis_dtos.py backend/app/providers/api_tennis_classification.py backend/app/providers/api_tennis.py backend/app/providers/__init__.py backend/app/config.py backend/app/main.py backend/.env.example backend/tests/fixtures/api_tennis backend/tests/test_api_tennis_provider.py backend/tests/live/test_api_tennis_live.py PROJECT.md ROADMAP.md CURRENT.md
git commit -m "feat: add the API-Tennis REST provider"
git push origin main
```

### T24: Add Match Catalog Filters, History, H2H, and P2 REST APIs

**Files:**
- Modify: `backend/app/service.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/chat/tools.py`
- Test: `backend/tests/test_p2_service.py`
- Test: `backend/tests/test_p2_api.py`
- Test: `backend/tests/test_p1_acceptance.py`

**Interfaces:**
- Consumes: T23 canonical API-Tennis data and existing `AsyncTTLCache`。
- Produces: `MatchCatalog`, `FacetCounts`, deterministic priority sorting, bounded recent results/H2H service methods and REST responses。

- [ ] **Step 1: Write failing service tests for defaults and boundaries**

Cover default facets, explicit combinations, stable sort, zero-count values, Featured choice, yesterday in `Asia/Macau`, recent limit `1..10`, H2H limit `1..10`, partial historical response and cache call counts.

```python
async def test_default_catalog_prefers_top_tour_singles(service):
    catalog = await service.list_catalog(status="upcoming", filters=MatchFilters.default())
    assert catalog.filters.circuits == (CircuitTier.ATP, CircuitTier.WTA)
    assert catalog.filters.disciplines == (Discipline.SINGLES,)
    assert all(item.tournament.circuit in {CircuitTier.ATP, CircuitTier.WTA} for item in catalog.matches)
    assert catalog.featured_match_id == catalog.matches[0].id
```

Run: `cd backend && uv run pytest tests/test_p2_service.py tests/test_p2_api.py -v`
Expected: FAIL because catalog/history APIs do not exist.

- [ ] **Step 2: Implement deterministic filter and sort rules**

Create immutable `MatchFilters.default()` and sort key:

```python
CIRCUIT_PRIORITY = {
    CircuitTier.ATP: 0,
    CircuitTier.WTA: 0,
    CircuitTier.CHALLENGER: 1,
    CircuitTier.ITF: 2,
    CircuitTier.OTHER: 3,
}

def catalog_sort_key(match: Match) -> tuple[int, int, datetime, str]:
    return (
        CIRCUIT_PRIORITY[match.tournament.circuit],
        0 if match.status is MatchStatus.LIVE else 1,
        match.scheduled_at or datetime.max.replace(tzinfo=timezone.utc),
        match.id,
    )
```

Facet counts are computed against the catalog source while respecting the other two active facet groups. Incompatible/zero values are returned, not removed.

- [ ] **Step 3: Add bounded history/H2H service and routes**

Add:

```text
GET /api/v1/players/{player_id}/results?scope=yesterday|recent&limit=1..10
GET /api/v1/head-to-head?first_player_id={internal_id}&second_player_id={internal_id}&limit=1..10
```

Responses distinguish `available`, `partial`, and `unavailable`. Cache successful history/H2H for 10 minutes and empty responses for 60 seconds; never write these response sets into the canonical history tables.

- [ ] **Step 4: Run service/API and P1 regression gates**

Run: `cd backend && uv run pytest tests/test_p2_service.py tests/test_p2_api.py tests/test_service.py tests/test_api.py tests/test_p1_acceptance.py -v`
Expected: PASS; P1 live/upcoming behavior remains valid, and the P1 Chat historical guard remains unchanged until T31 while the new deterministic history REST service is independently verified.

- [ ] **Step 5: Commit and push**

```bash
git add backend/app/service.py backend/app/api/schemas.py backend/app/api/routes.py backend/app/main.py backend/app/chat/tools.py backend/tests/test_p2_service.py backend/tests/test_p2_api.py backend/tests/test_p1_acceptance.py PROJECT.md ROADMAP.md CURRENT.md
git commit -m "feat: add P2 catalog and history services"
git push origin main
```

### T25: Add Stackable Home Facets and Priority Presentation

**Files:**
- Create: `frontend/lib/match-filters.ts`
- Create: `frontend/lib/match-filters.test.ts`
- Create: `frontend/components/home/match-filters.tsx`
- Create: `frontend/components/home/match-filters.test.tsx`
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/api/client.ts`
- Modify: `frontend/lib/view-models.ts`
- Modify: `frontend/components/home-page.tsx`
- Modify: `frontend/components/home/home-match-sections.tsx`
- Modify: `frontend/components/home-page.test.tsx`
- Test: `frontend/e2e/p2-home-filters.spec.ts`

**Interfaces:**
- Consumes: T24 `MatchCatalog` and facet counts。
- Produces: one shared Home filter state used by Featured/Live/Upcoming with required defaults and reset behavior。

- [ ] **Step 1: Write failing state and component tests**

```ts
it('uses the approved default facets', () => {
  expect(DEFAULT_MATCH_FILTERS).toEqual({
    circuits: ['atp', 'wta'],
    genders: [],
    disciplines: ['singles'],
  })
})

it('stacks circuit, gender, and discipline without relaxing filters', () => {
  const result = filterMatches(matches, {
    circuits: ['itf'],
    genders: ['women'],
    disciplines: ['doubles'],
  })
  expect(result.map((match) => match.id)).toEqual(['mat_itf_women_doubles'])
})
```

Run: `cd frontend && pnpm test -- lib/match-filters.test.ts components/home/match-filters.test.tsx`
Expected: FAIL because facet modules do not exist.

- [ ] **Step 2: Implement deterministic filters and accessible controls**

Use existing shadcn primitives. Every facet group has an accessible name, active state, count and disabled state. Empty `genders` means all genders. “恢复默认” sets exactly ATP+WTA/all/singles. Do not auto-select another value when a chosen combination becomes empty.

- [ ] **Step 3: Connect all Home match sections**

Replace `matches[0]` Featured selection with the catalog `featured_match_id` or the first deterministically sorted visible item. Live, Upcoming and Featured all consume the same filtered set. Preserve current cards, spacing, typography and Home chat behavior.

- [ ] **Step 4: Verify unit, browser, and visual behavior**

Run:

```bash
cd frontend
pnpm test
pnpm typecheck
pnpm build
pnpm test:e2e --grep "P2 Home filters|prototype"
```

Expected: all commands exit 0; desktop/mobile show top-tier singles by default and the exact stacked ITF women doubles case when selected.

- [ ] **Step 5: Commit and push**

```bash
git add frontend/lib/match-filters.ts frontend/lib/match-filters.test.ts frontend/components/home/match-filters.tsx frontend/components/home/match-filters.test.tsx frontend/lib/api/types.ts frontend/lib/api/client.ts frontend/lib/view-models.ts frontend/components/home-page.tsx frontend/components/home/home-match-sections.tsx frontend/components/home-page.test.tsx frontend/e2e/p2-home-filters.spec.ts PROJECT.md ROADMAP.md CURRENT.md
git commit -m "feat: add stackable Home match filters"
git push origin main
```

### T26: Build the Canonical Live Reducer and Transactional Persistence

**Files:**
- Create: `backend/app/realtime/__init__.py`
- Create: `backend/app/realtime/models.py`
- Create: `backend/app/realtime/reducer.py`
- Modify: `backend/app/persistence/repositories.py`
- Test: `backend/tests/test_live_reducer.py`
- Test: `backend/tests/integration/test_live_reduction_persistence.py`

**Interfaces:**
- Consumes: T23 provider snapshot mapping and T22 repositories。
- Produces: `LiveReduction`, `reduce_live_snapshot(previous, incoming)`, and atomic `save_reduction(reduction)`。

- [ ] **Step 1: Write failing reducer tests**

Build immutable samples for initial state, identical repeated snapshot, one appended point, corrected prior point, statistics-only change and match terminal state.

```python
def test_identical_supplier_snapshot_does_not_advance_version():
    first = reduce_live_snapshot(None, supplier_snapshot())
    repeated = reduce_live_snapshot(first.snapshot, supplier_snapshot())
    assert repeated.changed is False
    assert repeated.snapshot.state_version == first.snapshot.state_version
    assert repeated.events == ()


def test_point_correction_starts_recompute_at_changed_sequence():
    reduction = reduce_live_snapshot(existing_snapshot(), corrected_snapshot())
    assert reduction.point_revisions[0].sequence == 7
    assert reduction.recompute_from_sequence == 7
```

Run: `cd backend && uv run pytest tests/test_live_reducer.py -v`
Expected: FAIL because reducer types do not exist.

- [ ] **Step 2: Implement canonical diff and version rules**

Fingerprint canonical point identity and values separately. Sequence is stable for unchanged prefixes. A changed old point creates `PointRevision`; inserted/deleted/reordered tails are rebuilt from the first difference. Only a semantic change advances `state_version` by one.

- [ ] **Step 3: Persist before publication**

`save_reduction` writes the latest snapshot, current points, revisions, changed stats and data quality in one transaction. Momentum observations join this transaction in T30. The method returns only after commit; a failed transaction leaves the previous version readable.

- [ ] **Step 4: Run pure and PostgreSQL integration gates**

Run:

```bash
cd backend
uv run pytest tests/test_live_reducer.py -v
uv run pytest -m infrastructure tests/integration/test_live_reduction_persistence.py -v
```

Expected: PASS, with no duplicate points after replaying the same snapshots twice.

- [ ] **Step 5: Commit and push**

```bash
git add backend/app/realtime/__init__.py backend/app/realtime/models.py backend/app/realtime/reducer.py backend/app/persistence/repositories.py backend/tests/test_live_reducer.py backend/tests/integration/test_live_reduction_persistence.py PROJECT.md ROADMAP.md CURRENT.md
git commit -m "feat: add the canonical live reducer"
git push origin main
```

### T27: Add WebSocket Feed, Redis Leases, and the Realtime Worker

**Files:**
- Create: `backend/app/providers/api_tennis_live.py`
- Create: `backend/app/realtime/leases.py`
- Create: `backend/app/realtime/publisher.py`
- Create: `backend/app/realtime/worker.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_api_tennis_live_feed.py`
- Test: `backend/tests/test_realtime_leases.py`
- Test: `backend/tests/test_realtime_worker.py`
- Test: `backend/tests/live/test_api_tennis_websocket_live.py`

**Interfaces:**
- Consumes: T26 reducer/persistence and T23 REST reconciliation。
- Produces: one upstream subscription per demanded match, lease TTL/grace, Redis hot snapshots/pubsub, reconnect/fallback and retention cleanup。

- [ ] **Step 1: Write failing feed, lease, and supervisor tests**

Use fake clocks and fake Redis/feed ports. Assert two viewers create one upstream feed, renewals extend TTL, last release starts 60-second grace, hidden-viewer expiry closes feed, capacity returns `capacity_limited`, reconnect runs REST before accepting more WS deltas, and terminal state closes immediately.

```python
async def test_two_viewers_share_one_upstream_subscription(worker, leases, feed):
    await leases.acquire("mat_live", "viewer_a")
    await leases.acquire("mat_live", "viewer_b")
    await worker.reconcile_demand_once()
    assert feed.opened_external_ids == ["11997372"]
```

Run: `cd backend && uv run pytest tests/test_api_tennis_live_feed.py tests/test_realtime_leases.py tests/test_realtime_worker.py -v`
Expected: FAIL because realtime services do not exist.

- [ ] **Step 2: Implement secret-safe per-match WebSocket adapter**

Connect to the official WSS endpoint with `match_key` and configured timezone. Parse messages into private `ProviderLiveEnvelope`. Exceptions expose a typed reason without serializing the connection URI. Use bounded exponential reconnect delay with injected clock/randomness for tests.

- [ ] **Step 3: Implement Redis coordination and worker lifecycle**

Store viewer leases with expiry, a demanded-match index, hot snapshot JSON and per-match pub/sub. The worker opens only demanded matches, applies 60-second final-viewer grace, writes reduction to PostgreSQL, updates Redis and publishes after commit. Run raw payload cleanup at startup and then once per local day.

REST fallback starts only while WS is unavailable and a viewer lease remains; its minimum interval and backoff come from settings. It stops immediately after WS recovery.

- [ ] **Step 4: Run deterministic and real WebSocket smoke tests**

Run:

```bash
cd backend
uv run pytest tests/test_api_tennis_live_feed.py tests/test_realtime_leases.py tests/test_realtime_worker.py -v
TENNIX_RUN_API_TENNIS_LIVE=1 uv run pytest -m realtime_live tests/live/test_api_tennis_websocket_live.py -v
```

Expected: deterministic tests PASS; live test authenticates and receives a valid event when a live match exists, otherwise records a deliberate skip.

- [ ] **Step 5: Commit and push**

```bash
git add backend/app/providers/api_tennis_live.py backend/app/realtime/leases.py backend/app/realtime/publisher.py backend/app/realtime/worker.py backend/app/config.py backend/.env.example backend/tests/test_api_tennis_live_feed.py backend/tests/test_realtime_leases.py backend/tests/test_realtime_worker.py backend/tests/live/test_api_tennis_websocket_live.py PROJECT.md ROADMAP.md CURRENT.md
git commit -m "feat: add the P2 realtime worker"
git push origin main
```

### T28: Expose Match Snapshots and Versioned SSE to the Browser

**Files:**
- Modify: `backend/app/service.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_match_stream_api.py`
- Create: `frontend/app/api/matches/[matchId]/stream/route.ts`
- Modify: `frontend/lib/server/backend-proxy.ts`
- Modify: `frontend/lib/server/backend-proxy.test.ts`
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/api/client.ts`
- Modify: `frontend/lib/api/client.test.ts`
- Create: `frontend/hooks/use-match-stream.ts`
- Create: `frontend/hooks/use-match-stream.test.tsx`
- Modify: `frontend/components/match-page.tsx`

**Interfaces:**
- Consumes: T27 Redis leases/pubsub and T22/T26 persisted snapshots。
- Produces: `GET /matches/{id}` full P2 snapshot, `GET /matches/{id}/stream` versioned SSE and a browser hook with gap/visibility reconciliation。

- [ ] **Step 1: Write failing backend SSE tests**

Assert `ready`, atomic delta and terminal event framing; every version has at most one `match_delta`; SSE `id` equals version; viewer lease exists only while connection is open; pub/sub gap does not fabricate events; headers disable buffering.

```python
assert frames[0].event == "ready"
assert frames[1].event == "match_delta"
assert frames[1].id == "12"
assert frames[1].data["state_version"] == 12
assert {change["type"] for change in frames[1].data["changes"]} == {
    "score_updated", "point_appended", "statistics_updated"
}
```

Run: `cd backend && uv run pytest tests/test_match_stream_api.py -v`
Expected: FAIL because Match SSE route does not exist.

- [ ] **Step 2: Implement snapshot and SSE service/API**

Initial snapshot reads Redis hot state first, PostgreSQL second, and if neither contains the requested current match, obtains one API-Tennis REST snapshot through `TennisService`, persists it, and returns it. SSE creates a unique viewer ID server-side, renews its lease every 20 seconds, emits heartbeat without changing version, forwards typed pub/sub events, and releases on disconnect. `Last-Event-ID` is accepted for diagnostics; reconnect still reconciles via REST.

- [ ] **Step 3: Write failing frontend stream lifecycle tests**

Tests cover initial REST before stream, atomic typed changes, duplicate versions ignored, version jump forcing one snapshot reload, connection error retaining data, hidden timer closing after 60 seconds, visibility restore performing snapshot then SSE, unmount cleanup and terminal closure.

Run: `cd frontend && pnpm test -- hooks/use-match-stream.test.tsx lib/api/client.test.ts`
Expected: FAIL because Match stream types/hook do not exist.

- [ ] **Step 4: Implement thin proxy, typed parser, and hook**

The new Route Handler reuses `backend-proxy.ts`, forwards `Accept` and `Last-Event-ID`, preserves streaming and never forwards cookie/authorization. `useMatchStream(matchId)` exposes:

```ts
type MatchStreamState = {
  snapshot: MatchSnapshotDto | null
  phase: 'loading' | 'live' | 'reconnecting' | 'stale' | 'ended' | 'error'
  errorCode: string | null
  refresh(): Promise<void>
}
```

Replace `MatchPage` one-time load with this hook while keeping preview mode isolated.

- [ ] **Step 5: Verify, commit, and push**

Run:

```bash
cd backend && uv run pytest tests/test_match_stream_api.py -v
cd ../frontend && pnpm test && pnpm typecheck && pnpm build
```

Then:

```bash
git add backend/app/service.py backend/app/api/schemas.py backend/app/api/routes.py backend/app/main.py backend/tests/test_match_stream_api.py frontend/app/api/matches/'[matchId]'/stream/route.ts frontend/lib/server/backend-proxy.ts frontend/lib/server/backend-proxy.test.ts frontend/lib/api/types.ts frontend/lib/api/client.ts frontend/lib/api/client.test.ts frontend/hooks/use-match-stream.ts frontend/hooks/use-match-stream.test.tsx frontend/components/match-page.tsx PROJECT.md ROADMAP.md CURRENT.md
git commit -m "feat: stream versioned match state"
git push origin main
```

### T29: Render Full PBP and Available Match Statistics

**Files:**
- Create: `frontend/components/match/match-statistics.tsx`
- Create: `frontend/components/match/match-statistics.test.tsx`
- Create: `frontend/components/match/match-points.tsx`
- Create: `frontend/components/match/match-points.test.tsx`
- Modify: `frontend/lib/view-models.ts`
- Modify: `frontend/lib/view-models.test.ts`
- Modify: `frontend/components/match/match-main.tsx`
- Modify: `frontend/components/match-page.test.tsx`

**Interfaces:**
- Consumes: T28 live `MatchSnapshotDto` points/statistics/quality。
- Produces: grouped available statistics and Set→Game→Point timeline with stable live-update behavior。

- [ ] **Step 1: Write failing view-model and component tests**

Tests assert 22 known metric labels/units, available-only rendering, zero distinct from unavailable, partial badge, Set/Game grouping, key-point labels, current group expanded, old groups collapsed, correction notice, new-point auto-follow only when already near the bottom, and “有新分” when reviewing history.

```ts
expect(screen.getByText('ACE 球')).toBeVisible()
expect(screen.getByText('8')).toBeVisible()
expect(screen.getByText('双误暂未提供')).toBeVisible()
expect(screen.queryByText('双误 0')).not.toBeInTheDocument()
```

Run: `cd frontend && pnpm test -- components/match/match-statistics.test.tsx components/match/match-points.test.tsx`
Expected: FAIL because P2 components do not exist.

- [ ] **Step 2: Add canonical-to-presentation mapping**

Map metric enums to Chinese labels and units in one exhaustive record. Group into 发球、接发、关键分、制胜/失误、体能. “最近 10 分” is derived from determinate PointEvents; ignore vendor `Last 10 balls`.

- [ ] **Step 3: Replace production placeholders without touching preview data**

Extract `StatsCard` and the live PBP half of `MomentumCard` into focused components. Preview `/match?status=...` continues to use `match-preview-data.ts`; production uses only snapshot view models. Preserve card order and existing responsive grid.

- [ ] **Step 4: Run frontend and prototype gates**

Run:

```bash
cd frontend
pnpm test
pnpm typecheck
pnpm build
pnpm test:e2e --grep prototype
```

Expected: all pass; prototype snapshots remain unchanged unless a separately reviewed intentional baseline update is documented.

- [ ] **Step 5: Commit and push**

```bash
git add frontend/components/match/match-statistics.tsx frontend/components/match/match-statistics.test.tsx frontend/components/match/match-points.tsx frontend/components/match/match-points.test.tsx frontend/lib/view-models.ts frontend/lib/view-models.test.ts frontend/components/match/match-main.tsx frontend/components/match-page.test.tsx PROJECT.md ROADMAP.md CURRENT.md
git commit -m "feat: render live points and match statistics"
git push origin main
```

### T30: Calibrate and Implement Recent Control Index v1

**Files:**
- Create: `backend/app/momentum/__init__.py`
- Create: `backend/app/momentum/calibration.py`
- Create: `backend/app/momentum/engine.py`
- Create: `backend/app/momentum/calibration.v1.json`
- Modify: `backend/app/realtime/reducer.py`
- Modify: `backend/app/persistence/repositories.py`
- Create: `backend/tests/test_momentum_engine.py`
- Create: `backend/tests/test_momentum_calibration.py`
- Create: `frontend/components/match/match-momentum.tsx`
- Create: `frontend/components/match/match-momentum.test.tsx`
- Modify: `frontend/components/match/match-main.tsx`
- Modify: `frontend/lib/view-models.ts`

**Interfaces:**
- Consumes: determinate canonical PointEvents and match classification from T26/T29。
- Produces: `RecentControlEngine`, versioned aggregate calibration file, persisted observations and prototype-compatible control chart。

- [ ] **Step 1: Write failing formula and invariance tests**

Cover player-swap symmetry, return-point surprise greater than routine serve hold, no future leakage, no update for indeterminate winner, fewer than six points provisional, bounded output, deterministic replay and correction recompute.

```python
def test_player_swap_negates_recent_control(engine, point_history):
    original = engine.compute(point_history, focal_player_id="ply_a")
    swapped = engine.compute(swap_players(point_history), focal_player_id="ply_b")
    assert swapped[-1].value == pytest.approx(-original[-1].value)


def test_key_point_flag_has_no_fixed_numeric_multiplier(engine):
    ordinary = engine.update(history(), point(is_break_point=False))
    flagged = engine.update(history(), point(is_break_point=True))
    assert flagged.value == ordinary.value
```

Run: `cd backend && uv run pytest tests/test_momentum_engine.py tests/test_momentum_calibration.py -v`
Expected: FAIL because the engine does not exist.

- [ ] **Step 2: Implement the calibration command**

The command fetches a bounded recent sample through `TennisDataProvider`, discards matches without sufficient determinate PBP, evaluates candidate EWMA half-lives for responsiveness/stability and computes serve-point priors by `circuit × gender × discipline`. It writes only aggregate JSON containing schema version, generated time, sample counts, prior means/strength, alpha and scale; no raw vendor rows or IDs.

Run with the local ignored key:

```bash
cd backend
uv run python -m app.momentum.calibration --days 30 --max-matches 200 --output app/momentum/calibration.v1.json
```

Review that every cohort has a documented sample count and sparse cohorts use the explicit global fallback.

- [ ] **Step 3: Implement runtime formula and reducer integration**

Use only pre-point history:

```python
residual = 2.0 * (outcome - pre_point_probability)
smoothed = (1.0 - alpha) * previous_smoothed + alpha * residual
value = max(-100.0, min(100.0, 100.0 * smoothed / scale))
```

Apply beta-prior shrinkage to each server’s completed service points. Store algorithm version and input summary. Key-point flags remain annotations and never alter the formula.

- [ ] **Step 4: Render and verify the control chart**

Render the latest 20 observations, zero reference line, leader/value badge, provisional copy, `as_of`, and key-point markers. Keep the current chart/card geometry. Run backend momentum tests plus frontend test/typecheck/build and prototype visual tests.

- [ ] **Step 5: Commit and push**

Never add the input API payload or local key. Commit only the aggregate and task files:

```bash
git add backend/app/momentum backend/app/realtime/reducer.py backend/app/persistence/repositories.py backend/tests/test_momentum_engine.py backend/tests/test_momentum_calibration.py frontend/components/match/match-momentum.tsx frontend/components/match/match-momentum.test.tsx frontend/components/match/match-main.tsx frontend/lib/view-models.ts PROJECT.md ROADMAP.md CURRENT.md
git commit -m "feat: add calibrated recent control"
git push origin main
```

### T31: Add P2 Intelligence Tools and Versioned Chat Answers

**Files:**
- Create: `backend/app/intelligence.py`
- Modify: `backend/app/chat/models.py`
- Modify: `backend/app/chat/tools.py`
- Modify: `backend/app/chat/orchestrator.py`
- Modify: `backend/app/service.py`
- Create: `backend/tests/test_intelligence_packet.py`
- Modify: `backend/tests/test_chat_tools.py`
- Modify: `backend/tests/test_chat_orchestrator.py`
- Modify: `backend/tests/test_chat_api.py`
- Modify: `backend/tests/live/test_llm_live.py`
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/hooks/use-chat-stream.ts`
- Modify: `frontend/hooks/use-chat-stream.test.tsx`
- Modify: `frontend/components/match/match-sidebar.tsx`
- Modify: `frontend/components/match-page.test.tsx`

**Interfaces:**
- Consumes: T24 history/H2H and T28–T30 match snapshot/intelligence。
- Produces: compact `IntelligencePacket`, three P2 business tools and immutable Chat answer metadata。

- [ ] **Step 1: Write failing packet/tool tests**

Assert packet size is bounded, contains no vendor IDs/raw payload/full PBP, selects only requested topic facts, preserves unavailable/partial, and includes `state_version/as_of`. Assert Match scope overrides model-supplied match IDs.

```python
packet = build_intelligence_packet(snapshot, topic=IntelligenceTopic.MOMENTUM)
assert packet.state_version == snapshot.state_version
assert len(packet.recent_points) <= 20
assert "event_key" not in packet.model_dump_json()
assert "api_tennis" not in packet.model_dump_json()
```

Run: `cd backend && uv run pytest tests/test_intelligence_packet.py tests/test_chat_tools.py -v`
Expected: FAIL because P2 packet/tools do not exist.

- [ ] **Step 2: Add exact business tools and capability routing**

Keep P1 tools and add:

```text
get_match_intelligence(topic: overview|score|statistics|points|momentum)
get_player_results(player_name, scope: yesterday|recent, limit: 1..10)
get_head_to_head(first_player_name, second_player_name, limit: 1..10)
```

Replace the blanket historical phrase guard with deterministic supported-scope routing. Broad unsupported history returns typed `unsupported`; provider empty/partial remains distinct.

- [ ] **Step 3: Make answer metadata immutable**

The first structured Match data event carries answer metadata:

```json
{
  "answer_context": {
    "match_id": "mat_example",
    "state_version": 18,
    "as_of": "2026-09-09T08:30:00Z"
  }
}
```

The frontend stores this with each completed answer. When live snapshot version is newer, show “比赛已更新” beside the old answer; do not edit its text or auto-call the LLM.

- [ ] **Step 4: Run deterministic and real LLM gates**

Run:

```bash
cd backend
uv run pytest tests/test_intelligence_packet.py tests/test_chat_tools.py tests/test_chat_orchestrator.py tests/test_chat_api.py -v
TENNIX_RUN_LLM_LIVE=1 uv run pytest -m llm_live tests/live/test_llm_live.py -v
cd ../frontend
pnpm test
pnpm typecheck
pnpm build
```

Expected: deterministic tests PASS; real LLM chooses valid business tools and agrees with canonical facts without exact prose assertions.

- [ ] **Step 5: Commit and push**

```bash
git add backend/app/intelligence.py backend/app/chat/models.py backend/app/chat/tools.py backend/app/chat/orchestrator.py backend/app/service.py backend/tests/test_intelligence_packet.py backend/tests/test_chat_tools.py backend/tests/test_chat_orchestrator.py backend/tests/test_chat_api.py backend/tests/live/test_llm_live.py frontend/lib/api/types.ts frontend/hooks/use-chat-stream.ts frontend/hooks/use-chat-stream.test.tsx frontend/components/match/match-sidebar.tsx frontend/components/match-page.test.tsx PROJECT.md ROADMAP.md CURRENT.md
git commit -m "feat: add versioned match intelligence chat"
git push origin main
```

### T32: Add Replay E2E, Fault Recovery, Runbook, and Final P2 Gate

**Files:**
- Create: `backend/app/providers/replay.py`
- Create: `backend/tests/fixtures/replay/live_match.jsonl`
- Create: `backend/tests/test_replay_provider.py`
- Create: `backend/tests/integration/test_realtime_recovery.py`
- Create: `frontend/e2e/p2-realtime.spec.ts`
- Create: `frontend/e2e/p2.visual.spec.ts`
- Create: `frontend/e2e/__screenshots__/desktop/p2-*.png`
- Create: `frontend/e2e/__screenshots__/mobile/p2-*.png`
- Modify: `frontend/playwright.config.ts`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Create: `docs/runbooks/p2-local.md`
- Modify: `PROJECT.md`
- Modify: `ROADMAP.md`
- Modify: `CURRENT.md`

**Interfaces:**
- Consumes: complete T21–T31 P2 path。
- Produces: deterministic accelerated replay, restart/correction E2E evidence, reviewed visual baselines, real smoke gates and local operator runbook。

- [ ] **Step 1: Write replay and recovery tests before the provider exists**

The sanitized JSONL fixture contains ordered records with relative milliseconds and explicit scenarios: initial snapshot, point append, duplicate, statistics update, correction, disconnect, REST reconcile and terminal state. Tests assert speed scaling and deterministic event order.

```python
async def test_replay_emits_scripted_events_in_order(fake_clock):
    provider = ReplayTennisProvider.from_file(FIXTURE, clock=fake_clock, speed=20.0)
    received = [event.kind async for event in provider.stream_match("replay-live")]
    assert received == [
        "snapshot", "point", "duplicate", "statistics", "correction",
        "disconnect", "reconcile", "finished",
    ]
```

Run: `cd backend && uv run pytest tests/test_replay_provider.py tests/integration/test_realtime_recovery.py -v`
Expected: FAIL because Replay provider does not exist.

- [ ] **Step 2: Implement replay mode and full-process test wiring**

Add provider mode `replay`, fixture path and speed settings. Replay passes through the same reducer, PostgreSQL, Redis, FastAPI SSE and frontend path as API-Tennis. It may replace only the upstream provider; no UI-specific test backdoor is allowed.

- [ ] **Step 3: Add Playwright functional and visual coverage**

Verify at `1440×1000` and `390×844`:

- Home default facets, stacked filter and high-tier Featured。
- Live Match score/server/PBP/statistics/control changes without reload。
- Old PBP inspection does not auto-scroll; new-point notice works。
- Duplicate/correction/reconnect behavior and visible stale status。
- Two browser contexts share one upstream replay subscription。
- Hidden tab releases after 60 seconds and restores via snapshot。
- Chat answer version becomes old after later points while prose stays unchanged。
- Finished event closes stream and shows terminal state。

Generate snapshots only after functional assertions pass; inspect every changed PNG before acceptance.

- [ ] **Step 4: Write and execute the final local runbook**

`docs/runbooks/p2-local.md` includes safe env setup, Docker start/stop, migration, FastAPI/worker/Next commands, Replay acceptance, real REST/WS/LLM gates, reset-free recovery and troubleshooting. It never contains a real key.

Run the full gate from a clean process state:

```bash
docker compose up -d --wait postgres redis
cd backend
uv run alembic upgrade head
uv run pytest -m "not api_tennis_live and not realtime_live and not llm_live and not end_to_end_live" -v
uv run pytest -m infrastructure -v
cd ../frontend
pnpm test
pnpm typecheck
pnpm build
pnpm test:e2e
```

Then run enabled real gates separately. A missing live match is an explicit skip only for the live-push/browser path, not for REST authentication or deterministic Replay.

- [ ] **Step 5: Audit scope, close P2, commit, and push**

Perform these searches and inspect every hit:

```bash
git grep -nE 'live_odds|prediction|edge|polymarket' -- backend frontend ':!frontend/components/match/match-preview-data.ts'
git grep -nE 'event_key|event_first_player|APIkey=' -- backend/app ':!backend/app/providers/api_tennis*'
git diff --check
git status --short --branch
```

Record exact test counts, real skips, screenshot review and completion commits in the three control files. Stage only the T32 paths and commit the implementation:

```bash
git add backend/app/providers/replay.py backend/tests/fixtures/replay/live_match.jsonl backend/tests/test_replay_provider.py backend/tests/integration/test_realtime_recovery.py frontend/e2e/p2-realtime.spec.ts frontend/e2e/p2.visual.spec.ts frontend/e2e/__screenshots__/desktop/p2-*.png frontend/e2e/__screenshots__/mobile/p2-*.png frontend/playwright.config.ts backend/app/config.py backend/app/main.py docs/runbooks/p2-local.md PROJECT.md ROADMAP.md CURRENT.md
git commit -m "test: complete P2 realtime acceptance"
```

Then update the three control files with that implementation commit and the fresh evidence, commit the closure separately with `docs: close P2 live match intelligence`, push `origin/main`, and leave `CURRENT.md` idle with the next phase still requiring explicit approval.

## Final P2 Completion Gate

P2 may be marked `done` only when all statements are supported by fresh evidence:

1. API-Tennis is the default P2 provider and no vendor field escapes adapters.
2. PostgreSQL identity is stable across FastAPI/worker restart; Redis loss is recoverable.
3. One demanded match has one upstream subscription regardless of viewer count.
4. WebSocket is the normal live path; REST polling occurs only for documented reconcile/fallback.
5. Snapshot + versioned SSE + gap reconcile works without browser refresh.
6. Home defaults, stacked facets, counts and tier priority pass unit and Playwright tests.
7. PBP, 22-stat catalog, partial/unavailable states and correction behavior pass deterministic replay.
8. Recent Control uses committed calibration provenance, serve-adjusted residuals and EWMA with no fixed key-point multiplier.
9. Chat receives only compact canonical facts and preserves answer `state_version/as_of`.
10. History/H2H comes on demand from API-Tennis and no full supplier history mirror exists.
11. Raw payload cleanup proves a 14-day cutoff while canonical observations remain.
12. No P2 schema, API or production UI contains odds, prediction, market or trading functionality.
13. Backend deterministic/infrastructure suites, frontend unit/type/build, Replay E2E and reviewed dual-viewport visuals pass.
14. Real REST/WS/LLM gates pass where runnable and every environmental skip is recorded honestly.
15. `PROJECT.md`, `ROADMAP.md`, `CURRENT.md` and `docs/runbooks/p2-local.md` agree with code, tests and Git HEAD.
