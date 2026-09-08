# TennixAI Product Roadmap Design

**Status:** Approved roadmap specification
**Date:** 2026-09-08
**Planning horizon:** Detailed P1 implementation design with gated P2 and P3 milestones
**Delivery target:** Local, single-user, end-to-end product slice

## 1. Objective

TennixAI will become a tennis data and intelligence platform whose conversational interface is one consumer of trusted structured data. The first release must prove the complete path from a user's current-match question to real provider data, canonical models, business services, structured UI, and an LLM explanation without binding the product to LiveTennisAPI fields or model-generated facts.

The roadmap optimizes for a narrow, verifiable P1. It intentionally defers infrastructure and capabilities that do not help prove that path.

## 2. Architectural invariants

The durable dependency direction is:

```text
Provider adapter
      ↓
Canonical domain model
      ↓
TennisService
      ↓
REST API + business tools
      ↓
Next.js UI + conversational interface
```

These rules apply across all phases:

1. Vendor payloads end at the provider adapter. Business and UI code never consume vendor field names.
2. The LLM calls business tools, never arbitrary provider HTTP endpoints.
3. `TennisService` is the common source for REST and chat-tool results.
4. Structured facts remain separate from generated prose. UI cards and actions use trusted service output.
5. Missing, unsupported, stale, and zero are distinct states with provenance and timestamps.
6. TennixAI owns internal identities; external identifiers are provider-scoped mappings.
7. New abstractions and infrastructure enter only when a phase has a concrete need and an acceptance test.

## 3. P1 scope and non-goals

P1 answers current and upcoming match questions:

- tonight's, today's, and a player's next match
- start time in the user's product timezone
- opponent, tournament, round, and surface when available
- scheduled, live, and terminal status
- current score and server when reported by the provider
- navigation from a structured Home result into a contextual Match Page

P1 explicitly excludes:

- arbitrary historical-result lookup and the question “昨天 Sinner 赢了吗？”
- PostgreSQL, Redis, multi-worker deployment, and automatic polling
- account authentication and durable chat history
- match statistics, point-by-point data, and momentum computation
- LangGraph, vector search, event buses, and microservices
- Polymarket integration, prediction, paper trading, and order execution

If a user asks for unsupported historical data, the system returns an explicit `unsupported` result. It does not infer, scrape, or fabricate an answer, and it does not build an observed-history database solely to work around the Free plan.

## 4. P1 runtime topology

```text
Browser Client Components
          │ same-origin /api/*
          ↓
Next.js Route Handlers
          │ thin HTTP/SSE proxy
          ↓
FastAPI
   ├── deterministic REST endpoints
   ├── chat orchestrator and business tools
   ├── TennisService
   ├── process-local repository and TTL cache
   └── LiveTennisProvider → LiveTennisAPI Free

Server Components ───────────────→ FastAPI (server-side direct call allowed)
```

Next.js Route Handlers preserve status codes, headers needed by the contract, and SSE streaming. They contain no tennis business logic. `TENNIX_BACKEND_URL` is server-only, so the browser does not know the FastAPI address. Provider and LLM credentials exist only in the FastAPI environment.

P1 assumes one local FastAPI process. Process restart clears cache, chat state, and internal-to-provider ID mappings; an old match URL may stop resolving. This is acceptable for current/upcoming local validation and is the explicit reason stable persistence moves to P2.

## 5. Canonical domain and capability semantics

P1 defines only:

- `Player`
- `Tournament`
- `Match`
- `MatchScore`
- `SetScore`
- `LiveMatchState`
- `DataFreshness`

Match lifecycle values are `scheduled`, `live`, `finished`, `cancelled`, `postponed`, and `unknown`.

Canonical values carry enough metadata to distinguish:

- known value
- supported but not yet available
- unsupported capability
- source provider and source timestamp
- TennixAI observation time
- fresh versus stale data

Round, surface, server, and other optional fields remain absent when the provider does not report them. No upper layer derives them without an explicit, tested rule and provenance.

P1's process-local repository creates TennixAI match IDs and holds the mapping to LiveTennisAPI IDs. Provider IDs never appear in public routes or become domain primary keys.

## 6. Provider and service design

The P1 provider contract is limited to:

```python
class TennisDataProvider:
    get_live_matches()
    get_fixtures()
    search_players()
    get_match()
    get_score()
```

`LiveTennisProvider` owns authentication, HTTP behavior, vendor DTO validation, player-major score parsing, UTC timestamps, server normalization, lifecycle mapping, nullable fields, external-ID extraction, and forward-compatible ignoring of unknown fields.

`TennisService` owns player resolution, Asia/Macau date semantics, filtering, current/upcoming selection, internal identity, cache policy, and stable error translation. It never exposes provider DTOs.

The provider's 100-request daily Free quota makes request behavior part of correctness. P1 reads only on initial page load, explicit in-app refresh, or a user query. There is no browser or backend timer-based polling.

The process-local cache policy begins with:

| Data | Fresh TTL | Maximum stale fallback |
|---|---:|---:|
| Live list | 60 seconds | 5 minutes |
| Live match detail | 60 seconds | 5 minutes |
| Upcoming matches | 10 minutes | 30 minutes |
| Player search | 1 hour | none |
| Empty / not found | 30 seconds | none |

The cache is capped at 256 entries and coalesces concurrent identical in-flight requests. Stale fallback is clearly marked in `DataFreshness`. A `429` preserves `Retry-After` information through the service/API boundary.

## 7. Time and identity rules

Provider timestamps are parsed and retained as UTC. Product-relative language such as `today`, `tonight`, and `next` is interpreted in `Asia/Macau`, and the UI displays that local timezone. Timezone conversion lives in the service/domain boundary, not in prompts or visual components.

`next` means the earliest non-terminal match after the current time. `today` uses the local calendar day. `tonight` means the active or next local night window from 18:00 through 05:59 the following day: before 06:00 it uses the window that began the previous day; from 06:00 through 17:59 it uses the window beginning that evening; from 18:00 onward it uses the window already in progress. Match selection excludes fixtures whose canonical start time has passed unless their lifecycle is live. These boundaries are service rules with clock-controlled tests, not prompt instructions left to the LLM.

If player resolution yields multiple plausible players, the service returns `ambiguous_player` and the chat layer asks for clarification. It does not silently choose one.

## 8. Deterministic API contract

FastAPI routes:

- `GET /api/v1/health`
- `GET /api/v1/players/search?q=...`
- `GET /api/v1/matches?status=live|upcoming&player=...`
- `GET /api/v1/matches/{match_id}`
- `POST /api/v1/chat/stream`

Next.js proxy routes:

- `/api/players/search`
- `/api/matches`
- `/api/matches/[matchId]`
- `/api/chat/stream`

Stable application error codes are:

- `invalid_request`
- `ambiguous_player`
- `not_found`
- `unsupported`
- `provider_unavailable`
- `rate_limited`
- `llm_unavailable`
- `internal_error`

HTTP statuses remain meaningful, while bodies use one typed error envelope. Each request carries a request ID for browser-to-backend diagnostics without introducing a full observability platform.

## 9. LLM and chat design

P1 uses the OpenAI Python SDK against an OpenAI-compatible Chat Completions endpoint with native function calling. The pinned initial model is `qwen3.8-max-0902`.

Configuration is TennixAI-owned:

- `TENNIX_LLM_API_KEY`
- `TENNIX_LLM_BASE_URL`
- `TENNIX_LLM_MODEL`
- `TENNIX_BACKEND_URL` for the Next.js server

The separate DEUCE project supplied only a configuration pattern. TennixAI never imports its `.env`, and no secret value is copied into documentation or version control. P1 needs neither a vision model nor LangGraph.

The LLM receives exactly three business tools:

```text
find_player_matches(player_name, time_scope: today | tonight | next)
get_live_matches(player_name: string | null)
get_match(match_id)
```

Arguments are validated with Pydantic, and one user turn may use at most two tool-call rounds. The tool layer returns canonical data only. The model may summarize those facts but may not construct trusted cards, links, identifiers, or status values.

Chat is server-stateless. The browser keeps a bounded recent message history in React state and sends it with each request. Home uses `scope=global`; Match Page uses `scope=match` plus the internal `match_id`. Browser refresh or close may discard conversation state.

The SSE protocol uses:

- `status`: progress state such as tool selection or data lookup
- `data`: trusted structured service result
- `text_delta`: generated prose fragment
- `done`: successful terminal event
- `error`: typed terminal failure

If service data succeeds and the LLM fails, the stream still returns `data` plus fixed fallback copy and a terminal result that allows the UI to remain useful. If the provider fails, the model cannot fill the gap from memory. A valid stale value may be returned only within the documented cache bounds and with freshness visible.

## 10. Frontend integration and design fidelity

The existing v0 prototype is the approved visual specification. P1 is an incremental data integration, not a redesign.

The frontend work will:

1. capture visual baselines before component changes;
2. extract static fixtures and mock query routing from production paths;
3. add typed API DTOs, an API client, and DTO-to-view-model mappers;
4. feed existing Home and Match components through props/view models;
5. preserve upcoming, live, and finished visual states and responsive behavior;
6. introduce `/matches/[matchId]` as the production match route;
7. retain `/match?status=...` only temporarily as a deliberate visual-preview route;
8. delete production mock routing after the real P1 path passes acceptance.

No unrelated shadcn/ui migration, component-system rewrite, or stylistic cleanup belongs in P1.

Playwright screenshot baselines cover:

- desktop: `1440×1000`
- mobile: `390×844`
- Home initial, query/result, and error states
- Match upcoming, live, finished, contextual answer, and unavailable-data states

Intentional visual changes require explicit baseline review. Screenshot updates are never used to mask a regression.

## 11. Verification design

The test strategy separates deterministic correctness from costly and variable live integrations.

Backend unit and integration tests use fake providers and a fake LLM for domain parsing, service filtering, timezone boundaries, cache behavior, ambiguity, error translation, tool schemas, two-round limits, and SSE ordering.

Opt-in pytest suites use:

- `pytest -m llm_live`: real Qwen and fake tennis data
- `pytest -m provider_live`: fake LLM and real LiveTennisAPI
- `pytest -m end_to_end_live`: real Qwen and real LiveTennisAPI

Real-model tests assert tool choice, validated arguments, and agreement with canonical facts. They do not assert exact generated prose. The configured model is pinned for reproducibility.

Playwright uses Chromium in P1:

- default full-browser E2E uses controlled fake backend/LLM responses;
- one browser smoke path exercises the real LLM with controlled tennis data;
- the fully real provider-plus-LLM path is a manual acceptance gate because live schedules and provider quota are variable;
- failures retain screenshot, trace, and browser-console artifacts;
- desktop and mobile visual regression protects the approved prototype.

## 12. P1 execution roadmap

### P1.0 — Design freeze

Deliverables:

- approved architecture and roadmap specification
- inventory of existing Home and Match states
- desktop and mobile screenshot baselines
- documented visual exceptions, if any

Exit gate: all current target states have accepted baselines, and implementation scope contains no unresolved product decision.

### P1.1 — Foundation

Deliverables:

- FastAPI application skeleton and typed settings
- safe `.env.example` files with no secrets
- health endpoint and request-ID middleware
- Next.js thin Route Handler proxy, including SSE pass-through
- backend pytest, frontend unit-test, and Playwright test harnesses

Exit gate: the browser reaches FastAPI through the same-origin proxy; health and streaming smoke tests pass; no credential is exposed client-side.

### P1.2 — Domain and provider

Deliverables:

- minimal P1 canonical models and lifecycle/freshness semantics
- `TennisDataProvider` protocol
- deterministic fake provider and recorded safe payload fixtures
- `LiveTennisProvider` with vendor parsing and typed failures
- process-local internal-ID repository

Exit gate: provider contract tests prove both fake and live adapters produce the same canonical shapes, unknown vendor fields do not break parsing, and provider IDs do not leak into public DTOs.

### P1.3 — Service and REST

Deliverables:

- `TennisService` player resolution and match selection
- Asia/Macau `today`, `tonight`, and `next` rules
- TTL cache, bounded stale fallback, request coalescing, and quota errors
- deterministic player, match-list, and match-detail endpoints

Exit gate: all P1 factual questions can be answered through REST without an LLM; timezone edge cases, ambiguity, unavailable fields, stale data, and `429` handling have deterministic tests.

### P1.4 — Real frontend data

Deliverables:

- typed frontend API client and view-model mapping
- Home query/results driven by backend data
- dynamic `/matches/[matchId]` page driven by canonical match data
- explicit loading, empty, unsupported, stale, and error states
- manual refresh action without automatic polling

Exit gate: Home-to-Match navigation works with internal IDs and real structured responses while approved desktop/mobile screenshots remain within reviewed visual tolerance.

### P1.5 — Conversational path

Deliverables:

- three Pydantic-validated business tools
- OpenAI-compatible Qwen client and bounded tool loop
- global and match-scoped stateless prompts
- typed SSE event stream and browser stream consumer
- structured-data-first fallback behavior

Exit gate: chat uses the same service facts as REST, cards never depend on parsed prose, LLM failure leaves useful structured results, and provider failure never produces invented tennis facts.

### P1.6 — Acceptance and hardening

Deliverables:

- deterministic acceptance suite for all supported questions
- live LLM, live provider, and combined opt-in suites
- Playwright functional and visual suites at both approved viewports
- failure artifacts and operator runbook
- explicit unsupported test for historical questions

Exit gate: default unit/integration/E2E suites pass; live gates pass within provider availability and quota; the product completes the Home query → structured card → Match Page → contextual query flow; no P1 non-goal has entered the implementation.

## 13. P1 acceptance matrix

| User intent | Required result |
|---|---|
| 今晚 Sinner 几点打？ | Resolved player, Macau-local start time, structured match card |
| Alcaraz 今天有比赛吗？ | Deterministic yes/no or ambiguity, with matching canonical data |
| Djokovic 下一场对谁？ | Earliest non-terminal match and opponent |
| 这是什么赛事？ | Match-context tournament or explicit unavailable state |
| 第几轮？ | Match-context round or explicit unavailable state |
| 什么场地？ | Match-context surface or explicit unavailable state |
| 比赛开始了吗？ | Canonical lifecycle status |
| 现在比分多少？ | Canonical score with freshness |
| 谁在发球？ | Canonical server or explicit unavailable state |
| 昨天 Sinner 赢了吗？ | Typed `unsupported`; no fabricated result |

Every supported row is checked through deterministic service/API output and the LLM tool path. A fluent answer cannot compensate for wrong structured data, and a model outage cannot hide a successful structured lookup.

## 14. P2 milestone: Live Match Intelligence

P2 begins only after P1's acceptance gates pass. Its purpose is richer live state and durable multi-process operation.

Planned capabilities:

- PostgreSQL for stable internal identities, provider mappings, observations, and snapshot history
- Redis for shared cache, provider-quota accounting, coordinated polling locks, and event distribution
- controlled polling based on match lifecycle and provider quota
- `ApiTennisProvider` with explicit timezone and empty-array normalization
- provider capability metadata and compatibility tests proving upper layers survive a provider swap
- `MatchStatistics`, `PointEvent`, and derived momentum models
- live Match Page modules fed by real statistics and point events
- server-to-browser live updates behind existing service contracts

Entry gate:

- P1 has a stable provider contract and canonical response fixtures
- the need for cross-restart IDs and coordinated refresh is demonstrated
- API-Tennis trial credentials and quota behavior are verified
- storage schemas and rollback strategy receive a separate approved design

Exit gate:

- the same service behavior works against LiveTennisAPI and API-Tennis where capabilities overlap
- statistics and point events show source timestamps and availability correctly
- polling respects lifecycle, quotas, locks, and backoff across multiple workers
- Match Page explains live progression using canonical data, not vendor fields

Historical-result support may enter P2 only with a deliberate entitlement and retention decision; it is not implied merely by adding PostgreSQL.

## 15. P3 milestone: Market and Decision Support

P3 begins after live tennis state is trustworthy and observable. It adds analysis, not autonomous execution.

Planned capabilities:

- Polymarket Gamma discovery and CLOB market/orderbook ingestion
- explicit tennis-match-to-market mapping with manual confirmation for ambiguity
- `MarketState` preserving bid, ask, midpoint, last trade, spread, liquidity, status, and timestamp
- feature engine and versioned prediction output
- decision engine comparing model probability with an explicit executable-price and cost assumption
- confidence, edge, recommendation, and abstention semantics
- paper-trading ledger, reproducible audit trail, evaluation dashboard, and Match Page market modules

Entry gate:

- P2 match state and timestamps meet freshness targets
- mapping quality can be measured and ambiguous markets can be blocked
- prediction evaluation methodology and data-leakage controls have an approved design
- paper-trading risk rules are specified before recommendations are surfaced

Exit gate:

- every recommendation is reproducible from versioned features, model, market snapshot, and decision rule
- paper results include calibration, expected value, slippage assumptions, and abstentions
- stale, closed, unmapped, or illiquid markets cannot produce actionable recommendations
- no wallet credential or order-placement path exists in the P3 product slice

Automated execution is a separate optional phase. It requires a validated paper-trading threshold, position and loss limits, isolated signing keys, geographic eligibility checks, idempotency, a kill switch, auditability, and separate explicit approval.

## 16. Risks and controls

| Risk | P1 control | Later transition |
|---|---|---|
| Free provider quota | request-driven reads, TTL cache, coalescing, typed `429` | Redis quota coordination and controlled polling |
| Provider schema drift | strict DTO boundary, ignore additive fields, contract fixtures | multi-provider compatibility suite |
| LLM hallucination | structured tools, two-round limit, data/prose separation | model evals and expanded tool-policy tests |
| Process restart loses IDs | accepted local-P1 constraint | PostgreSQL identity mappings |
| Stale live score | short TTL, bounded marked fallback, manual refresh | coordinated polling and event delivery |
| Prototype visual regression | pre-change screenshots and dual-viewport Playwright tests | reviewed baseline changes only |
| Live-test variability | fake defaults and opt-in real integrations | scheduled reliability monitoring after infrastructure exists |
| Scope expansion | phase non-goals and exit gates | separate approved designs for P2/P3 |

## 17. Decision log

- LiveTennisAPI Free is the P1 provider; arbitrary history is not implemented.
- P1 has no PostgreSQL, Redis, automatic polling, or authentication.
- A process-local repository and bounded TTL cache are sufficient for the local single-user slice.
- Default product timezone is `Asia/Macau`; canonical timestamps are UTC.
- Browser traffic uses a Next.js Route Handler proxy to FastAPI.
- Chat state lives only in the browser for P1.
- Qwen `qwen3.8-max-0902` is called through an OpenAI-compatible endpoint with native tool calling.
- The LLM has exactly three business tools and at most two tool-call rounds.
- The existing v0 UI is the visual source of truth; integration is incremental.
- Playwright Chromium E2E and desktop/mobile visual regression are P1 requirements.
- Real LLM calls are allowed in opt-in backend and browser smoke tests; deterministic fake-backed tests remain the default gate.
- P2 adds PostgreSQL, Redis, coordinated polling, and API-Tennis live intelligence.
- P3 adds Polymarket market state and paper decision support, not automated orders.
