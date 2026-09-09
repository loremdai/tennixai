# TennixAI P1 Implementation Plan

> **Configuration path superseded on 2026-09-09:** M01 made the repository-root `.env` / `.env.example` the only current configuration entry. Subdirectory env paths below are retained only as historical execution steps and must not be recreated.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the local single-user P1 path from real LiveTennisAPI current/upcoming data through FastAPI and trusted structured responses to the existing Next.js Home and Match experiences with Qwen tool calling.

**Architecture:** FastAPI owns provider access, canonical models, identity, cache policy, deterministic REST APIs, business tools, and stateless chat orchestration. Browser code reaches FastAPI only through thin same-origin Next.js Route Handlers; existing v0 components receive typed view models so visual structure survives the mock-to-real cutover.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, httpx, OpenAI Python SDK, pytest, Next.js 16, TypeScript 5.7, React 19, Tailwind CSS 4, Vitest, Playwright Chromium, pnpm, uv

**Spec:** `docs/superpowers/specs/2026-09-08-tennixai-product-roadmap-design.md`

## Global Constraints

- P1 is local, single-user, and single-process; do not add PostgreSQL, Redis, authentication, multi-worker coordination, or automatic polling.
- LiveTennisAPI Free is the only real tennis provider; do not call completed/history endpoints or build observed-history persistence.
- Historical questions return typed `unsupported`; no tennis fact may be invented by the LLM or inferred from prose.
- Canonical timestamps are UTC; `today`, `tonight`, and `next` use `Asia/Macau`. `tonight` is the active or next 18:00–05:59 local window.
- The browser calls same-origin `/api/*`; Route Handlers remain pure HTTP/SSE proxies and `TENNIX_BACKEND_URL` remains server-only.
- Qwen model `qwen3.8-max-0902` uses an OpenAI-compatible Chat Completions endpoint and native function calling.
- The LLM receives exactly `find_player_matches`, `get_live_matches`, and `get_match`, with no more than two tool-call rounds.
- Structured match data and LLM text remain separate. Cards, links, IDs, score, status, server, and freshness come only from `TennisService` output.
- No timer-based refresh exists in P1. Initial load, explicit in-app refresh, and user questions are the only read triggers.
- The v0 prototype is the visual source of truth. Preserve component geometry, typography, color, responsive layout, and interaction states at `1440×1000` and `390×844`.
- Default tests use fake provider and fake LLM. Real LLM/provider suites are opt-in and never assert exact generated prose.

## Planned File Structure

### Backend

- `backend/pyproject.toml`, `backend/uv.lock`: Python dependency and test configuration.
- `backend/.env.example`: safe backend variable names and local defaults.
- `backend/app/config.py`: typed settings and mode validation.
- `backend/app/errors.py`: stable application exceptions and error codes.
- `backend/app/domain.py`: the seven P1 canonical models and lifecycle enums.
- `backend/app/identity.py`: process-local internal/external ID mapping.
- `backend/app/providers/base.py`: the five-method async provider protocol.
- `backend/app/providers/fake.py`: deterministic provider for unit/E2E tests.
- `backend/app/providers/livetennis_dtos.py`: permissive vendor-only DTOs.
- `backend/app/providers/livetennis.py`: HTTP adapter and vendor-to-domain mapping.
- `backend/app/cache.py`: bounded async TTL cache and in-flight coalescing.
- `backend/app/service.py`: player resolution, time scopes, cache policy, and match queries.
- `backend/app/api/schemas.py`: stable REST/chat envelopes.
- `backend/app/api/routes.py`: health, player, match, and chat routes.
- `backend/app/chat/models.py`: chat request, internal model turn, tool call, and SSE event types.
- `backend/app/chat/tools.py`: the three business-tool schemas and dispatcher.
- `backend/app/chat/client.py`: fake and OpenAI-compatible model clients.
- `backend/app/chat/orchestrator.py`: historical guard, bounded tool loop, and data-first fallback.
- `backend/app/main.py`: application factory and dependency wiring.
- `backend/tests/`: matching unit, contract, live-marker, and acceptance tests.

### Frontend

- `frontend/vitest.config.ts`, `frontend/vitest.setup.ts`: unit/component test setup.
- `frontend/playwright.config.ts`, `frontend/e2e/`: Chromium functional and visual suites.
- `frontend/.env.example`: server-only FastAPI address.
- `frontend/lib/server/backend-proxy.ts`: reusable thin proxy implementation.
- `frontend/app/api/**/route.ts`: same-origin REST and SSE proxy routes.
- `frontend/lib/api/types.ts`: backend DTO and SSE event types.
- `frontend/lib/api/client.ts`: browser REST calls and abortable SSE parsing.
- `frontend/lib/view-models.ts`: canonical DTO-to-existing-component presentation mapping.
- `frontend/hooks/use-chat-stream.ts`: browser-only stateless chat lifecycle.
- `frontend/app/matches/[matchId]/page.tsx`: production internal-ID match route.
- `frontend/components/home-page.tsx`, `frontend/components/home/*`: real slate/chat state with existing Home visuals.
- `frontend/components/match-page.tsx`, `frontend/components/match/*`: real match/chat props plus isolated prototype preview state.
- `frontend/components/match/match-preview-data.ts`: mock data used only by `/match?status=...`.

---

### Task 1: Freeze the Existing Prototype Visually

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`
- Modify: `.gitignore`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/prototype.visual.spec.ts`
- Create: `frontend/e2e/__screenshots__/**`

**Interfaces:**
- Consumes: current `/` and `/match?status=upcoming|live|finished` prototype routes.
- Produces: named desktop/mobile screenshot baselines that later tasks must preserve or explicitly review.

- [ ] **Step 1: Install Playwright and add exact scripts**

Run:

```bash
cd frontend
pnpm add -D @playwright/test
pnpm exec playwright install chromium
```

Add these scripts to `frontend/package.json`:

```json
{
  "scripts": {
    "test:e2e": "playwright test",
    "test:e2e:update": "playwright test --update-snapshots"
  }
}
```

Add only generated reports to `.gitignore`; snapshot baselines remain tracked:

```gitignore
frontend/playwright-report/
frontend/test-results/
frontend/blob-report/
```

- [ ] **Step 2: Write the visual test before snapshots exist**

Create `frontend/playwright.config.ts`:

```ts
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:3100',
    colorScheme: 'dark',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  snapshotPathTemplate: '{testDir}/__screenshots__/{projectName}/{arg}{ext}',
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: {
    command: 'pnpm dev --hostname 127.0.0.1 --port 3100',
    url: 'http://127.0.0.1:3100',
    reuseExistingServer: !process.env.CI,
  },
})
```

Create `frontend/e2e/prototype.visual.spec.ts`:

```ts
import { expect, test } from '@playwright/test'

const states = [
  ['home-initial', '/'],
  ['home-answer', '/?q=Sinner%20%E4%BB%8A%E6%99%9A%E5%87%A0%E7%82%B9%E6%AF%94%E8%B5%9B%EF%BC%9F'],
  ['match-upcoming', '/match?status=upcoming'],
  ['match-live', '/match?status=live'],
  ['match-finished', '/match?status=finished'],
] as const

for (const [name, path] of states) {
  test(`${name} matches approved prototype`, async ({ page }) => {
    await page.goto(path)
    await page.evaluate(() => document.fonts.ready)
    await expect(page).toHaveScreenshot(`${name}.png`, {
      animations: 'disabled',
      fullPage: true,
    })
  })
}
```

- [ ] **Step 3: Run the tests to verify the missing-baseline failure**

Run: `cd frontend && pnpm test:e2e`

Expected: FAIL with missing snapshot files for both `desktop` and `mobile` projects.

- [ ] **Step 4: Generate and verify the approved baseline**

Run:

```bash
cd frontend
pnpm test:e2e:update
pnpm test:e2e
pnpm build
```

Expected: 10 visual tests PASS and Next.js build exits 0. Inspect all 10 generated PNGs before staging them.

- [ ] **Step 5: Commit**

```bash
git add .gitignore frontend/package.json frontend/pnpm-lock.yaml frontend/playwright.config.ts frontend/e2e
git commit -m "test: freeze prototype visual baselines"
```

### Task 2: Establish the FastAPI Foundation

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/uv.lock`
- Create: `backend/.env.example`
- Create: `frontend/.env.example`
- Modify: `.gitignore`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/errors.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_health.py`

**Interfaces:**
- Consumes: no application code; reads only `TENNIX_*` environment variables.
- Produces: `Settings`, `AppError`, `create_app()`, `GET /api/v1/health`, and an `X-Request-ID` response header.

- [ ] **Step 1: Write failing health and request-ID tests**

Create `backend/tests/test_health.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_health_and_request_id() -> None:
    app = create_app(Settings(_env_file=None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health", headers={"X-Request-ID": "req-test"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "tennix-api"}
    assert response.headers["X-Request-ID"] == "req-test"
```

- [ ] **Step 2: Run the test to verify the backend does not exist**

Run: `cd backend && uv run pytest tests/test_health.py -v`

Expected: FAIL because `backend/pyproject.toml` and package `app` do not exist.

- [ ] **Step 3: Add dependencies, typed settings, error base, health route, and app factory**

Create `backend/pyproject.toml`:

```toml
[project]
name = "tennix-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.135,<1",
  "httpx>=0.28,<1",
  "openai>=2,<3",
  "pydantic-settings>=2,<3",
  "uvicorn[standard]>=0.35,<1",
]

[dependency-groups]
dev = ["pytest>=8,<10", "pytest-asyncio>=1,<2"]

[tool.pytest.ini_options]
pythonpath = ["."]
asyncio_mode = "auto"
markers = [
  "llm_live: calls the configured real LLM",
  "provider_live: calls LiveTennisAPI",
  "end_to_end_live: calls both real integrations",
]

[tool.uv]
package = false
```

Create `backend/app/config.py` with these exact public fields and mode checks:

```python
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TENNIX_", env_file=".env", extra="ignore")

    provider_mode: Literal["fake", "live"] = "fake"
    livetennis_api_key: SecretStr | None = None
    livetennis_base_url: str = "https://api.livetennisapi.com/api/public/v1"
    llm_mode: Literal["fake", "openai_compatible"] = "fake"
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_model: str = "qwen3.8-max-0902"
    product_timezone: str = "Asia/Macau"
    cache_max_entries: int = 256
    fixed_now: str | None = None

    @model_validator(mode="after")
    def validate_required_credentials(self) -> "Settings":
        if self.provider_mode == "live" and (
            self.livetennis_api_key is None
            or not self.livetennis_api_key.get_secret_value().strip()
        ):
            raise ValueError("TENNIX_LIVETENNIS_API_KEY is required in live provider mode")
        if self.llm_mode == "openai_compatible" and (
            self.llm_api_key is None
            or not self.llm_api_key.get_secret_value().strip()
            or not self.llm_base_url
        ):
            raise ValueError("TENNIX_LLM_API_KEY and TENNIX_LLM_BASE_URL are required")
        return self
```

Create `backend/app/errors.py`:

```python
from typing import Any


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
```

Create `backend/app/api/routes.py` and `backend/app/main.py`:

```python
# backend/app/api/routes.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "tennix-api"}
```

```python
# backend/app/main.py
from uuid import uuid4

from fastapi import FastAPI, Request

from app.api.routes import router
from app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Tennix API")
    app.state.settings = settings or Settings()

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        value = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
        request.state.request_id = value
        response = await call_next(request)
        response.headers["X-Request-ID"] = value
        return response

    app.include_router(router)
    return app


app = create_app()
```

Create safe examples without values copied from DEUCE:

```dotenv
# backend/.env.example
TENNIX_PROVIDER_MODE=fake
TENNIX_LIVETENNIS_API_KEY=
TENNIX_LIVETENNIS_BASE_URL=https://api.livetennisapi.com/api/public/v1
TENNIX_LLM_MODE=fake
TENNIX_LLM_API_KEY=
TENNIX_LLM_BASE_URL=
TENNIX_LLM_MODEL=qwen3.8-max-0902
TENNIX_PRODUCT_TIMEZONE=Asia/Macau
```

```dotenv
# frontend/.env.example
TENNIX_BACKEND_URL=http://127.0.0.1:8000
```

Append Python-generated files to `.gitignore`:

```gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
```

Run `cd backend && uv lock` to create `uv.lock`. Keep both `__init__.py` files empty.

- [ ] **Step 4: Run foundation verification**

Run:

```bash
cd backend
uv run pytest tests/test_health.py -v
uv run python -c "from app.config import Settings; print(Settings(_env_file=None).llm_model)"
```

Expected: test PASS and output exactly `qwen3.8-max-0902` with no secret value printed.

- [ ] **Step 5: Commit**

```bash
git add .gitignore backend frontend/.env.example
git commit -m "feat: establish FastAPI foundation"
```

### Task 3: Define Canonical Models and In-Memory Identity

**Files:**
- Create: `backend/app/domain.py`
- Create: `backend/app/identity.py`
- Create: `backend/tests/test_domain.py`
- Create: `backend/tests/test_identity.py`

**Interfaces:**
- Consumes: UTC-aware `datetime` values and provider-scoped `(entity, provider, external_id)` keys.
- Produces: `Player`, `Tournament`, `Match`, `MatchScore`, `SetScore`, `LiveMatchState`, `DataFreshness`, `MatchStatus`, and `MemoryIdentityRepository`.

- [ ] **Step 1: Write failing model and identity tests**

Create tests that pin UTC validation and non-leaking IDs:

```python
# backend/tests/test_identity.py
from app.identity import MemoryIdentityRepository


def test_internal_id_is_stable_in_process_and_reversible() -> None:
    repository = MemoryIdentityRepository()
    first = repository.get_or_create("match", "livetennis", "21131")
    second = repository.get_or_create("match", "livetennis", "21131")

    assert first == second
    assert first.startswith("mat_")
    assert "21131" not in first
    assert repository.external_id("match", "livetennis", first) == "21131"
```

```python
# backend/tests/test_domain.py
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain import DataFreshness


def test_freshness_requires_timezone_aware_datetimes() -> None:
    with pytest.raises(ValidationError):
        DataFreshness(provider="fake", observed_at=datetime(2026, 9, 8, 12, 0))

    value = DataFreshness(
        provider="fake",
        observed_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
    )
    assert value.is_stale is False
```

- [ ] **Step 2: Run tests to verify missing modules**

Run: `cd backend && uv run pytest tests/test_domain.py tests/test_identity.py -v`

Expected: FAIL with imports for `app.domain` and `app.identity` missing.

- [ ] **Step 3: Implement the seven canonical models and repository**

Create `backend/app/domain.py` with these exact fields:

```python
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator


class MatchStatus(StrEnum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"
    UNKNOWN = "unknown"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DataFreshness(FrozenModel):
    provider: str
    source_updated_at: datetime | None = None
    observed_at: datetime
    is_stale: bool = False
    age_seconds: int = 0

    @field_validator("source_updated_at", "observed_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class Player(FrozenModel):
    id: str
    name: str
    country_code: str | None = None
    ranking: int | None = None


class Tournament(FrozenModel):
    id: str
    name: str
    tour: str | None = None


class SetScore(FrozenModel):
    number: int
    player1_games: int | None = None
    player2_games: int | None = None


class MatchScore(FrozenModel):
    sets_won: tuple[int, int]
    sets: tuple[SetScore, ...]
    points: tuple[str | None, str | None] = (None, None)
    is_tiebreak: bool = False


class LiveMatchState(FrozenModel):
    score: MatchScore | None = None
    server_player_id: str | None = None


class Match(FrozenModel):
    id: str
    status: MatchStatus
    players: tuple[Player, Player]
    tournament: Tournament
    scheduled_at: datetime | None = None
    round: str | None = None
    surface: str | None = None
    indoor: bool | None = None
    format: str | None = None
    live_state: LiveMatchState | None = None
    winner_player_id: str | None = None
    freshness: DataFreshness

    @field_validator("scheduled_at")
    @classmethod
    def require_scheduled_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("scheduled_at must be timezone-aware")
        return value
```

Create `backend/app/identity.py`:

```python
from uuid import uuid4


class MemoryIdentityRepository:
    PREFIXES = {"match": "mat", "player": "ply", "tournament": "trn"}

    def __init__(self) -> None:
        self._forward: dict[tuple[str, str, str], str] = {}
        self._reverse: dict[tuple[str, str, str], str] = {}

    def get_or_create(self, entity: str, provider: str, external_id: str) -> str:
        prefix = self.PREFIXES[entity]
        key = (entity, provider, str(external_id))
        if key not in self._forward:
            internal_id = f"{prefix}_{uuid4().hex}"
            self._forward[key] = internal_id
            self._reverse[(entity, provider, internal_id)] = str(external_id)
        return self._forward[key]

    def external_id(self, entity: str, provider: str, internal_id: str) -> str | None:
        return self._reverse.get((entity, provider, internal_id))
```

- [ ] **Step 4: Run model tests**

Run: `cd backend && uv run pytest tests/test_domain.py tests/test_identity.py -v`

Expected: all tests PASS, including rejection of naive datetimes and absence of provider IDs in internal IDs.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain.py backend/app/identity.py backend/tests/test_domain.py backend/tests/test_identity.py
git commit -m "feat: define canonical tennis models"
```

### Task 4: Add the Provider Contract and Deterministic Fake

**Files:**
- Create: `backend/app/providers/__init__.py`
- Create: `backend/app/providers/base.py`
- Create: `backend/app/providers/fake.py`
- Create: `backend/tests/test_provider_contract.py`

**Interfaces:**
- Consumes: internal player/match IDs from `MemoryIdentityRepository`.
- Produces: async `TennisDataProvider` protocol and `FakeTennisProvider` implementing all five methods.

- [ ] **Step 1: Write the provider contract test**

Create `backend/tests/test_provider_contract.py`:

```python
from datetime import datetime, timezone

import pytest

from app.domain import MatchStatus
from app.identity import MemoryIdentityRepository
from app.providers.base import TennisDataProvider
from app.providers.fake import FakeTennisProvider


@pytest.mark.asyncio
async def test_fake_provider_satisfies_contract_without_external_ids() -> None:
    repository = MemoryIdentityRepository()
    provider: TennisDataProvider = FakeTennisProvider(
        identities=repository,
        now=lambda: datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
    )

    players = await provider.search_players("Sinner")
    fixtures = await provider.get_fixtures(player_id=players[0].id)
    live = await provider.get_live_matches(player_id=None)
    detail = await provider.get_match(fixtures[0].id)
    score = await provider.get_score(live[0].id)

    assert fixtures[0].status is MatchStatus.SCHEDULED
    assert detail.id == fixtures[0].id
    assert score.server_player_id == live[0].players[0].id
    assert all("fake-" not in item.id for item in [*players, *fixtures, *live])
```

- [ ] **Step 2: Run the test to verify the protocol and fake are missing**

Run: `cd backend && uv run pytest tests/test_provider_contract.py -v`

Expected: FAIL on missing `app.providers.base`.

- [ ] **Step 3: Define exact async signatures and deterministic fixture data**

Create `backend/app/providers/base.py`:

```python
from typing import Protocol

from app.domain import LiveMatchState, Match, Player


class TennisDataProvider(Protocol):
    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        raise NotImplementedError

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        raise NotImplementedError

    async def search_players(self, query: str) -> list[Player]:
        raise NotImplementedError

    async def get_match(self, match_id: str) -> Match:
        raise NotImplementedError

    async def get_score(self, match_id: str) -> LiveMatchState:
        raise NotImplementedError
```

Implement `FakeTennisProvider` with one shared `_matches` dictionary created in `__init__`. Use repository mappings for external IDs `fake-sinner`, `fake-alcaraz`, `fake-djokovic`, `fake-ruud`, `fake-upcoming`, and `fake-live`; return:

```python
self.sinner_alcaraz = Match(
    id=identities.get_or_create("match", "fake", "fake-upcoming"),
    status=MatchStatus.SCHEDULED,
    players=(sinner, alcaraz),
    tournament=atp_finals,
    scheduled_at=datetime(2026, 9, 8, 12, 30, tzinfo=timezone.utc),
    round="Semifinal",
    surface="hard",
    indoor=True,
    format="BO3",
    freshness=DataFreshness(provider="fake", observed_at=now()),
)
```

Create a second live match at `2026-09-08T10:00:00Z` with sets `6–4, 4–6, 4–5`, points `30–15`, and Sinner serving. `search_players` performs case-insensitive substring matching; list methods optionally filter either participant; unknown IDs raise the `not_found` `AppError` defined below:

```python
raise AppError("not_found", "Match not found", 404)
```

The fake's public methods return new list objects but may reuse immutable Pydantic model instances.

- [ ] **Step 4: Run the provider contract test**

Run: `cd backend && uv run pytest tests/test_provider_contract.py -v`

Expected: PASS with all five protocol methods exercised.

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers backend/tests/test_provider_contract.py
git commit -m "test: add deterministic tennis provider"
```

### Task 5: Implement the LiveTennisAPI Adapter

**Files:**
- Create: `backend/app/providers/livetennis_dtos.py`
- Create: `backend/app/providers/livetennis.py`
- Create: `backend/tests/fixtures/livetennis/players.json`
- Create: `backend/tests/fixtures/livetennis/fixtures.json`
- Create: `backend/tests/fixtures/livetennis/matches_live.json`
- Create: `backend/tests/fixtures/livetennis/match_detail.json`
- Create: `backend/tests/fixtures/livetennis/score.json`
- Create: `backend/tests/test_livetennis_provider.py`

**Interfaces:**
- Consumes: official Free endpoints `GET /players?search=`, `/fixtures`, `/matches?status=live`, `/matches/{id}`, and `/matches/{id}/score` using `X-API-Key`.
- Produces: `LiveTennisProvider` implementing `TennisDataProvider` and returning canonical models only.

- [ ] **Step 1: Record safe contract fixtures and write failing parser tests**

Use sanitized examples matching the official schema. The central live fixture must contain this score shape plus an unknown additive field:

```json
{
  "data": [{
    "id": 21131,
    "tournament": "ATP Finals",
    "tournament_id": "1217",
    "tour": "atp",
    "surface": "hard",
    "indoor": true,
    "format": "BO3",
    "round": "Semifinal",
    "status": "live",
    "event_status": null,
    "scheduled_time": "2026-09-08T12:30:00Z",
    "players": {
      "p1": {"id": 101, "name": "Jannik Sinner", "country": "ita", "ranking": 1},
      "p2": {"id": 102, "name": "Carlos Alcaraz", "country": "esp", "ranking": 2}
    },
    "score": {
      "sets": [1, 1],
      "games": [[6, 4, 4], [4, 6, 5]],
      "points": ["30", "15"],
      "server": 1,
      "is_tiebreak": false,
      "timestamp": "2026-09-08T10:00:00Z"
    },
    "future_additive_field": "ignored"
  }],
  "meta": {"limit": 50, "offset": 0, "count": 1, "total": 1, "has_more": false}
}
```

Write tests using `httpx.MockTransport` that assert player-major arrays become three `SetScore` rows, server `1` becomes player 1's internal ID, `completed` maps to `finished`, `Postponed` maps to `postponed`, fixture null start time remains `None`, and unknown fields do not fail validation.

- [ ] **Step 2: Run adapter tests to verify imports fail**

Run: `cd backend && uv run pytest tests/test_livetennis_provider.py -v`

Expected: FAIL because `LiveTennisProvider` and DTOs do not exist.

- [ ] **Step 3: Implement permissive DTOs, mapping, and exact error translation**

Define vendor DTOs with `ConfigDict(extra="ignore")`, including `LivePlayerDto`, `LiveScoreDto`, `LiveMatchDto`, `LiveFixtureDto`, and `ListResponse[T]`. The score mapper must transpose player-major games safely:

```python
def map_score(dto: LiveScoreDto) -> MatchScore:
    p1_games, p2_games = (dto.games + [[], []])[:2]
    set_count = max(len(p1_games), len(p2_games))
    sets = tuple(
        SetScore(
            number=index + 1,
            player1_games=p1_games[index] if index < len(p1_games) else None,
            player2_games=p2_games[index] if index < len(p2_games) else None,
        )
        for index in range(set_count)
    )
    points = tuple((dto.points + [None, None])[:2])
    return MatchScore(
        sets_won=tuple((dto.sets + [0, 0])[:2]),
        sets=sets,
        points=points,
        is_tiebreak=dto.is_tiebreak,
    )
```

`LiveTennisProvider` owns one injected `httpx.AsyncClient`, `MemoryIdentityRepository`, and UTC clock. `_request()` sends `X-API-Key`, uses a 10-second timeout at client construction, and translates responses exactly:

```python
if response.status_code == 404:
    raise AppError("not_found", "Provider resource not found", 404)
if response.status_code == 429:
    raise AppError(
        "rate_limited",
        "LiveTennisAPI quota exceeded",
        429,
        {"retry_after": response.headers.get("Retry-After")},
    )
if response.status_code == 403:
    raise AppError("provider_unavailable", "Provider plan does not support this request", 503)
if response.status_code >= 400:
    raise AppError("provider_unavailable", "LiveTennisAPI request failed", 503)
```

Map fixture IDs into the same match identity namespace as `/matches`, map nullable player IDs by using `fixture:{fixture_id}:p1|p2` only when an ID is absent, and filter `/fixtures` locally when `player_id` is supplied because that endpoint has no player filter. Never call a completed/history endpoint.

- [ ] **Step 4: Run adapter and contract tests**

Run: `cd backend && uv run pytest tests/test_livetennis_provider.py tests/test_provider_contract.py -v`

Expected: PASS, including exact `X-API-Key`, query parameter, transposition, null, unknown-field, 404, 429, and 403 assertions.

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers backend/tests/fixtures backend/tests/test_livetennis_provider.py
git commit -m "feat: add LiveTennisAPI provider"
```

### Task 6: Add the Bounded Async TTL Cache

**Files:**
- Create: `backend/app/cache.py`
- Create: `backend/tests/test_cache.py`

**Interfaces:**
- Consumes: hashable keys, async zero-argument loaders, fresh TTL, stale-fallback TTL, and an injectable monotonic clock.
- Produces: `AsyncTTLCache.get_or_load()` returning `CacheOutcome[T]` with `value`, `is_stale`, and `age_seconds`.

- [ ] **Step 1: Write failing cache behavior tests**

Create tests for fresh hits, coalescing, stale fallback, expiry, and LRU bounds. The coalescing test must prove one loader call under concurrency:

```python
@pytest.mark.asyncio
async def test_coalesces_identical_inflight_loads() -> None:
    calls = 0
    gate = asyncio.Event()
    cache: AsyncTTLCache[str, str] = AsyncTTLCache(max_entries=256)

    async def loader() -> str:
        nonlocal calls
        calls += 1
        await gate.wait()
        return "value"

    tasks = [asyncio.create_task(cache.get_or_load("key", loader, ttl=60, stale_ttl=300)) for _ in range(3)]
    await asyncio.sleep(0)
    gate.set()
    results = await asyncio.gather(*tasks)

    assert calls == 1
    assert [result.value for result in results] == ["value", "value", "value"]
```

Use an injected numeric clock in the remaining tests. Assert a loader exception returns a marked stale entry only while `age <= stale_ttl`, re-raises beyond it, and the 257th distinct insertion evicts the least-recently-used entry.

- [ ] **Step 2: Run tests to verify the cache is missing**

Run: `cd backend && uv run pytest tests/test_cache.py -v`

Expected: FAIL on missing `app.cache`.

- [ ] **Step 3: Implement cache outcomes, entries, coalescing, and LRU eviction**

Create these public types in `backend/app/cache.py`:

```python
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from time import monotonic
from typing import Generic, TypeVar
import asyncio

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass(frozen=True)
class CacheOutcome(Generic[V]):
    value: V
    is_stale: bool
    age_seconds: int


@dataclass
class _Entry(Generic[V]):
    value: V
    loaded_at: float
    ttl: int


class AsyncTTLCache(Generic[K, V]):
    def __init__(self, max_entries: int, now: Callable[[], float] = monotonic) -> None:
        self._max_entries = max_entries
        self._now = now
        self._entries: OrderedDict[K, _Entry[V]] = OrderedDict()
        self._inflight: dict[K, asyncio.Task[V]] = {}

    async def get_or_load(
        self,
        key: K,
        loader: Callable[[], Awaitable[V]],
        *,
        ttl: int | Callable[[V], int],
        stale_ttl: int | Callable[[V], int],
    ) -> CacheOutcome[V]:
        current = self._entries.get(key)
        if current is not None:
            age = max(0.0, self._now() - current.loaded_at)
            if age <= current.ttl:
                self._entries.move_to_end(key)
                return CacheOutcome(current.value, False, int(age))

        task = self._inflight.get(key)
        if task is None:
            async def load_and_store() -> V:
                value = await loader()
                resolved_ttl = ttl(value) if callable(ttl) else ttl
                self._entries[key] = _Entry(value=value, loaded_at=self._now(), ttl=resolved_ttl)
                self._entries.move_to_end(key)
                while len(self._entries) > self._max_entries:
                    self._entries.popitem(last=False)
                return value

            task = asyncio.create_task(load_and_store())
            self._inflight[key] = task

            def remove_inflight(done: asyncio.Task[V]) -> None:
                if self._inflight.get(key) is done:
                    self._inflight.pop(key, None)

            task.add_done_callback(remove_inflight)

        try:
            value = await asyncio.shield(task)
        except Exception:
            current = self._entries.get(key)
            if current is None:
                raise
            age = max(0.0, self._now() - current.loaded_at)
            resolved_stale_ttl = stale_ttl(current.value) if callable(stale_ttl) else stale_ttl
            if age > resolved_stale_ttl:
                raise
            self._entries.move_to_end(key)
            return CacheOutcome(current.value, True, int(age))

        stored = self._entries[key]
        return CacheOutcome(value, False, int(max(0.0, self._now() - stored.loaded_at)))
```

This implementation deliberately accepts value-based TTL callables so empty lists and missing matches can use a 30-second negative TTL without a second cache type.

- [ ] **Step 4: Run cache tests**

Run: `cd backend && uv run pytest tests/test_cache.py -v`

Expected: all cache tests PASS with no sleeps longer than one event-loop turn.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cache.py backend/tests/test_cache.py
git commit -m "feat: add bounded request cache"
```

### Task 7: Implement TennisService and Time Semantics

**Files:**
- Create: `backend/app/service.py`
- Create: `backend/tests/test_service.py`

**Interfaces:**
- Consumes: `TennisDataProvider`, `AsyncTTLCache`, an aware UTC clock, and `Asia/Macau` timezone.
- Produces: `MatchTimeScope`, `TennisService.search_players()`, `list_matches()`, `find_player_matches()`, and `get_match()`.

- [ ] **Step 1: Write failing service tests for every selection rule**

Create clock-controlled tests covering:

```python
@pytest.mark.parametrize(
    ("now", "expected_start", "expected_end"),
    [
        ("2026-09-08T02:00:00+08:00", "2026-09-07T18:00:00+08:00", "2026-09-08T06:00:00+08:00"),
        ("2026-09-08T12:00:00+08:00", "2026-09-08T18:00:00+08:00", "2026-09-09T06:00:00+08:00"),
        ("2026-09-08T20:00:00+08:00", "2026-09-08T18:00:00+08:00", "2026-09-09T06:00:00+08:00"),
    ],
)
def test_tonight_window(now: str, expected_start: str, expected_end: str) -> None:
    assert tonight_window(datetime.fromisoformat(now)) == (
        datetime.fromisoformat(expected_start),
        datetime.fromisoformat(expected_end),
    )
```

Also assert: exact case-insensitive player match wins; multiple substring matches raise `ambiguous_player` with candidate IDs/names; no match raises `not_found`; `next` chooses the earliest future non-terminal match; past scheduled fixtures are excluded; live matches remain eligible; live list/detail stale fallback is at most 300 seconds; upcoming fallback is at most 1,800 seconds; player-search TTL is 3,600 seconds; and empty results are reused for 30 seconds.

- [ ] **Step 2: Run tests to verify the service is missing**

Run: `cd backend && uv run pytest tests/test_service.py -v`

Expected: FAIL on missing `app.service`.

- [ ] **Step 3: Implement exact service signatures and policies**

Create `backend/app/service.py` with:

```python
import asyncio
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from enum import StrEnum
from typing import cast
from zoneinfo import ZoneInfo

from app.cache import AsyncTTLCache, CacheOutcome
from app.domain import Match, MatchStatus, Player
from app.errors import AppError
from app.providers.base import TennisDataProvider


class MatchTimeScope(StrEnum):
    TODAY = "today"
    TONIGHT = "tonight"
    NEXT = "next"


def tonight_window(now_local: datetime) -> tuple[datetime, datetime]:
    day = now_local.date()
    if now_local.time() < time(6):
        start_day = day - timedelta(days=1)
    else:
        start_day = day
    start = datetime.combine(start_day, time(18), tzinfo=now_local.tzinfo)
    return start, start + timedelta(hours=12)


class TennisService:
    def __init__(
        self,
        provider: TennisDataProvider,
        cache: AsyncTTLCache[str, object],
        now: Callable[[], datetime],
        timezone: str,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._now = now
        self._timezone = ZoneInfo(timezone)

    async def search_players(self, query: str) -> list[Player]:
        normalized = query.strip()
        if not normalized:
            raise AppError("invalid_request", "Player query is required", 422)

        async def load() -> object:
            return await self._provider.search_players(normalized)

        outcome = await self._cache.get_or_load(
            f"players:{normalized.casefold()}",
            load,
            ttl=lambda value: 30 if not cast(list[Player], value) else 3600,
            stale_ttl=0,
        )
        return cast(list[Player], outcome.value)

    async def _resolve_player(self, query: str) -> Player:
        players = await self.search_players(query)
        exact = [player for player in players if player.name.casefold() == query.strip().casefold()]
        candidates = exact or players
        if not candidates:
            raise AppError("not_found", "Player not found", 404)
        if len(candidates) > 1:
            raise AppError(
                "ambiguous_player",
                "Player name is ambiguous",
                409,
                {"candidates": [{"id": player.id, "name": player.name} for player in candidates]},
            )
        return candidates[0]

    def _mark_matches(self, outcome: CacheOutcome[object]) -> list[Match]:
        matches = cast(list[Match], outcome.value)
        if not outcome.is_stale:
            return matches
        return [
            match.model_copy(update={
                "freshness": match.freshness.model_copy(update={
                    "is_stale": True,
                    "age_seconds": outcome.age_seconds,
                }),
            })
            for match in matches
        ]

    async def _list_by_player_id(self, status: str, player_id: str | None) -> list[Match]:
        if status not in {"live", "upcoming"}:
            raise AppError("invalid_request", "Status must be live or upcoming", 422)

        async def load() -> object:
            if status == "live":
                return await self._provider.get_live_matches(player_id=player_id)
            return await self._provider.get_fixtures(player_id=player_id)

        fresh_ttl = 60 if status == "live" else 600
        stale_limit = 300 if status == "live" else 1800
        outcome = await self._cache.get_or_load(
            f"matches:{status}:{player_id or 'all'}",
            load,
            ttl=lambda value: 30 if not cast(list[Match], value) else fresh_ttl,
            stale_ttl=lambda value: 0 if not cast(list[Match], value) else stale_limit,
        )
        return self._mark_matches(outcome)

    async def list_matches(self, status: str, player_name: str | None = None) -> list[Match]:
        player = await self._resolve_player(player_name) if player_name else None
        return await self._list_by_player_id(status, player.id if player else None)

    async def find_player_matches(
        self,
        player_name: str,
        time_scope: MatchTimeScope,
    ) -> list[Match]:
        player = await self._resolve_player(player_name)
        live, upcoming = await asyncio.gather(
            self._list_by_player_id("live", player.id),
            self._list_by_player_id("upcoming", player.id),
        )
        matches = list({match.id: match for match in [*live, *upcoming]}.values())
        now_utc = self._now()
        now_local = now_utc.astimezone(self._timezone)

        def eligible(match: Match) -> bool:
            return match.status is MatchStatus.LIVE or (
                match.scheduled_at is not None and match.scheduled_at >= now_utc
            )

        def sort_key(match: Match) -> datetime:
            return match.scheduled_at or datetime.max.replace(tzinfo=timezone.utc)

        eligible_matches = [match for match in matches if eligible(match)]
        if time_scope is MatchTimeScope.NEXT:
            future = [match for match in eligible_matches if match.status is not MatchStatus.LIVE]
            return sorted(future, key=sort_key)[:1]
        if time_scope is MatchTimeScope.TODAY:
            return sorted([
                match for match in eligible_matches
                if match.scheduled_at is not None
                and match.scheduled_at.astimezone(self._timezone).date() == now_local.date()
            ], key=sort_key)

        start, end = tonight_window(now_local)
        return sorted([
            match for match in eligible_matches
            if match.scheduled_at is not None
            and start <= match.scheduled_at.astimezone(self._timezone) < end
        ], key=sort_key)

    async def get_match(self, match_id: str) -> Match:
        async def load() -> object:
            try:
                return await self._provider.get_match(match_id)
            except AppError as error:
                if error.code == "not_found":
                    return None
                raise

        def fresh_ttl(value: object) -> int:
            match = cast(Match | None, value)
            if match is None:
                return 30
            return 60 if match.status is MatchStatus.LIVE else 600

        def stale_limit(value: object) -> int:
            match = cast(Match | None, value)
            if match is None:
                return 0
            return 300 if match.status is MatchStatus.LIVE else 1800

        outcome = await self._cache.get_or_load(
            f"match:{match_id}", load, ttl=fresh_ttl, stale_ttl=stale_limit
        )
        match = cast(Match | None, outcome.value)
        if match is None:
            raise AppError("not_found", "Match not found", 404)
        if not outcome.is_stale:
            return match
        return match.model_copy(update={
            "freshness": match.freshness.model_copy(update={
                "is_stale": True,
                "age_seconds": outcome.age_seconds,
            }),
        })
```

- [ ] **Step 4: Run service and lower-layer tests**

Run: `cd backend && uv run pytest tests/test_service.py tests/test_cache.py tests/test_provider_contract.py -v`

Expected: PASS with provider call counters proving every TTL and negative-cache rule.

- [ ] **Step 5: Commit**

```bash
git add backend/app/service.py backend/tests/test_service.py
git commit -m "feat: add tennis query service"
```

### Task 8: Expose Deterministic REST APIs

**Files:**
- Create: `backend/app/api/schemas.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `TennisService` and stable `AppError` values.
- Produces: typed health/player/match endpoints, one error envelope, request-ID propagation, and injectable application wiring.

- [ ] **Step 1: Write failing endpoint and error-envelope tests**

Use `create_app(settings, provider=fake_provider)` and assert:

```python
@pytest.mark.asyncio
async def test_match_list_never_exposes_provider_ids(client: AsyncClient) -> None:
    response = await client.get("/api/v1/matches", params={"status": "upcoming", "player": "Sinner"})
    body = response.json()

    assert response.status_code == 200
    assert body["data"][0]["id"].startswith("mat_")
    assert "external_id" not in response.text
    assert "fake-upcoming" not in response.text


@pytest.mark.asyncio
async def test_invalid_status_has_stable_error(client: AsyncClient) -> None:
    response = await client.get("/api/v1/matches", params={"status": "finished"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
```

Also test `/players/search?q=`, `/matches/{match_id}`, unknown match 404, ambiguous player 409, provider 503, quota 429 with `Retry-After`, and generated request IDs.

- [ ] **Step 2: Run API tests to verify routes are absent**

Run: `cd backend && uv run pytest tests/test_api.py -v`

Expected: FAIL because the application only exposes health.

- [ ] **Step 3: Add response envelopes, exception handlers, routes, and app wiring**

Create `backend/app/api/schemas.py`:

```python
from typing import Any
from pydantic import BaseModel, Field

from app.domain import Match, Player


class PlayerListResponse(BaseModel):
    data: list[Player]


class MatchListResponse(BaseModel):
    data: list[Match]


class MatchResponse(BaseModel):
    data: Match


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody
    request_id: str
```

Add dependencies that read `request.app.state.tennis_service`, routes with `Query(min_length=1)` and `Literal["live", "upcoming"]`, and exception handlers for both `AppError` and `RequestValidationError`. Translate validation to `invalid_request`; `ambiguous_player` is 409; `not_found` is 404; `rate_limited` is 429 and copies `retry_after` to `Retry-After`; provider errors are 503.

Change the factory to:

```python
def create_app(
    settings: Settings | None = None,
    *,
    provider: TennisDataProvider | None = None,
    chat_orchestrator=None,
) -> FastAPI:
```

Build one `MemoryIdentityRepository`, provider, `AsyncTTLCache(max_entries=settings.cache_max_entries)`, and `TennisService`. Use `FakeTennisProvider` in fake mode and `LiveTennisProvider` with one lifespan-managed `httpx.AsyncClient(timeout=10.0)` in live mode. Store service and optional orchestrator on `app.state`; close the live client at shutdown.

Parse `settings.fixed_now` once at startup, accepting a trailing `Z` by replacing it with `+00:00`, reject a naive value, and inject one shared clock into the fake provider and service:

```python
fixed_now = (
    datetime.fromisoformat(settings.fixed_now.replace("Z", "+00:00"))
    if settings.fixed_now
    else None
)
if fixed_now is not None and fixed_now.tzinfo is None:
    raise ValueError("TENNIX_FIXED_NOW must be timezone-aware")
clock = (lambda: fixed_now) if fixed_now is not None else (lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Run the full deterministic backend suite**

Run: `cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live" -v`

Expected: PASS; the response text contains no provider external IDs or credentials.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat: expose deterministic tennis API"
```

### Task 9: Add Thin Next.js Route Handler Proxies

**Files:**
- Create: `frontend/lib/server/backend-proxy.ts`
- Create: `frontend/lib/server/backend-proxy.test.ts`
- Create: `frontend/app/api/players/search/route.ts`
- Create: `frontend/app/api/matches/route.ts`
- Create: `frontend/app/api/matches/[matchId]/route.ts`
- Create: `frontend/app/api/chat/stream/route.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`

**Interfaces:**
- Consumes: incoming Next.js `Request`, server-only `TENNIX_BACKEND_URL`, and a fixed FastAPI path.
- Produces: transparent `GET`/`POST` proxies preserving body streaming, status, content type, request ID, cache control, and retry information.

- [ ] **Step 1: Install unit-test dependencies and write failing proxy tests**

Run: `cd frontend && pnpm add -D vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event vite-tsconfig-paths`

Add scripts:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit"
  }
}
```

Create `frontend/lib/server/backend-proxy.test.ts` to mock `global.fetch` and assert:

```ts
it('preserves SSE without reading the upstream body', async () => {
  const stream = new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode('event: done\ndata: {}\n\n')) } })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream', 'X-Request-ID': 'req-1' },
  })))

  const response = await proxyBackend(new Request('http://local/api/chat/stream', {
    method: 'POST', body: '{"scope":"global","messages":[]}',
  }), '/api/v1/chat/stream')

  expect(response.body).toBe(stream)
  expect(response.headers.get('content-type')).toBe('text/event-stream')
  expect(response.headers.get('x-request-id')).toBe('req-1')
})
```

Also assert query strings are copied, 429 and `Retry-After` are preserved, authorization/cookie headers are not forwarded, a fetch rejection becomes typed `internal_error` with HTTP 502, and the response never contains the backend base URL.

- [ ] **Step 2: Run the test to verify proxy code is missing**

Run: `cd frontend && pnpm test -- lib/server/backend-proxy.test.ts`

Expected: FAIL because `proxyBackend` does not exist.

- [ ] **Step 3: Implement one reusable proxy and four route modules**

Create `frontend/lib/server/backend-proxy.ts`:

```ts
const RESPONSE_HEADERS = ['content-type', 'cache-control', 'retry-after', 'x-request-id']

export async function proxyBackend(request: Request, path: string): Promise<Response> {
  const baseUrl = process.env.TENNIX_BACKEND_URL
  if (!baseUrl) {
    return Response.json({ error: { code: 'internal_error', message: 'Backend URL is not configured', details: {} } }, { status: 500 })
  }

  const incoming = new URL(request.url)
  const target = new URL(path, baseUrl)
  target.search = incoming.search
  const headers = new Headers({ 'Content-Type': request.headers.get('content-type') ?? 'application/json' })
  const requestId = request.headers.get('x-request-id')
  if (requestId) headers.set('X-Request-ID', requestId)

  let upstream: Response
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === 'GET' || request.method === 'HEAD' ? undefined : request.body,
      cache: 'no-store',
      duplex: 'half',
    } as RequestInit)
  } catch {
    return Response.json(
      { error: { code: 'internal_error', message: 'Backend is unavailable', details: {} } },
      { status: 502 },
    )
  }

  const responseHeaders = new Headers()
  for (const name of RESPONSE_HEADERS) {
    const value = upstream.headers.get(name)
    if (value) responseHeaders.set(name, value)
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders })
}
```

Each static route calls `proxyBackend(request, exactFastApiPath)`. The dynamic route awaits `params: Promise<{ matchId: string }>` and uses `encodeURIComponent(matchId)`. Export `runtime = 'nodejs'` and `dynamic = 'force-dynamic'` from all four modules. Do not add response transformation or CORS logic.

- [ ] **Step 4: Run frontend unit, type, and build checks**

Run:

```bash
cd frontend
pnpm test -- lib/server/backend-proxy.test.ts
pnpm typecheck
pnpm build
```

Expected: all commands PASS. If TypeScript's DOM `RequestInit` rejects `duplex`, define a local intersection type containing `duplex: 'half'`; do not remove streaming.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: proxy frontend requests to FastAPI"
```

### Task 10: Define Chat Models, Historical Guard, and Business Tools

**Files:**
- Create: `backend/app/chat/__init__.py`
- Create: `backend/app/chat/models.py`
- Create: `backend/app/chat/tools.py`
- Create: `backend/tests/test_chat_tools.py`

**Interfaces:**
- Consumes: `TennisService`, raw user messages, global or match scope, and Pydantic-validated tool arguments.
- Produces: three JSON schemas, `BusinessTools.execute()`, structured tool results, and deterministic historical-query rejection.

- [ ] **Step 1: Write failing schema, dispatch, context, and unsupported tests**

Pin the exact tool names and enum schema:

```python
def test_tool_catalog_is_exactly_p1_surface(tools: BusinessTools) -> None:
    catalog = tools.catalog()
    assert [item["function"]["name"] for item in catalog] == [
        "find_player_matches", "get_live_matches", "get_match"
    ]
    scope = catalog[0]["function"]["parameters"]["properties"]["time_scope"]
    assert scope["enum"] == ["today", "tonight", "next"]


@pytest.mark.asyncio
async def test_match_scope_injects_match_id(tools: BusinessTools, known_match_id: str) -> None:
    result = await tools.execute("get_match", {}, ChatContext(scope="match", match_id=known_match_id))
    assert result.matches[0].id == known_match_id


def test_historical_query_is_rejected_without_calling_model() -> None:
    assert is_historical_query("昨天 Sinner 赢了吗？") is True
    assert is_historical_query("Sinner tonight?") is False
```

Also test malformed args yield `invalid_request`, a global `get_match` without `match_id` fails, explicit tool `match_id` cannot override Match Page context, and tool results contain domain models rather than serialized vendor payloads.

- [ ] **Step 2: Run tests to verify chat modules are absent**

Run: `cd backend && uv run pytest tests/test_chat_tools.py -v`

Expected: FAIL on missing `app.chat.models`.

- [ ] **Step 3: Implement chat contracts and exactly three dispatch paths**

Create Pydantic models:

```python
class ChatScope(StrEnum):
    GLOBAL = "global"
    MATCH = "match"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    scope: ChatScope
    match_id: str | None = None
    messages: list[ChatMessage] = Field(min_length=1, max_length=12)


class ChatContext(BaseModel):
    scope: ChatScope
    match_id: str | None = None


class StructuredToolResult(BaseModel):
    kind: Literal["matches", "match", "unsupported"]
    matches: list[Match] = Field(default_factory=list)


class FindPlayerMatchesArgs(BaseModel):
    player_name: str = Field(min_length=1)
    time_scope: MatchTimeScope


class GetLiveMatchesArgs(BaseModel):
    player_name: str | None = None


class GetMatchArgs(BaseModel):
    match_id: str | None = None
```

`BusinessTools.catalog()` returns the three definitions in the order shown in Step 1, using each argument model's `model_json_schema()` as `function.parameters`. Each item has shape `{"type":"function","function":{"name", "description", "parameters"}}` and uses these descriptions:

```python
DESCRIPTIONS = {
    "find_player_matches": "Find a player's matches for today, tonight, or their next scheduled match.",
    "get_live_matches": "List matches that are live now, optionally filtered by player name.",
    "get_match": "Get trusted details for one Tennix internal match ID.",
}
```

`BusinessTools.execute()` validates through the matching model and dispatches exactly as follows:

```python
if name == "find_player_matches":
    args = FindPlayerMatchesArgs.model_validate(arguments)
    matches = await self._service.find_player_matches(args.player_name, args.time_scope)
    return StructuredToolResult(kind="matches", matches=matches)
if name == "get_live_matches":
    args = GetLiveMatchesArgs.model_validate(arguments)
    matches = await self._service.list_matches("live", args.player_name)
    return StructuredToolResult(kind="matches", matches=matches)
if name == "get_match":
    args = GetMatchArgs.model_validate(arguments)
    match_id = context.match_id if context.scope is ChatScope.MATCH else args.match_id
    if match_id is None:
        raise AppError("invalid_request", "match_id is required", 422)
    return StructuredToolResult(kind="match", matches=[await self._service.get_match(match_id)])
raise AppError("invalid_request", f"Unknown tool: {name}", 422)
```

Catch `ValidationError` at the dispatcher boundary and translate it to `AppError("invalid_request", "Invalid tool arguments", 422, {"tool": name})`. In Match scope, ignore any model-supplied `match_id` in favor of `ChatContext.match_id`.

Implement `is_historical_query()` as a case-insensitive guard over these P1 phrases: `昨天`, `昨日`, `上一场`, `最近一场`, `历史`, `yesterday`, `last match`, `previous match`, and `history`. `ChatOrchestrator` uses the boolean to create `StructuredToolResult(kind="unsupported")` plus fixed copy `P1 暂不支持历史比赛结果查询。`; it never calls the provider or model. Keep this policy in the chat layer, not `TennisService`, because deterministic REST has no history endpoint.

- [ ] **Step 4: Run chat-tool and service tests**

Run: `cd backend && uv run pytest tests/test_chat_tools.py tests/test_service.py -v`

Expected: PASS with exactly three tools and no provider call during the historical test.

- [ ] **Step 5: Commit**

```bash
git add backend/app/chat backend/tests/test_chat_tools.py
git commit -m "feat: define tennis chat tools"
```

### Task 11: Add the OpenAI-Compatible Tool Loop and SSE Route

**Files:**
- Create: `backend/app/chat/client.py`
- Create: `backend/app/chat/orchestrator.py`
- Modify: `backend/app/chat/models.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_chat_orchestrator.py`
- Create: `backend/tests/test_chat_api.py`

**Interfaces:**
- Consumes: `BusinessTools`, a `ChatModel`, at most 12 browser-supplied messages, and a global/match context.
- Produces: ordered `status`, `data`, `text_delta`, `done`, and `error` events from `POST /api/v1/chat/stream`.

- [ ] **Step 1: Write failing tool-loop and stream-order tests**

Use a scripted fake model to prove these sequences:

```python
@pytest.mark.asyncio
async def test_tool_result_precedes_generated_text(orchestrator, request) -> None:
    events = [event async for event in orchestrator.stream(request)]
    assert [event.type for event in events] == ["status", "data", "text_delta", "done"]
    assert events[1].payload["matches"][0]["id"].startswith("mat_")


@pytest.mark.asyncio
async def test_llm_failure_after_data_keeps_structured_result(orchestrator_with_stream_failure, request) -> None:
    events = [event async for event in orchestrator_with_stream_failure.stream(request)]
    assert [event.type for event in events] == ["status", "data", "text_delta", "error"]
    assert events[2].payload["delta"] == "比赛数据已找到，但 AI 说明暂时不可用。"
    assert events[3].payload["code"] == "llm_unavailable"
```

Also assert: historical guard emits `data(unsupported)`, fixed text, and `done` with zero model/provider calls; a provider exception emits only `status,error`; a third requested tool round emits `invalid_request`; Match Page context is present in the system message; and SSE frames end with exactly two newlines.

- [ ] **Step 2: Run tests to verify model client and orchestrator are missing**

Run: `cd backend && uv run pytest tests/test_chat_orchestrator.py tests/test_chat_api.py -v`

Expected: FAIL on missing `app.chat.client` or `ChatOrchestrator`.

- [ ] **Step 3: Implement internal model turns, clients, and bounded orchestration**

Add these internal contracts to `backend/app/chat/models.py`:

```python
class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, object]


class ModelTurn(BaseModel):
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ChatEventType(StrEnum):
    STATUS = "status"
    DATA = "data"
    TEXT_DELTA = "text_delta"
    DONE = "done"
    ERROR = "error"


class ChatEvent(BaseModel):
    type: ChatEventType
    payload: dict[str, object]

    def to_sse(self) -> str:
        return f"event: {self.type.value}\ndata: {json.dumps(self.payload, ensure_ascii=False)}\n\n"
```

Define a `ChatModel` protocol with `choose(messages, tools) -> ModelTurn` and `stream_text(messages) -> AsyncIterator[str]`. `FakeChatModel` uses deterministic scripted turns supplied by tests and a small runtime default: global requests containing a player name select `find_player_matches`; a global score/live request without a player selects `get_live_matches`; match scope selects `get_match`; final text is fixed and derived only from the tool result included in messages.

`OpenAICompatibleChatModel` receives concrete `api_key`, `base_url`, and `model` constructor arguments and constructs `AsyncOpenAI(api_key=api_key, base_url=base_url)`. `choose()` calls `chat.completions.create(model=self._model, messages=messages, tools=tools, tool_choice="auto")`, parses each function's JSON arguments into `ToolCall`, and translates SDK/JSON failures to `llm_unavailable`. `stream_text()` calls the same endpoint with `model=self._model`, `stream=True`, `tool_choice="none"`, and yields only non-empty `choice.delta.content` strings.

Implement `ChatOrchestrator.stream()` with this exact order:

1. Validate Match scope has `match_id`.
2. If the latest user message is historical, emit `data`, fixed `text_delta`, and `done`, then return.
3. Emit `status={"stage":"resolving"}`.
4. Call `choose()`, execute every returned call in order, append assistant/tool messages, and emit one `data` event with `result.model_dump(mode="json")` for each structured result.
5. Repeat only when the model asks for another tool round; reject a third round with `invalid_request`.
6. Call `stream_text()` with tools disabled and emit each chunk as `text_delta`.
7. Emit `done={"ok":True}`.
8. If model streaming fails after any `data`, emit fixed fallback `text_delta` and terminal `error=llm_unavailable`; if no data exists, emit only the terminal typed error. Propagate provider `AppError` as terminal `error` without calling final generation.

The system message must state that all tennis facts require tools, external IDs are forbidden, unavailable fields must be admitted, and Match scope already identifies the current match.

- [ ] **Step 4: Wire `POST /chat/stream` and run all deterministic backend tests**

Return a `StreamingResponse` with `media_type="text/event-stream"` and headers `Cache-Control: no-cache, no-transform` and `X-Accel-Buffering: no`. The generator converts caught `AppError` values to `ChatEvent(type="error", payload={"code", "message", "details"})`; it never returns an HTML error body after streaming starts.

Run: `cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live" -v`

Expected: PASS, including event order, two-round bound, fallback copy, and no-data provider failure.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat: stream tool-backed chat responses"
```

### Task 12: Add Typed Frontend API, SSE Parsing, and View Models

**Files:**
- Create: `frontend/lib/api/types.ts`
- Create: `frontend/lib/api/client.ts`
- Create: `frontend/lib/api/client.test.ts`
- Create: `frontend/lib/view-models.ts`
- Create: `frontend/lib/view-models.test.ts`
- Create: `frontend/hooks/use-chat-stream.ts`
- Create: `frontend/hooks/use-chat-stream.test.tsx`

**Interfaces:**
- Consumes: same-origin JSON/SSE responses containing snake_case FastAPI DTOs.
- Produces: `getPlayers`, `getMatches`, `getMatch`, `streamChat`, `toHomeMatch`, `toMatchViewModel`, and `useChatStream`.

- [ ] **Step 1: Write failing DTO, SSE-boundary, mapper, and abort tests**

Pin the parser against arbitrarily split network chunks:

```ts
it('parses SSE when a frame is split across chunks', async () => {
  const chunks = [
    'event: data\ndata: {"kind":"matches","mat',
    'ches":[]}\n\nevent: text_delta\ndata: {"delta":"你好"}\n\n',
  ]
  const events = await collect(parseSse(toReadableStream(chunks)))
  expect(events).toEqual([
    { type: 'data', payload: { kind: 'matches', matches: [] } },
    { type: 'text_delta', payload: { delta: '你好' } },
  ])
})
```

Also assert non-2xx REST bodies throw `ApiError` with code/details, aborting cancels the stream without showing `internal_error`, stale matches map to a visible freshness label, null round/surface/server map to `暂未提供`, provider IDs cannot exist in DTO types, and a live score maps player-major rows correctly.

- [ ] **Step 2: Run tests to verify frontend API modules are missing**

Run: `cd frontend && pnpm test -- lib/api/client.test.ts lib/view-models.test.ts hooks/use-chat-stream.test.tsx`

Expected: FAIL on missing modules.

- [ ] **Step 3: Define exact DTO and presentation contracts**

Create `frontend/lib/api/types.ts` with JSON shapes matching backend field names:

```ts
export type MatchStatus = 'scheduled' | 'live' | 'finished' | 'cancelled' | 'postponed' | 'unknown'

export type PlayerDto = { id: string; name: string; country_code: string | null; ranking: number | null }
export type TournamentDto = { id: string; name: string; tour: string | null }
export type SetScoreDto = { number: number; player1_games: number | null; player2_games: number | null }
export type MatchScoreDto = {
  sets_won: [number, number]
  sets: SetScoreDto[]
  points: [string | null, string | null]
  is_tiebreak: boolean
}
export type MatchDto = {
  id: string
  status: MatchStatus
  players: [PlayerDto, PlayerDto]
  tournament: TournamentDto
  scheduled_at: string | null
  round: string | null
  surface: string | null
  indoor: boolean | null
  format: string | null
  live_state: { score: MatchScoreDto | null; server_player_id: string | null } | null
  winner_player_id: string | null
  freshness: {
    provider: string
    source_updated_at: string | null
    observed_at: string
    is_stale: boolean
    age_seconds: number
  }
}
export type StructuredData = { kind: 'matches' | 'match' | 'unsupported'; matches: MatchDto[] }
export type ChatRequest = {
  scope: 'global' | 'match'
  match_id?: string
  messages: Array<{ role: 'user' | 'assistant'; content: string }>
}
export type ChatEvent =
  | { type: 'status'; payload: { stage: string } }
  | { type: 'data'; payload: StructuredData }
  | { type: 'text_delta'; payload: { delta: string } }
  | { type: 'done'; payload: { ok: boolean } }
  | { type: 'error'; payload: { code: string; message: string; details: Record<string, unknown> } }
```

Define these presentation interfaces in `frontend/lib/view-models.ts`:

```ts
export type HomeMatchViewModel = {
  id: string
  href: string
  status: 'upcoming' | 'live' | 'finished' | 'unavailable'
  tournament: string
  round: string
  time: string
  surface: string
  players: [string, string]
  score?: { rows: [{ player: string; sets: string[]; points: string; serving: boolean }, { player: string; sets: string[]; points: string; serving: boolean }] }
  freshnessLabel: string
  isStale: boolean
}

export type MatchViewModel = {
  id: string
  canonicalStatus: MatchStatus
  visualStatus: 'upcoming' | 'live' | 'finished' | 'unavailable'
  tournament: string
  round: string
  surface: string
  scheduledDate: string
  scheduledTime: string
  timezoneLabel: '澳门时间'
  format: string
  indoorLabel: string
  players: [{ id: string; name: string; shortName: string; initials: string; countryCode: string; ranking: number | null }, { id: string; name: string; shortName: string; initials: string; countryCode: string; ranking: number | null }]
  score: MatchScoreDto | null
  serverPlayerId: string | null
  winnerPlayerId: string | null
  freshnessLabel: string
  isStale: boolean
}
```

Both mappers use `/matches/${encodeURIComponent(match.id)}`, localize UTC timestamps with `Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Macau' })`, and preserve null as `暂未提供`. Use initials rather than synthesizing a flag URL from the provider's three-letter country code. Both map canonical `scheduled` to visual `upcoming`, keep live/finished, and map cancelled/postponed/unknown to `unavailable`.

- [ ] **Step 4: Implement browser calls, SSE parser, and chat hook; run tests**

`parseSse(stream)` must create `const decoder = new TextDecoder()`, decode each chunk with `decoder.decode(chunk, { stream: true })`, retain an incomplete buffer, split frames on `/\r?\n\r?\n/`, join repeated `data:` lines, JSON-parse payloads, and ignore comment/blank lines. `streamChat()` POSTs `/api/chat/stream`, throws `ApiError` before parsing a non-OK response, and accepts an `AbortSignal`.

Export these exact client signatures:

```ts
export function getPlayers(query: string, signal?: AbortSignal): Promise<PlayerDto[]>
export function getMatches(status: 'live' | 'upcoming', player?: string, signal?: AbortSignal): Promise<MatchDto[]>
export function getMatch(matchId: string, signal?: AbortSignal): Promise<MatchDto>
export function parseSse(stream: ReadableStream<Uint8Array>): AsyncGenerator<ChatEvent>
export function streamChat(request: ChatRequest, signal?: AbortSignal): AsyncGenerator<ChatEvent>
```

The REST helpers unwrap only the top-level `data` field. They call `/api/players/search`, `/api/matches`, and `/api/matches/${encodeURIComponent(matchId)}` with `cache: 'no-store'`; no helper calls FastAPI directly.

`useChatStream` owns `idle|loading|streaming|success|error`, accumulated text, latest structured data, bounded message history of 12 entries, and one `AbortController`. Starting a request aborts the prior request; unmount aborts without state updates. It never derives a match card from text. Export this exact interface:

```ts
export type ChatViewState = {
  phase: 'idle' | 'loading' | 'streaming' | 'success' | 'error'
  question: string
  text: string
  data: StructuredData | null
  error: { code: string; message: string } | null
}

export function useChatStream(scope: 'global' | 'match', matchId?: string): {
  state: ChatViewState
  send: (prompt: string) => Promise<void>
  cancel: () => void
  reset: () => void
}
```

Run:

```bash
cd frontend
pnpm test -- lib/api/client.test.ts lib/view-models.test.ts hooks/use-chat-stream.test.tsx
pnpm typecheck
```

Expected: PASS, including split-frame and abort behavior.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib frontend/hooks
git commit -m "feat: add typed frontend data client"
```

### Task 13: Connect Home to Real Structured Data Without Redesigning It

**Files:**
- Modify: `frontend/components/home-page.tsx`
- Modify: `frontend/components/home/home-assistant.tsx`
- Modify: `frontend/components/home/home-data.ts`
- Modify: `frontend/components/home/home-match-sections.tsx`
- Modify: `frontend/components/home/home-player-sections.tsx`
- Modify: `frontend/app/page.tsx`
- Create: `frontend/components/home-page.test.tsx`

**Interfaces:**
- Consumes: `getMatches`, `useChatStream`, `HomeMatchViewModel[]`, and optional `initialQuestion`.
- Produces: request-driven Home slate, structured chat cards, manual refresh, and explicit unsupported/loading/empty/stale/error states in the existing layout.

- [ ] **Step 1: Write failing Home integration tests**

Mock only `frontend/lib/api/client.ts` and assert behavior, not implementation details:

```tsx
it('renders structured stream data and never parses the prose into a card', async () => {
  mockStreamChat({
    data: canonicalMatch,
    text: 'Sinner 今晚 20:30 出场。',
  })
  render(<HomePage />)

  await userEvent.type(screen.getByLabelText('继续向 Tennix 提问'), 'Sinner 今晚几点比赛？')
  await userEvent.keyboard('{Enter}')

  expect(await screen.findByText('Sinner 今晚 20:30 出场。')).toBeVisible()
  expect(screen.getByRole('link', { name: /打开比赛/ })).toHaveAttribute('href', `/matches/${canonicalMatch.id}`)
})
```

Also test: initial question triggers exactly once; initial slate calls live and upcoming once with no timers; clicking refresh makes one new pair of calls; loading disables duplicate submit; historical question renders `unsupported` without a card; stale badge is visible; empty lists keep section shells; API failure renders typed retry copy; and no text says sample data is real.

- [ ] **Step 2: Run the Home test to verify it still uses mock routing**

Run: `cd frontend && pnpm test -- components/home-page.test.tsx`

Expected: FAIL because `answerHomeQuestion()` still determines results synchronously.

- [ ] **Step 3: Replace production mock routing with API/view-model state**

Keep the current DOM hierarchy and Tailwind classes in `HomePage`, `HomeHero`, and `HomeAssistant`. Replace `answerHomeQuestion` with `useChatStream('global')`. Build cards only from `chat.state.data.matches.map(toHomeMatch)` and render `chat.state.text` as the article summary. Derive the article label from `chat.state.data.kind`, use the first match's two names as the title, and use fixed labels for no-match/unsupported states.

Load `live` and `upcoming` once in `useEffect` and from an explicit refresh callback:

```ts
const loadSlate = useCallback(async () => {
  setSlateState('loading')
  try {
    const [live, upcoming] = await Promise.all([getMatches('live'), getMatches('upcoming')])
    setSlate({ live: live.map(toHomeMatch), upcoming: upcoming.map(toHomeMatch) })
    setSlateState('success')
  } catch (error) {
    setSlateState('error')
  }
}, [])
```

Do not add `setInterval`, recursive timeout, revalidation timer, or polling library. Keep `homeExampleQueries` and phase marketing labels in `home-data.ts`; remove `answerHomeQuestion`, fake match arrays, fake recent results, and fake status-bearing followed-player data from the production Home path.

- [ ] **Step 4: Preserve unsupported modules and run functional/visual checks**

`FeaturedMatchSection`, `LiveNowSection`, and `UpcomingSection` receive arrays as props; first live match is featured, otherwise first upcoming. Empty arrays render the existing card shell with factual Chinese empty copy. Add an `unavailable` entry to HomeAssistant's status-label map so cancelled/postponed/unknown matches render `状态待确认` rather than indexing an absent key. `RecentResultsCard` keeps its current visual shell but displays `P1 暂不支持历史赛果`. `FollowedPlayersSection` keeps its section position but displays `关注功能将在后续阶段接入`; it must not show fabricated player statuses. Change the footer to `数据由 Tennix 服务提供 · 时间为澳门本地时间`.

Run:

```bash
cd frontend
pnpm test -- components/home-page.test.tsx
pnpm typecheck
pnpm test:e2e --grep prototype
```

Expected: tests PASS or produce only reviewed content-state diffs with unchanged layout geometry. Inspect a diff before changing any tracked snapshot; never update baselines solely to make the command pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/page.tsx frontend/components/home-page.tsx frontend/components/home frontend/e2e
git commit -m "feat: connect Home to tennis data"
```

### Task 14: Add the Internal-ID Match Page and Contextual Chat

**Files:**
- Create: `frontend/app/matches/[matchId]/page.tsx`
- Create: `frontend/components/match/match-preview-data.ts`
- Modify: `frontend/app/match/page.tsx`
- Modify: `frontend/components/match-page.tsx`
- Modify: `frontend/components/match/match-data.ts`
- Modify: `frontend/components/match/match-hero.tsx`
- Modify: `frontend/components/match/match-main.tsx`
- Modify: `frontend/components/match/match-sidebar.tsx`
- Create: `frontend/components/match-page.test.tsx`

**Interfaces:**
- Consumes: internal `matchId`, `getMatch`, `toMatchViewModel`, and `useChatStream('match', matchId)`.
- Produces: production `/matches/[matchId]`, explicit manual refresh, contextual structured answers, and isolated `/match?status=` visual preview.

- [ ] **Step 1: Write failing route and Match Page tests**

Assert the production route uses the internal ID and injects it into chat:

```tsx
it('keeps the current match context out of the user prompt', async () => {
  mockGetMatch(canonicalMatch)
  render(<MatchPage matchId={canonicalMatch.id} />)
  await screen.findByText('Jannik Sinner')

  await userEvent.type(screen.getByLabelText('向 Tennix 询问本场比赛'), '谁在发球？')
  await userEvent.keyboard('{Enter}')

  expect(mockStreamChat).toHaveBeenCalledWith(expect.objectContaining({
    scope: 'match',
    match_id: canonicalMatch.id,
    messages: expect.arrayContaining([{ role: 'user', content: '谁在发球？' }]),
  }), expect.anything())
})
```

Also test upcoming/live/finished hero mapping; server highlighting from `server_player_id`; missing round/surface/server copy; stale indicator; explicit refresh; 404 state; provider error retry; stats/momentum always show P2-unavailable on the production route; and `/match?status=live` still renders the original prototype preview.

- [ ] **Step 2: Run the Match test to verify production route is missing**

Run: `cd frontend && pnpm test -- components/match-page.test.tsx`

Expected: FAIL because `MatchPage` accepts only prototype status.

- [ ] **Step 3: Isolate preview fixtures and make presentational components prop-driven**

Move all static players, `matchMeta`, score, statistics, momentum, and point arrays from `match-data.ts` to `match-preview-data.ts`. Keep only shared display enums and labels in `match-data.ts`. Add `buildPreviewMatch(status)` so `/match?status=` passes a `MatchViewModel` plus `preview=true` to the same component tree.

Change the components to accept the view model instead of importing fixtures:

```ts
type MatchPageProps = { matchId: string } | { previewMatch: MatchViewModel }
type MatchHeroProps = { match: MatchViewModel; highlight: MatchHighlight; onAsk: () => void; onRefresh?: () => void }
type MatchMainProps = { match: MatchViewModel; preview: boolean; highlight: MatchHighlight; onPromptSelect: (prompt: string) => void }
type MatchSidebarProps = { match: MatchViewModel; chat: ChatViewState; onSubmit: (prompt: string) => void }
```

Production stats, point, and momentum cards use `FutureModule` with `P2 数据暂不可用`; only `preview=true` may render existing sample statistics and momentum. Remove every hard-coded winner, score, tournament, time, and server sentence from the production branch.

- [ ] **Step 4: Implement the dynamic route, data state, contextual stream, and verify visuals**

`frontend/app/matches/[matchId]/page.tsx` awaits `params: Promise<{matchId:string}>` and renders `<MatchPage matchId={matchId} />`. The client loads once on mount and again only from the refresh action. Its chat hook always sends Match scope and the current internal ID; `data` events update only structured result/highlight, while `text_delta` updates assistant prose.

Run:

```bash
cd frontend
pnpm test -- components/match-page.test.tsx
pnpm typecheck
pnpm build
pnpm test:e2e --grep prototype
```

Expected: unit/type/build PASS, the preview screenshots remain pixel-stable, and the production path contains no prototype status toggle or fabricated P2 statistic.

- [ ] **Step 5: Commit**

```bash
git add frontend/app frontend/components/match-page.tsx frontend/components/match
git commit -m "feat: add contextual match experience"
```

### Task 15: Complete Browser E2E, Live Gates, and the P1 Runbook

**Files:**
- Modify: `frontend/playwright.config.ts`
- Create: `frontend/e2e/p1-flow.spec.ts`
- Create: `frontend/e2e/p1.visual.spec.ts`
- Create: `frontend/e2e/llm-live.spec.ts`
- Create: `frontend/e2e/end-to-end-live.spec.ts`
- Create: `backend/tests/live/test_llm_live.py`
- Create: `backend/tests/live/test_provider_live.py`
- Create: `backend/tests/live/test_end_to_end_live.py`
- Create: `backend/tests/test_p1_acceptance.py`
- Create: `docs/runbooks/p1-local.md`

**Interfaces:**
- Consumes: completed fake-backed P1, optional Tennix LLM credentials, optional LiveTennisAPI key, and both approved viewports.
- Produces: deterministic acceptance gates, opt-in real integration evidence, failure artifacts, and exact local operating commands.

- [ ] **Step 1: Write deterministic P1 acceptance and browser-flow tests**

Parameterize backend acceptance over all supported intents and the historical rejection:

```python
@pytest.mark.parametrize(
    ("scope", "question", "expected_tool"),
    [
        ("global", "今晚 Sinner 几点打？", "find_player_matches"),
        ("global", "Alcaraz 今天有比赛吗？", "find_player_matches"),
        ("global", "Djokovic 下一场对谁？", "find_player_matches"),
        ("match", "这是什么赛事？", "get_match"),
        ("match", "第几轮？", "get_match"),
        ("match", "什么场地？", "get_match"),
        ("match", "比赛开始了吗？", "get_match"),
        ("match", "现在比分多少？", "get_match"),
        ("match", "谁在发球？", "get_match"),
    ],
)
async def test_supported_acceptance_intents(
    scope: str,
    question: str,
    expected_tool: str,
    acceptance_harness,
) -> None:
    result = await acceptance_harness.ask(
        question,
        scope=scope,
        match_id=acceptance_harness.live_match_id if scope == "match" else None,
    )
    assert result.executed_tool_names == [expected_tool]
    assert result.data_events[0]["matches"]
    assert result.terminal_event == "done"
```

Define `acceptance_harness` in the same test file around the real `ChatOrchestrator` with `FakeTennisProvider`, a recording `BusinessTools`, and `FakeChatModel`:

```python
@dataclass
class AcceptanceResult:
    executed_tool_names: list[str]
    data_events: list[dict[str, object]]
    terminal_event: str


class RecordingBusinessTools(BusinessTools):
    def __init__(self, service: TennisService) -> None:
        super().__init__(service)
        self.executed: list[str] = []

    async def execute(self, name: str, arguments: dict[str, object], context: ChatContext):
        self.executed.append(name)
        return await super().execute(name, arguments, context)


class AcceptanceHarness:
    def __init__(self, orchestrator: ChatOrchestrator, tools: RecordingBusinessTools, live_match_id: str) -> None:
        self.orchestrator = orchestrator
        self.tools = tools
        self.live_match_id = live_match_id

    async def ask(self, question: str, scope: str, match_id: str | None) -> AcceptanceResult:
        self.tools.executed.clear()
        request = ChatRequest(
            scope=scope,
            match_id=match_id,
            messages=[ChatMessage(role="user", content=question)],
        )
        events = [event async for event in self.orchestrator.stream(request)]
        data_events = [event.payload for event in events if event.type is ChatEventType.DATA]
        return AcceptanceResult(self.tools.executed.copy(), data_events, events[-1].type.value)
```

The historical row asserts `kind == "unsupported"`, zero provider calls, and zero model calls.

`p1-flow.spec.ts` covers Home query → structured card → Open Match → contextual “谁在发球？” → explicit refresh, plus typed provider error and unsupported history. Assertions target roles/text/test IDs, not screenshots.

- [ ] **Step 2: Configure two local web servers and verify initial failures**

Extend Playwright `webServer` to an array. Define the backend environment so real integrations require explicit E2E flags, then start FastAPI from `../backend` on port 8000 and Next.js on port 3100:

```ts
const realProvider = process.env.TENNIX_E2E_REAL_PROVIDER === '1'
const realLlm = process.env.TENNIX_E2E_REAL_LLM === '1'
const backendEnv = {
  ...process.env,
  TENNIX_PROVIDER_MODE: realProvider ? 'live' : 'fake',
  TENNIX_LLM_MODE: realLlm ? 'openai_compatible' : 'fake',
  ...(realProvider ? {} : { TENNIX_FIXED_NOW: '2026-09-08T10:00:00Z' }),
}

webServer: [
  {
    cwd: '../backend',
    command: 'uv run uvicorn app.main:app --host 127.0.0.1 --port 8000',
    url: 'http://127.0.0.1:8000/api/v1/health',
    env: backendEnv,
  },
  {
    command: 'pnpm dev --hostname 127.0.0.1 --port 3100',
    url: 'http://127.0.0.1:3100',
    env: { ...process.env, TENNIX_BACKEND_URL: 'http://127.0.0.1:8000' },
  },
]
```

Run: `cd frontend && pnpm test:e2e --grep "P1 flow"`

Expected: FAIL until selectors, fake runtime defaults, and production screenshots are finalized.

- [ ] **Step 3: Add opt-in real integration tests with structural assertions**

Each live test calls `pytest.skip()` when its required variables are absent. Requirements and assertions are exact:

- `llm_live`: `TENNIX_LLM_API_KEY` and `TENNIX_LLM_BASE_URL`; use fake tennis data; assert Qwen selects the expected tool/enum for three acceptance prompts and generated prose includes the structured opponent or time, never exact sentence equality.
- `provider_live`: `TENNIX_LIVETENNIS_API_KEY`; call player search plus either live or upcoming based on availability; assert IDs use `ply_`/`mat_`, timestamps are aware UTC, payload has no external ID, and skip with a clear reason only when both current lists are honestly empty.
- `end_to_end_live`: all three credentials/modes; ask one player-current/next prompt; assert a structured result or an honest empty result, a terminal event, and no provider field name in output.
- `llm-live.spec.ts`: run only when `TENNIX_E2E_REAL_LLM=1`; provider stays fake; submit one Home prompt and assert a structured card plus non-empty streamed prose.
- `end-to-end-live.spec.ts`: run only when both E2E flags are `1`; ask for current live matches and accept either trusted cards or the explicit honest-empty state, but always require non-empty model prose and a terminal stream state.

Never log keys, full request headers, or the DEUCE `.env` path/value in artifacts.

- [ ] **Step 4: Finish visual coverage, run all gates, and write the runbook**

`p1.visual.spec.ts` captures Home initial/result/error, production Match upcoming/live/P2-unavailable states, and the isolated preview's finished state at both existing projects. Review diffs against Task 1 before accepting new snapshots; preserve layout geometry and document only unavoidable data-copy changes in `docs/runbooks/p1-local.md`. The unit test from Task 14 remains the deterministic production finished-state proof because Free current listings do not provide an independently discoverable finished fixture.

The runbook must contain these exact commands and mode meanings:

```bash
cd backend && cp .env.example .env
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && cp .env.example .env.local
cd frontend && pnpm dev --port 3100
cd backend && uv run pytest -m "not llm_live and not provider_live and not end_to_end_live"
cd frontend && pnpm test && pnpm typecheck && pnpm build && pnpm test:e2e
cd backend && uv run pytest -m llm_live
cd backend && uv run pytest -m provider_live
cd backend && uv run pytest -m end_to_end_live
cd frontend && TENNIX_E2E_REAL_LLM=1 pnpm test:e2e llm-live.spec.ts
cd frontend && TENNIX_E2E_REAL_PROVIDER=1 TENNIX_E2E_REAL_LLM=1 pnpm test:e2e end-to-end-live.spec.ts
```

Run the deterministic gate fresh:

```bash
cd backend
uv run pytest -m "not llm_live and not provider_live and not end_to_end_live"
cd ../frontend
pnpm test
pnpm typecheck
pnpm build
pnpm test:e2e
```

Expected: all deterministic commands PASS. Run live gates only when credentials and provider quota are available; record skip/pass output without secrets. Confirm `git grep -nE 'event_key|event_first_player|score\[0\]\[1\]' -- ':!docs'` has no business/UI-code match.

- [ ] **Step 5: Commit the completed P1 acceptance layer**

```bash
git add backend/tests frontend/e2e frontend/playwright.config.ts docs/runbooks/p1-local.md
git commit -m "test: complete P1 acceptance coverage"
```

## Final P1 Completion Gate

Before claiming P1 complete, run every deterministic command from Task 15 again from a clean working tree, then run the available live markers. Inspect Playwright failure artifacts and both viewport baselines. Confirm all of the following manually:

- no browser bundle contains `TENNIX_BACKEND_URL`, LLM credentials, or provider credentials;
- no automatic timer or polling dependency exists;
- no PostgreSQL, Redis, auth, history, statistics, point-event, or Polymarket implementation entered P1;
- Home cards and Match facts originate from structured service data;
- a provider failure never yields a model-authored tennis fact;
- an LLM failure after successful lookup still leaves the structured result visible;
- `/match?status=` is clearly a preview and `/matches/[matchId]` is the production path;
- desktop and mobile visuals still follow the approved prototype.
