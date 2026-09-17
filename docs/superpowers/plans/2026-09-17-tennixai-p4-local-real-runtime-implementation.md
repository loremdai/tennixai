# TennixAI P4.0 Local Real Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the completed P1–P3 components into one safe, local, real-data daily runtime with `init`, `up`, `status`, `down`, optional `logs`, and explicit `verify`, while remaining permanently paper-only.

**Architecture:** A root launcher owns local process lifecycle; a separate `runtime` process is the only owner of API-Tennis and Polymarket upstream WebSockets and low-frequency discovery. FastAPI becomes a read/API/Chat process in local-runtime API role, reading canonical PostgreSQL and Redis hot state; it may retain bounded user-triggered REST history/H2H fallbacks but never starts upstream streams or discovery. Existing canonical models, P2/P3 repositories, reducers, SSE, and paper ledger remain the authority rather than being replaced.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy async/Alembic, asyncpg, Redis, httpx, websockets, Docker Compose, `uv`, Next.js/TypeScript, pnpm, pytest, Playwright.

**Spec:** [P4.0 Local Real Runtime Design](../specs/2026-09-17-tennixai-p4-local-real-runtime-design.md)

## Global Constraints

- Root `.env` is the only human-maintained configuration file; never create or read `backend/.env`, `frontend/.env`, or `frontend/.env.local`.
- The local-real database is exactly `tennix_live_local`; `init` and `up` reject the legacy `tennix`, test databases, non-loopback hosts, and any other database name.
- Runtime data is canonical only. Provider external IDs, API keys, raw payloads, token IDs, URLs with query strings, wallets, private keys, signatures, and trading credentials never reach public APIs, browser code, logs, fixtures, or status output.
- `runtime` is the only process that may own API-Tennis or Polymarket WebSockets and automatic discovery. Browser refreshes and FastAPI restarts must not create a second upstream subscription.
- Scores/PBP/statistics and market books are event-driven with REST first-frame/reconnect reconciliation. Catalog/ranking/market discovery use bounded low-frequency jobs, not fast polling.
- API-Tennis REST remains permitted only for bounded, user-triggered, cached history/H2H/detail fallbacks in FastAPI. It is not a background replacement for runtime WebSockets.
- Preserve raw provider retention at 14 days; preserve canonical facts and paper audit history. Do not implement reset, truncate, downgrade, volume deletion, cloud deployment, cron, authentication, multi-user behavior, new market types, model promotion, threshold relaxation, wallets, signing, or real orders.
- The local runtime requires `TENNIX_PROVIDER_MODE=api_tennis`, `TENNIX_P3_MODE=paper`, a real API-Tennis key, and the configured OpenAI-compatible LLM credentials. `up` never invokes the LLM; only `init` may run missing-name offline enrichment and only once per missing player.
- Existing P1–P3 visual designs remain frozen. Runtime work may add truthful operational state but must not redesign Home, Match, Players, or Markets.
- Default tests remain deterministic and do not spend external quota. Real checks are explicit, bounded, read-only, and report pass/fail/skip honestly.

---

## Investigation Baseline

- `backend/app/main.py` currently creates the P2 `RealtimeWorker` inside FastAPI's lifespan, while P3 creates `MarketWorker`/`DecisionWorker` dependencies but starts no P3 background loop. Local-runtime API role must therefore suppress that lifespan worker and move all automatic work to the new daemon.
- `RealtimeWorker` already provides REST-first snapshots, reconnect recovery, canonical persistence, Redis publication, and viewer-lease demand. `MarketWorker` already provides bounded queues, REST reconciliation, hot books, retention cleanup, and a dynamic demand source. The new runtime composes rather than rewrites them.
- `TrackingDemand` already knows main-tour singles coverage and unresolved positions, but `main.py` currently supplies `match_info=None`. The runtime must obtain real status/schedule/circuit/discipline from its canonical catalog.
- Existing `players`, `matches`, `match_state_snapshots`, `markets`, links, observations, and paper-ledger tables are reusable. The minimal migration adds a small runtime state table for the init marker and aggregate health; it must not duplicate provider JSON.
- API-Tennis' official documentation confirms `get_fixtures`, `get_livescore`, `get_standings`, and a live WebSocket that pushes score/PBP updates. It does not provide a public account-specific concurrency entitlement, so the implementation keeps the existing bounded subscriptions and makes entitlement failures explicit rather than assuming a plan limit. [REST documentation](https://api-tennis.com/documentation) · [WebSocket documentation](https://api-tennis.com/documentation_websocket)
- Polymarket's official market channel is public, subscribes by asset IDs, supplies book/price updates, and requires client ping every 10 seconds; the existing `PolymarketMarketFeed` already uses that public channel and heartbeat. Public Gamma/CLOB REST is for discovery and reconciliation, not a trading client. [Market Channel](https://docs.polymarket.com/api-reference/wss/market) · [rate limits](https://docs.polymarket.com/api-reference/rate-limits)

## File Map

| File | Responsibility |
|---|---|
| `backend/app/config.py` | Add bounded local-runtime settings and the explicit process role while retaining all current modes. |
| `backend/app/runtime/models.py` | Internal, secret-safe Pydantic models for init records, source health, aggregate runtime health, and launcher state. |
| `backend/app/runtime/config.py` | Validate the live-local boundary and construct child-only environment overrides without logging secrets. |
| `backend/app/runtime/catalog.py` | Sync API-Tennis live/upcoming canonical matches and expose deterministic per-match tracking context. |
| `backend/app/runtime/bootstrap.py` | Idempotent database creation/migration/init pipeline, ranking/catalog seed, English aliases, and one-time missing Chinese-name enrichment. |
| `backend/app/runtime/assembly.py` | Build and close the local-runtime-only provider/repository/worker graph for API and runtime roles without modifying fake/replay assembly. |
| `backend/app/runtime/health.py` | Track source health and freshness/gap overlays; persist only aggregate, canonical-safe health summaries. |
| `backend/app/runtime/daemon.py` | Run the unique WebSocket owners, bounded schedulers, P3 paper maintenance, and graceful shutdown. |
| `backend/app/runtime/child.py` | Wrap launcher-owned children so `down` can prove ownership before signalling a process group. |
| `backend/app/runtime/launcher.py` | Implement safe Compose/process/port lifecycle, status rendering, and secret-safe log access. |
| `backend/app/runtime/cli.py` | Parse the six user commands and map their return codes to clear, non-secret messages. |
| `backend/app/runtime/verify.py` | Run bounded read-only real smoke checks only when explicitly requested. |
| `backend/app/persistence/models.py` | Add the small `runtime_state` SQLAlchemy row model. |
| `backend/app/persistence/repositories.py` | Add canonical catalog and runtime-state repositories while reusing the existing player/match/tournament tables. |
| `backend/migrations/versions/20260917_0005_local_runtime_state.py` | Add only `runtime_state`; downgrade drops only that new table. |
| `backend/app/service.py` | Prefer the injected catalog repository for normal local-runtime Home/Match catalog reads; retain current provider fallback when no catalog is injected. |
| `backend/app/main.py` | Introduce `local_runtime_role=api`: attach read services but never start an upstream worker in FastAPI lifespan. |
| `backend/app/api/routes.py`, `backend/app/api/schemas.py` | Add a canonical, internal-ID-only runtime-health endpoint without changing the existing P1 `/health` contract. |
| `backend/app/realtime/worker.py` | Accept an optional composed demand source and post-persistence snapshot/connection callbacks; preserve the current lease-only default. |
| `backend/app/markets/worker.py` | Expose active market IDs, report baseline/recovery health, and feed initial/recovered books to the P3 queue without SQL-per-delta behavior. |
| `backend/app/decision/worker.py` | Obtain optional runtime freshness/gap overlay before evaluating an action; default behavior remains unchanged for existing tests. |
| `backend/app/players/sync.py` | Add a narrow deterministic alias method for only newly cataloged player IDs; it never calls the LLM. |
| `scripts/tennix-live` | Repository-root executable wrapper for the Python launcher, invoked as `./scripts/tennix-live <command>`. |
| `.env.example`, `docs/runbooks/local-real-runtime.md` | Safe configuration template and user-readable operational instructions. |
| `backend/tests/test_runtime_*.py`, `backend/tests/integration/test_runtime_*.py`, `backend/tests/live/test_local_runtime_verify.py` | Deterministic unit/integration gates plus opt-in, bounded real verification. |
| `frontend/e2e/local-real-runtime.spec.ts` | Opt-in browser acceptance against an already-running real local runtime; no fixture or preview fallback. |

## Task 1 — T73: Add Live-Local Configuration and Isolation Guards

**Files:**

- Create: `backend/app/runtime/__init__.py`
- Create: `backend/app/runtime/models.py`
- Create: `backend/app/runtime/config.py`
- Create: `backend/tests/test_runtime_config.py`
- Modify: `backend/app/config.py`
- Modify: `backend/tests/test_config.py`
- Modify: `.env.example`

**Interfaces:**

- Consumes: `Settings`, root `.env`, `SecretStr`, and normal process environment precedence.
- Produces:

  ```python
  class LiveLocalConfigurationError(ValueError):
      code: str

  class LocalRuntimeSettings(FrozenModel):
      database_url: str
      redis_url: str
      live_catalog_seconds: int
      upcoming_catalog_seconds: int
      ranking_seconds: int
      market_discovery_seconds: int

  def require_live_local(settings: Settings) -> LocalRuntimeSettings: ...
  def child_environment(
      settings: Settings, *, role: Literal["runtime", "api", "verify"]
  ) -> dict[str, str]: ...
  ```

- `Settings` gains `local_runtime_role: Literal["off", "api", "runtime", "verify"] = "off"` and bounded `local_runtime_*` fields. Child overrides set existing `TENNIX_DATABASE_URL`, `TENNIX_REDIS_URL`, `TENNIX_PROVIDER_MODE`, `TENNIX_P3_MODE`, and the role; they never mutate the parent shell or `.env`.

- [ ] **Step 1: Write failing configuration tests.**

  ```python
  def test_live_local_accepts_only_the_dedicated_loopback_database():
      settings = local_settings(database_url="postgresql+asyncpg://x:y@127.0.0.1:5432/tennix_live_local")
      assert require_live_local(settings).database_url.endswith("/tennix_live_local")

      with pytest.raises(LiveLocalConfigurationError, match="LOCAL_DATABASE_NAME_INVALID"):
          require_live_local(local_settings(database_url="postgresql+asyncpg://x:y@127.0.0.1:5432/tennix"))

  def test_child_environment_never_exposes_credentials_to_frontend_keys():
      values = child_environment(local_settings(), role="runtime")
      assert values["TENNIX_LOCAL_RUNTIME_ROLE"] == "runtime"
      assert values["TENNIX_P3_MODE"] == "paper"
      assert not any(key.startswith("NEXT_PUBLIC_") for key in values)
  ```

- [ ] **Step 2: Run the focused tests and confirm the missing runtime module fails.**

  Run: `cd backend && uv run pytest tests/test_runtime_config.py -q`

  Expected: FAIL because `app.runtime.config` does not exist.

- [ ] **Step 3: Add the bounded fields and validation.**

  ```python
  def require_live_local(settings: Settings) -> LocalRuntimeSettings:
      if settings.provider_mode != "api_tennis":
          raise LiveLocalConfigurationError("LOCAL_PROVIDER_MODE_INVALID")
      if settings.p3_mode != "paper":
          raise LiveLocalConfigurationError("LOCAL_P3_MODE_INVALID")
      if not settings.api_tennis_api_key or not settings.llm_api_key or not settings.llm_base_url:
          raise LiveLocalConfigurationError("LOCAL_CREDENTIALS_MISSING")
      parsed = make_url(settings.local_runtime_database_url)
      if parsed.database != "tennix_live_local" or parsed.host not in {"127.0.0.1", "localhost", "::1"}:
          raise LiveLocalConfigurationError("LOCAL_DATABASE_NAME_INVALID")
      return LocalRuntimeSettings.model_validate({...})
  ```

  Use `sqlalchemy.engine.make_url`; error text contains only the stable reason code, never the supplied URL or secret. Enforce `Redis` DB 11 and intervals `live >= 30`, `upcoming >= 300`, `ranking >= 3600`, and `market discovery >= 60` in the Pydantic field bounds.

- [ ] **Step 4: Add the safe template block.**

  Add these non-secret defaults to `.env.example` while preserving the current default fake mode for ordinary development:

  ```dotenv
  TENNIX_LOCAL_RUNTIME_DATABASE_URL=postgresql+asyncpg://tennix:tennix@127.0.0.1:5432/tennix_live_local
  TENNIX_LOCAL_RUNTIME_REDIS_URL=redis://127.0.0.1:6379/11
  TENNIX_LOCAL_RUNTIME_LIVE_CATALOG_SECONDS=60
  TENNIX_LOCAL_RUNTIME_UPCOMING_CATALOG_SECONDS=600
  TENNIX_LOCAL_RUNTIME_RANKING_SECONDS=86400
  TENNIX_LOCAL_RUNTIME_MARKET_DISCOVERY_SECONDS=120
  ```

- [ ] **Step 5: Prove the focused and existing configuration gates pass.**

  Run: `cd backend && uv run pytest tests/test_runtime_config.py tests/test_config.py -q`

  Expected: PASS; tests cover bad DB names, non-loopback hosts, wrong provider/P3 modes, missing credentials, too-fast periods, no secret echo, and child-role overrides.

- [ ] **Step 6: Commit the isolated configuration foundation.**

  ```bash
  git add backend/app/config.py backend/app/runtime backend/tests/test_runtime_config.py backend/tests/test_config.py .env.example
  git commit -m "feat: add local runtime configuration guards"
  ```

## Task 2 — T74: Persist a Canonical Catalog and Runtime State Without Copying Provider JSON

**Files:**

- Create: `backend/migrations/versions/20260917_0005_local_runtime_state.py`
- Create: `backend/tests/test_runtime_repositories.py`
- Create: `backend/tests/integration/test_runtime_catalog_postgres.py`
- Modify: `backend/app/persistence/models.py`
- Modify: `backend/app/persistence/repositories.py`
- Modify: `backend/tests/test_persistence_models.py`

**Interfaces:**

- Consumes: existing canonical `Match`, `Player`, `Tournament`, `MatchRow`, player/tournament rows, and `Database`.
- Produces:

  ```python
  class MatchCatalogRepository:
      async def upsert_matches(self, matches: Sequence[Match], *, observed_at: datetime) -> set[str]: ...
      async def list_matches(self, status: MatchStatus, *, player_id: str | None = None) -> list[Match]: ...
      async def get_match(self, match_id: str) -> Match | None: ...

  class RuntimeStateRepository:
      async def is_initialized(self) -> bool: ...
      async def mark_initialized(self, record: RuntimeInitRecord) -> None: ...
      async def save_health(self, health: RuntimeHealth) -> None: ...
      async def load_health(self) -> RuntimeHealth | None: ...
  ```

- `runtime_state` has `key` (primary key), `payload` (JSONB), and `updated_at`; only keys `local_runtime_init` and `local_runtime_health` are accepted by its repository. It stores no provider IDs or raw events.

- [ ] **Step 1: Write failing repository contract tests.**

  ```python
  async def test_catalog_round_trips_scheduled_match_without_live_snapshot(database, upcoming_match):
      catalog = MatchCatalogRepository(database)
      inserted = await catalog.upsert_matches([upcoming_match], observed_at=NOW)
      assert inserted == {upcoming_match.players[0].id, upcoming_match.players[1].id}
      assert await catalog.list_matches(MatchStatus.SCHEDULED) == [upcoming_match]

  async def test_init_marker_is_idempotent_and_health_never_deletes_catalog(database, upcoming_match):
      catalog, state = MatchCatalogRepository(database), RuntimeStateRepository(database)
      await catalog.upsert_matches([upcoming_match], observed_at=NOW)
      await state.mark_initialized(RuntimeInitRecord(completed_at=NOW, migration_revision="0005"))
      await state.mark_initialized(RuntimeInitRecord(completed_at=NOW, migration_revision="0005"))
      assert await state.is_initialized() is True
      assert await catalog.get_match(upcoming_match.id) is not None
  ```

- [ ] **Step 2: Run tests before the schema exists.**

  Run: `cd backend && uv run pytest tests/test_runtime_repositories.py -q`

  Expected: FAIL with missing repository/model imports.

- [ ] **Step 3: Add migration `0005` and the two focused repositories.**

  Reuse the existing canonical upsert shapes for players, tournaments, and matches. A catalog upsert updates only fields supplied by the canonical `Match`; it must not set a finished match back to scheduled merely because an older fixture arrives. The migration's downgrade drops only `runtime_state`.

  ```python
  class RuntimeStateRow(Base):
      __tablename__ = "runtime_state"
      key: Mapped[str] = mapped_column(String(64), primary_key=True)
      payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
      updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  ```

- [ ] **Step 4: Add the PostgreSQL integration proof.**

  Run: `cd backend && uv run pytest -m infrastructure tests/integration/test_runtime_catalog_postgres.py -q`

  Expected: PASS; migration reaches head, scheduled and live catalog rows round-trip with internal IDs only, marker/health upserts are idempotent, and no existing P2/P3 rows are deleted.

- [ ] **Step 5: Run repository and existing persistence regression tests.**

  Run: `cd backend && uv run pytest tests/test_runtime_repositories.py tests/test_persistence_models.py tests/integration/test_postgres_repositories.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit the reversible read-model addition.**

  ```bash
  git add backend/app/persistence/models.py backend/app/persistence/repositories.py backend/migrations/versions/20260917_0005_local_runtime_state.py backend/tests/test_runtime_repositories.py backend/tests/integration/test_runtime_catalog_postgres.py backend/tests/test_persistence_models.py
  git commit -m "feat: persist local runtime catalog state"
  ```

## Task 3 — T75: Implement Idempotent `init` Data Preparation

**Files:**

- Create: `backend/app/runtime/catalog.py`
- Create: `backend/app/runtime/bootstrap.py`
- Create: `backend/tests/test_runtime_catalog.py`
- Create: `backend/tests/test_runtime_bootstrap.py`
- Modify: `backend/app/players/sync.py`
- Modify: `backend/tests/test_player_directory_sync.py`

**Interfaces:**

- Consumes: `ApiTennisProvider`, `PlayerDirectorySync`, `PlayerAliasEnricher`, `MatchCatalogRepository`, `RuntimeStateRepository`, and an injected migration runner.
- Produces:

  ```python
  class CatalogSyncResult(FrozenModel):
      live_matches: int
      upcoming_matches: int
      newly_seen_player_ids: tuple[str, ...]
      observed_at: datetime

  class CatalogSynchronizer:
      async def sync(self) -> CatalogSyncResult: ...
      async def tracking_info(self, match_id: str) -> MatchTrackingInfo | None: ...

  class RuntimeBootstrapper:
      async def initialize(self) -> RuntimeInitRecord: ...

  async def sync_player_aliases(self, player_ids: Collection[str]) -> DirectorySyncReport: ...
  ```

- `initialize()` order is fixed: migrations → rankings → known ranking aliases → canonical live/upcoming catalog → aliases for newly cataloged players → missing Chinese enrichment → aggregate counts → init marker. The marker is written last and only after every required step succeeds.

- [ ] **Step 1: Write failing catalog and bootstrap tests.**

  ```python
  async def test_catalog_sync_deduplicates_live_and_fixture_rows_and_returns_new_players():
      result = await synchronizer.sync()
      assert result.live_matches == 1
      assert result.upcoming_matches == 1
      assert result.newly_seen_player_ids == ("ply_a", "ply_b", "ply_c")

  async def test_init_writes_marker_only_after_all_required_steps_finish():
      bootstrap = make_bootstrapper(enrichment=FailingEnrichment())
      with pytest.raises(AppError, match="provider_unavailable"):
          await bootstrap.initialize()
      assert await bootstrap.state.is_initialized() is False
  ```

- [ ] **Step 2: Run the new tests before implementation.**

  Run: `cd backend && uv run pytest tests/test_runtime_catalog.py tests/test_runtime_bootstrap.py -q`

  Expected: FAIL with missing runtime modules.

- [ ] **Step 3: Implement canonical catalog sync and narrow English alias sync.**

  `CatalogSynchronizer.sync()` calls `get_live_matches()` and `get_fixtures()` exactly once each per sync, deduplicates by internal match ID, persists canonical rows, and returns counts. It does not delete a previous catalog on provider failure. `sync_player_aliases()` queries only the returned player IDs and uses `derive_english_aliases`; it performs no LLM call and does not scan the whole directory on every ten-minute update.

- [ ] **Step 4: Implement the all-or-nothing init marker sequence.**

  ```python
  async def initialize(self) -> RuntimeInitRecord:
      await self._migrations.upgrade_head()
      rankings = await self._directory.sync_rankings()
      if rankings.failed:
          raise AppError("provider_unavailable", "Ranking initialization failed", 503)
      await self._directory.sync_known_player_aliases()
      catalog = await self._catalog.sync()
      await self._directory.sync_player_aliases(catalog.newly_seen_player_ids)
      enrichment = await self._enricher.enrich_missing(batch_size=25)
      if enrichment.failed:
          raise AppError("provider_unavailable", "Chinese alias initialization failed", 503)
      record = await self._build_record(catalog, rankings, enrichment)
      await self._state.mark_initialized(record)
      return record
  ```

  Catch neither provider nor enrichment failures as success. Preserve any already persisted real rows, return a nonzero CLI code later, and print aggregate counts only.

- [ ] **Step 5: Prove idempotency and no-repeat-LLM behavior.**

  Run: `cd backend && uv run pytest tests/test_runtime_catalog.py tests/test_runtime_bootstrap.py tests/test_player_directory_sync.py -q`

  Expected: PASS; a second successful init has no missing-name translator calls, catalog keeps existing real rows, and a failed rerun never erases the marker or data from the prior successful run.

- [ ] **Step 6: Commit the `init` preparation domain layer.**

  ```bash
  git add backend/app/runtime/catalog.py backend/app/runtime/bootstrap.py backend/app/players/sync.py backend/tests/test_runtime_catalog.py backend/tests/test_runtime_bootstrap.py backend/tests/test_player_directory_sync.py
  git commit -m "feat: add idempotent local runtime initialization"
  ```

## Task 4 — T76: Split FastAPI Read Role From Runtime WebSocket Ownership

**Files:**

- Create: `backend/app/runtime/assembly.py`
- Create: `backend/tests/test_runtime_api_role.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/service.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/tests/test_api.py`
- Modify: `backend/tests/test_p2_api.py`
- Modify: `backend/tests/integration/test_p3_assembly.py`

**Interfaces:**

- Consumes: local-role `Settings`, current API-Tennis/Polymarket adapters, P2 repositories, P3 query service, catalog/state repositories.
- Produces:

  ```python
  @dataclass
  class LocalRuntimeAssembly:
      database: Database
      redis: Redis
      provider: ApiTennisProvider
      directory: PostgresPlayerDirectoryRepository
      resolver: PlayerResolver
      catalog: MatchCatalogRepository
      state: RuntimeStateRepository
      realtime: SimpleNamespace  # worker is None in API role
      p3_queries: P3QueryService
      async def aclose(self) -> None: ...

  @router.get("/runtime/health", response_model=RuntimeHealthResponse)
  async def runtime_health(...) -> RuntimeHealthResponse: ...
  ```

- `TennisService(..., catalog=None)` uses `catalog.list_matches(...)` only when supplied. It retains the present cached provider path in all fake/live/replay tests and uses provider detail/history/H2H only on a user-triggered local miss.

- [ ] **Step 1: Write failing ownership and read-path tests.**

  ```python
  async def test_local_api_role_serves_catalog_without_starting_realtime_worker(app, catalog_match):
      async with app.router.lifespan_context(app):
          response = await client.get("/api/v1/matches/catalog?status=upcoming")
      assert response.status_code == 200
      assert response.json()["data"]["matches"][0]["id"] == catalog_match.id
      assert app.state.realtime.worker is None

  async def test_runtime_health_response_contains_no_external_identifier_or_secret(client):
      body = (await client.get("/api/v1/runtime/health")).text
      assert "event_key" not in body and "conditionId" not in body and "APIkey" not in body
  ```

- [ ] **Step 2: Run the focused tests before changing app assembly.**

  Run: `cd backend && uv run pytest tests/test_runtime_api_role.py -q`

  Expected: FAIL because the role and endpoint do not exist.

- [ ] **Step 3: Build local-role assembly and keep existing non-local paths unchanged.**

  In `local_runtime_role == "api"`, build PostgreSQL/Redis/provider/resolver/catalog/P3 query dependencies through `LocalRuntimeAssembly`, set `realtime.worker = None`, and do not create a lifespan task. Keep the current fake, replay, LiveTennisAPI, and ordinary API-Tennis behavior byte-for-byte compatible where no local role is selected.

- [ ] **Step 4: Make ordinary catalog reads canonical-first in local API role.**

  ```python
  async def _list_by_player_id(self, status: str, player_id: str | None) -> list[Match]:
      if self._catalog is not None:
          return await self._catalog.list_matches(_status_for(status), player_id=player_id)
      return await self._cached_provider_match_list(status, player_id)
  ```

  Do not use this branch for `resolve_match_snapshot` when a local snapshot is absent; that remains the bounded user-driven provider fallback already approved by the spec.

- [ ] **Step 5: Add the internal-only runtime-health endpoint.**

  Return the persisted aggregate `RuntimeHealth` if present; return a typed `runtime_not_started` state when no daemon has written one. Do not change `/api/v1/health`, because existing P1 compatibility tests use that contract.

- [ ] **Step 6: Run focused API/P2/P3 compatibility gates.**

  Run: `cd backend && uv run pytest tests/test_runtime_api_role.py tests/test_api.py tests/test_p2_api.py tests/integration/test_p3_assembly.py -q`

  Expected: PASS; FastAPI local role starts zero upstream worker, the canonical catalog is served, and normal paths remain compatible.

- [ ] **Step 7: Commit the API/runtime role split.**

  ```bash
  git add backend/app/runtime/assembly.py backend/app/main.py backend/app/service.py backend/app/api/routes.py backend/app/api/schemas.py backend/tests/test_runtime_api_role.py backend/tests/test_api.py backend/tests/test_p2_api.py backend/tests/integration/test_p3_assembly.py
  git commit -m "feat: separate local runtime from api role"
  ```

## Task 5 — T77: Compose P2 and P3 Demand Under One Runtime Owner

**Files:**

- Create: `backend/app/runtime/demand.py`
- Create: `backend/tests/test_runtime_demand.py`
- Create: `backend/tests/test_runtime_workers.py`
- Modify: `backend/app/realtime/worker.py`
- Modify: `backend/app/markets/worker.py`
- Modify: `backend/app/decision/worker.py`
- Modify: `backend/tests/test_realtime_worker.py`
- Modify: `backend/tests/test_market_worker.py`
- Modify: `backend/tests/test_decision_worker.py`

**Interfaces:**

- Consumes: `ViewerLeaseStore`, `TrackingDemand`, `MarketRepositoryLinks`, `CatalogSynchronizer.tracking_info`, `RealtimeWorker`, `MarketWorker`, and `DecisionWorker`.
- Produces:

  ```python
  class RuntimeDemand:
      async def demanded_matches(self) -> dict[str, str]: ...

  class RealtimeWorker:
      def __init__(..., demand_source: Callable[[], Awaitable[dict[str, str]]] | None = None,
                   on_snapshot: Callable[[str, MatchSnapshot], Awaitable[None]] | None = None,
                   on_connection: Callable[[str, str], Awaitable[None]] | None = None): ...

  class MarketWorker:
      def active_market_ids(self) -> tuple[str, ...]: ...
  ```

- `RuntimeDemand` returns viewer-lease match IDs plus the match IDs corresponding to durable P3 tracked market IDs. Duplicate IDs collapse to one active subscription; P3 tracking keeps a match alive with zero viewers.

- [ ] **Step 1: Write failing composed-demand tests.**

  ```python
  async def test_runtime_demand_unions_viewer_and_paper_tracking_without_duplicates():
      demand = RuntimeDemand(leases=FakeLeases({"mat_view"}), tracking=FakeTracking({"mkt_paper"}), links=FakeLinks({"mat_paper": "mkt_paper"}))
      assert await demand.demanded_matches() == {"mat_view": "active", "mat_paper": "active"}

  async def test_runtime_opens_one_sports_subscription_when_viewer_and_p3_need_same_match(worker, feed):
      await worker.reconcile_demand_once()
      assert feed.opened_external_ids == ["match_external_1"]
  ```

- [ ] **Step 2: Run focused tests before adding optional worker hooks.**

  Run: `cd backend && uv run pytest tests/test_runtime_demand.py tests/test_runtime_workers.py -q`

  Expected: FAIL with missing runtime demand/hook interfaces.

- [ ] **Step 3: Add backward-compatible worker extension points.**

  Keep `RealtimeWorker` lease-only when `demand_source is None`; existing P2 tests must continue to prove that behavior. Invoke `on_snapshot` only after canonical reduction is committed, and isolate callback errors so a decision failure cannot corrupt or suppress P2 publication. Invoke `on_connection` at reconnect/gap and healthy recovery transitions using stable values only.

  In `MarketWorker`, expose a tuple copy of active IDs; invoke the existing downstream `on_state` after a REST baseline as well as a changed WebSocket book, so P3 can see initial/recovered books. Preserve bounded queues and asynchronous observation batches.

- [ ] **Step 4: Wire real `match_info` for P3 tracking.**

  ```python
  async def match_info(match_id: str) -> MatchTrackingInfo | None:
      match = await catalog.get_match(match_id)
      if match is None:
          return None
      return MatchTrackingInfo(
          status=match.status,
          scheduled_at=match.scheduled_at,
          circuit=match.tournament.circuit,
          discipline=match.tournament.discipline,
      )
  ```

  Runtime assembly passes this callable to `TrackingDemand`; it must no longer use `match_info=None` in the live-local runtime.

- [ ] **Step 5: Run P2/P3 worker regression gates.**

  Run: `cd backend && uv run pytest tests/test_runtime_demand.py tests/test_runtime_workers.py tests/test_realtime_worker.py tests/test_market_worker.py tests/test_decision_worker.py tests/test_p3_tracking_demand.py -q`

  Expected: PASS; same match has one upstream subscription, P3 durable demand works without a viewer, regular viewer lease semantics remain unchanged, and a callback failure is visible as a metric/health condition rather than a data corruption.

- [ ] **Step 6: Commit composed ownership.**

  ```bash
  git add backend/app/runtime/demand.py backend/app/realtime/worker.py backend/app/markets/worker.py backend/app/decision/worker.py backend/tests/test_runtime_demand.py backend/tests/test_runtime_workers.py backend/tests/test_realtime_worker.py backend/tests/test_market_worker.py backend/tests/test_decision_worker.py
  git commit -m "feat: compose local runtime live demand"
  ```

## Task 6 — T78: Run Bounded Discovery, Freshness, and Paper Maintenance in the Daemon

**Files:**

- Create: `backend/app/runtime/health.py`
- Create: `backend/app/runtime/daemon.py`
- Create: `backend/tests/test_runtime_health.py`
- Create: `backend/tests/test_runtime_daemon.py`
- Create: `backend/tests/integration/test_runtime_recovery.py`
- Modify: `backend/app/decision/worker.py`
- Modify: `backend/app/markets/worker.py`
- Modify: `backend/tests/test_decision_worker.py`
- Modify: `backend/tests/test_market_worker.py`
- Modify: `backend/tests/integration/test_p3_worker_recovery.py`

**Interfaces:**

- Consumes: `CatalogSynchronizer`, `PlayerDirectorySync`, `PolymarketProvider`, `MarketRepository`, `map_market`, `RuntimeDemand`, P2/P3 workers, `PaperTradingService`, and `RuntimeStateRepository`.
- Produces:

  ```python
  class RuntimeHealthRegistry:
      async def mark_success(self, source: str, *, tracked: int = 0) -> None: ...
      async def mark_degraded(self, source: str, reason_code: str) -> None: ...
      async def mark_gap(self, source: str, reason_code: str) -> None: ...
      async def freshness_for(self, match_id: str, market_id: str | None) -> FreshnessOverlay: ...
      async def persist(self) -> RuntimeHealth: ...

  class LocalRuntimeDaemon:
      async def run(self) -> None: ...
      async def stop(self) -> None: ...
  ```

- Default schedules are exact: live catalog 60 seconds, upcoming catalog 600 seconds, ranking 86,400 seconds, and market discovery 120 seconds. Resolution/rules maintenance applies only to active linked markets, unresolved positions, or recently closed markets and runs no more often than the market-discovery interval.

- [ ] **Step 1: Write failing health and scheduler tests with a fake clock.**

  ```python
  async def test_score_silence_does_not_mark_a_healthy_websocket_stale():
      await health.mark_success("tennis_live", tracked=1)
      clock.advance(seconds=90)
      assert (await health.freshness_for("mat_1", None)).has_gap is False

  async def test_gap_revokes_new_decision_actions_until_rest_reconciliation_succeeds():
      await health.mark_gap("polymarket", "CONNECTION_LOST")
      await decision_worker.handle_book("mkt_1", book)
      assert latest.action is DecisionAction.NO_BET
      assert latest.has_gap is True

  async def test_scheduler_runs_catalog_and_market_jobs_at_bounded_intervals():
      await daemon.tick_once()
      clock.advance(seconds=59)
      await daemon.tick_once()
      assert catalog.live_calls == 1
      clock.advance(seconds=1)
      await daemon.tick_once()
      assert catalog.live_calls == 2
  ```

- [ ] **Step 2: Run the new deterministic tests before implementation.**

  Run: `cd backend && uv run pytest tests/test_runtime_health.py tests/test_runtime_daemon.py -q`

  Expected: FAIL because daemon and health registry do not exist.

- [ ] **Step 3: Implement aggregate health and decision freshness overlay.**

  `RuntimeHealthRegistry` stores only source state, last success/event timestamps, stable reason codes, counts, and paper/model status. It treats an open, heartbeat-confirmed sports connection as fresh even if the score is unchanged. A disconnect, queue overflow, or reconciliation period produces `gap`; a low-frequency job failure produces `degraded` without deleting prior canonical data. `DecisionWorker` receives an optional `freshness_for` callback and passes both `is_stale` and `has_gap` to `DecisionInput`; default `None` preserves current behavior.

- [ ] **Step 4: Implement the runtime daemon loops.**

  ```python
  async def tick_once(self) -> None:
      await self._realtime.reconcile_demand_once()
      await self._market_worker.reconcile_demand_once()
      for market_id in self._market_worker.active_market_ids():
          await self._decision_worker.pump_once(market_id)
          await self._execute_due_intents(market_id)
      await self._jobs.run_due(self._clock())
      await self._health.persist()
  ```

  The job set is: live catalog, upcoming catalog, rankings, tennis moneyline discovery/mapping/rules capture, and bounded market resolution/rules recheck. Discovery saves canonical markets, evaluates `map_market` against the canonical catalog, writes only successful strict links, and leaves failed mappings as `MARKET_ONLY`. It never uses LLM, fuzzy matching, or a permanent manual mapping.

- [ ] **Step 5: Handle P3 paper lifecycle safely.**

  After each eligible book cycle, fetch only the canonical hot book and execution metadata for that market, then call `PaperTradingService.execute_due_intents`. If reconciliation or metadata fails while an intent is due, provide `None` so existing `BOOK_UNVERIFIABLE`/`NO_FILL` semantics apply; do not manufacture a fill. For provider final resolutions, route `get_resolution()` only through `DecisionWorker.on_resolution`.

- [ ] **Step 6: Add restart/recovery integration proof.**

  Run: `cd backend && uv run pytest -m infrastructure tests/integration/test_runtime_recovery.py tests/integration/test_p3_worker_recovery.py -q`

  Expected: PASS; a restarted daemon rebuilds subscriptions from the durable demand/catalog/ledger, restores cursors and hot books via REST, writes an explicit gap before recovery, and creates neither duplicate intent nor duplicate fill.

- [ ] **Step 7: Run worker, decision, and latency regressions.**

  Run: `cd backend && uv run pytest tests/test_runtime_health.py tests/test_runtime_daemon.py tests/test_market_worker.py tests/test_decision_worker.py tests/integration/test_p3_latency_gate.py -q`

  Expected: PASS; no SQL-per-delta regression, P3 stale/gap hard gate remains fail-closed, and existing latency thresholds still pass.

- [ ] **Step 8: Commit the actual long-running runtime.**

  ```bash
  git add backend/app/runtime/health.py backend/app/runtime/daemon.py backend/app/decision/worker.py backend/app/markets/worker.py backend/tests/test_runtime_health.py backend/tests/test_runtime_daemon.py backend/tests/integration/test_runtime_recovery.py backend/tests/test_decision_worker.py backend/tests/test_market_worker.py backend/tests/integration/test_p3_worker_recovery.py
  git commit -m "feat: run bounded local real runtime daemon"
  ```

## Task 7 — T79: Add a Safe Repository-Root Launcher

**Files:**

- Create: `backend/app/runtime/child.py`
- Create: `backend/app/runtime/launcher.py`
- Create: `backend/app/runtime/cli.py`
- Create: `backend/tests/test_runtime_launcher.py`
- Create: `scripts/tennix-live`
- Modify: `compose.yaml`

**Interfaces:**

- Consumes: `LocalRuntimeSettings`, `RuntimeBootstrapper`, `RuntimeStateRepository`, Docker Compose, port probes, and process state under the operating system temporary directory.
- Produces:

  ```python
  class RuntimeLauncher:
      def init(self) -> int: ...
      def up(self) -> int: ...
      def status(self, *, as_json: bool = False) -> int: ...
      def down(self) -> int: ...
      def logs(self, role: Literal["runtime", "api", "frontend"]) -> int: ...

  # `./scripts/tennix-live {init,up,status,down,logs,verify}`
  ```

- Launcher state is stored under `tempfile.gettempdir() / f"tennix-live-{uid}"`, not in the repository. Each managed process is a tokenized `app.runtime.child` wrapper in its own process group; `down` signals it only after command/token verification.

- [ ] **Step 1: Write failing launcher safety tests with a fake command runner and process inspector.**

  ```python
  def test_up_refuses_uninitialized_database_without_starting_children(launcher):
      launcher.state.initialized = False
      assert launcher.up() == 2
      assert launcher.runner.spawned == []

  def test_down_never_signals_a_pid_without_our_wrapper_token(launcher):
      launcher.state.processes = [ManagedProcess(role="api", pid=123, token="ours")]
      launcher.inspector.command_for_pid[123] = "python unrelated.py"
      assert launcher.down() == 0
      assert launcher.runner.signalled_pids == []

  def test_up_reports_foreign_port_without_killing_it(launcher):
      launcher.ports.in_use[8000] = "foreign"
      assert launcher.up() == 2
      assert launcher.runner.signalled_pids == []
  ```

- [ ] **Step 2: Run tests before adding the command surface.**

  Run: `cd backend && uv run pytest tests/test_runtime_launcher.py -q`

  Expected: FAIL with missing launcher imports.

- [ ] **Step 3: Implement process and Compose ownership accounting.**

  Before `docker compose up -d --wait postgres redis`, record service container IDs. Store only container IDs newly created by this invocation; on `down`, stop an exact current-ID match and never run `docker compose down`, remove volumes, or stop a pre-existing container. Check ports 8000 and 3100 before spawn; a non-owned listener is a clear failure, not a kill target.

- [ ] **Step 4: Implement `init` and `up` sequencing.**

  ```text
  init: validate root .env → ensure Compose → create dedicated database if absent → RuntimeBootstrapper.initialize (including Alembic upgrade head) → print aggregate counts → exit
  up: validate root .env → ensure Compose → require init marker/schema head → reserve ports → spawn runtime → wait for persisted healthy first discovery → spawn API → wait /api/v1/health → spawn frontend → write ownership state
  ```

  `up` injects child-only `TENNIX_DATABASE_URL`, `TENNIX_REDIS_URL`, `TENNIX_PROVIDER_MODE=api_tennis`, `TENNIX_P3_MODE=paper`, and the appropriate local runtime role. It does not run initialization or enrichment.

- [ ] **Step 5: Implement `status`, `logs`, and graceful `down`.**

  `status` emits a concise text table or JSON with stack, database, Redis, runtime, sports stream, schedule, rankings, Polymarket, paper-only/model state, API, and frontend. It reads persisted health when API is down. `logs` accepts only `runtime`, `api`, or `frontend` and reads the current launcher's log file. `down` asks runtime to stop first, then API/frontend, then exact owned Compose containers; it flushes bounded buffers through the daemon shutdown path and preserves all data.

- [ ] **Step 6: Add the executable wrapper and Compose readiness compatibility.**

  ```sh
  #!/usr/bin/env sh
  set -eu
  root_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
  exec uv run --directory "$root_dir/backend" python -m app.runtime.cli "$@"
  ```

  Keep Compose services localhost-bound. Do not change `POSTGRES_DB=tennix`: the launcher creates the separate live database through the existing PostgreSQL instance.

- [ ] **Step 7: Prove launcher safety and formatting.**

  Run: `cd backend && uv run pytest tests/test_runtime_launcher.py tests/test_runtime_config.py -q && test -x ../scripts/tennix-live`

  Expected: PASS; no test invokes real Docker, binds a port, reads `.env` values, or kills a process.

- [ ] **Step 8: Commit the one-command local lifecycle.**

  ```bash
  git add backend/app/runtime/child.py backend/app/runtime/launcher.py backend/app/runtime/cli.py backend/tests/test_runtime_launcher.py scripts/tennix-live compose.yaml
  git commit -m "feat: add safe local runtime launcher"
  ```

## Task 8 — T80: Add Explicit Real Verification, Browser Acceptance, and the Human Runbook

**Files:**

- Create: `backend/app/runtime/verify.py`
- Create: `backend/tests/test_runtime_verify.py`
- Create: `backend/tests/live/test_local_runtime_verify.py`
- Create: `frontend/e2e/local-real-runtime.spec.ts`
- Create: `docs/runbooks/local-real-runtime.md`
- Modify: `backend/pyproject.toml`
- Modify: `docs/runbooks/p2-local.md`
- Modify: `.env.example`

**Interfaces:**

- Consumes: validated live-local configuration, bounded provider clients, launcher health, and an already-running local stack for browser validation.
- Produces:

  ```python
  class VerifyOutcome(FrozenModel):
      name: str
      status: Literal["passed", "failed", "skipped"]
      reason_code: str | None = None

  async def verify_runtime(*, with_llm: bool) -> tuple[VerifyOutcome, ...]: ...
  ```

- Add pytest marker `local_runtime_live` and gate it with `TENNIX_RUN_LOCAL_RUNTIME_VERIFY=1`. The test never writes a provider fixture, never sends an order, and never treats an external empty window as success.

- [ ] **Step 1: Write failing verifier result tests.**

  ```python
  async def test_verify_reports_no_live_match_as_honest_skip_not_pass():
      outcomes = await verify_runtime(with_llm=False, tennis=NoLiveTennis(), markets=ActiveMarket())
      assert outcome_by_name(outcomes, "tennis_websocket").status == "skipped"
      assert outcome_by_name(outcomes, "tennis_websocket").reason_code == "NO_LIVE_MATCH"

  async def test_verify_never_calls_llm_without_explicit_flag():
      llm = RecordingLlm()
      await verify_runtime(with_llm=False, llm=llm, ...)
      assert llm.calls == 0
  ```

- [ ] **Step 2: Run verifier tests before implementation.**

  Run: `cd backend && uv run pytest tests/test_runtime_verify.py -q`

  Expected: FAIL with missing verifier module.

- [ ] **Step 3: Implement bounded, read-only `verify`.**

  Execute at most one ATP ranking call, one current fixture/catalog call, one subscribed live-match WebSocket attempt only if an eligible live match exists, one tennis moneyline discovery call, one book/reconciliation call, and one public market WebSocket attempt only if an active mapped book exists. Bound each receive wait by 45 seconds. `--with-llm` is the sole path that invokes a real Chat contract. Emit aggregate names/status/reason codes only.

- [ ] **Step 4: Add opt-in browser acceptance.**

  `frontend/e2e/local-real-runtime.spec.ts` runs only when `TENNIX_E2E_LOCAL_RUNTIME=1` and assumes `./scripts/tennix-live up` is already running. It asserts Home has real catalog data or the approved honest empty state, Players renders English primary/Chinese secondary names or an honest coverage state, Match/Markets have no preview fixture strings, Decision Workbench is paper-only and has no trading CTA, and DOM/network output has no provider external-ID/token/key patterns. It does not assume a live match or a `BUY` action exists.

- [ ] **Step 5: Write the short human runbook.**

  The runbook begins with this user flow:

  ```text
  1. Copy .env.example to .env and fill only the named real credentials.
  2. Set provider mode to api_tennis and P3 mode to paper.
  3. ./scripts/tennix-live init        # one-time preparation; may spend LLM quota for missing Chinese names
  4. ./scripts/tennix-live up          # normal daily start; does not call the LLM
  5. ./scripts/tennix-live status
  6. ./scripts/tennix-live down        # preserves real data and paper ledger
  ```

  Explain `fresh`, `degraded`, `stale`, and `gap` in one sentence each; explain that no live match, no mapped market, and model-not-promoted are normal factual states. Link old P2 manual startup instructions to this runbook without deleting replay procedures.

- [ ] **Step 6: Run deterministic verification, frontend quality gates, and opt-in smoke.**

  Run:

  ```bash
  cd backend && uv run pytest tests/test_runtime_verify.py -q
  cd frontend && pnpm test && pnpm typecheck && pnpm build
  TENNIX_RUN_LOCAL_RUNTIME_VERIFY=1 ./scripts/tennix-live verify
  cd frontend && TENNIX_E2E_LOCAL_RUNTIME=1 pnpm exec playwright test e2e/local-real-runtime.spec.ts
  ```

  Expected: deterministic tests/build PASS. The two opt-in commands print either actual PASS, actual FAIL, or honest SKIP per source; do not label a skipped quiet data window as fully passed.

- [ ] **Step 7: Run final full regression and perform the local-real manual gate.**

  Run:

  ```bash
  cd backend && env -u NO_PROXY -u no_proxy uv run pytest -m "not api_tennis_live and not realtime_live and not llm_live and not end_to_end_live and not provider_live and not polymarket_live and not local_runtime_live" -q
  cd backend && uv run pytest -m infrastructure -q
  cd frontend && pnpm test && pnpm typecheck && pnpm build && pnpm test:e2e
  ```

  Then manually run `init → up → status → browser refresh → down → up → status`. Record the actual command result, exact test counts, real source pass/fail/skip outcomes, and a human check that IDs/data/ledger survived restart. Do not update visual baselines unless an independently approved design change exists.

- [ ] **Step 8: Commit verification and runbook deliverables.**

  ```bash
  git add backend/app/runtime/verify.py backend/tests/test_runtime_verify.py backend/tests/live/test_local_runtime_verify.py frontend/e2e/local-real-runtime.spec.ts docs/runbooks/local-real-runtime.md docs/runbooks/p2-local.md backend/pyproject.toml .env.example
  git commit -m "test: verify local real runtime"
  ```

## Completion Gate for T73–T80

- [ ] The normal user interface is `./scripts/tennix-live init`, then `up/status/down`; it uses only root `.env` and preserves all live data on stop.
- [ ] `tennix_live_local` is created and migrated without modifying the legacy `tennix` database; unsafe targets are rejected before any database command.
- [ ] The runtime daemon is the sole owner of automatic API-Tennis/Polymarket WebSockets and discovery. FastAPI/browser restart tests prove no duplicate subscription.
- [ ] Catalog, rankings, live state, markets, paper ledger, freshness, and Chat consume the same canonical read models; user-triggered historical fallback is bounded and separate from background work.
- [ ] Score/book streams are event-driven; scheduler intervals are bounded and health reports their last success. Quiet tennis scores do not falsely become stale.
- [ ] Any stream gap/recovery preserves last trusted state and prevents a new `BUY`/`SELL` until reconciliation; pending intents without a verifiable book follow existing no-fill semantics.
- [ ] The runtime stays `paper` with no wallet, signing, user channel, order submission, or real trade path. Unpromoted models display factual `NO BET`/`MARKET_ONLY`.
- [ ] Default deterministic, infrastructure, frontend, and Playwright gates have actual recorded evidence. Explicit real verification and browser testing record pass/fail/skip truthfully.
- [ ] `PROJECT.md`, `ROADMAP.md`, `CURRENT.md`, the runbook, and Git completion commits agree before P4.0 is marked done.
