# TennixAI Product and Architecture Context

**Status:** Product and architecture baseline
**Last verified:** 2026-09-08
**Purpose:** Record the stable product direction, current prototype state, verified provider constraints, and engineering principles that future designs and implementation plans must preserve.

## 1. Product thesis

TennixAI is not a general-purpose tennis chatbot. It is a structured tennis data and intelligence product with a conversational interface.

The product's source of truth is the data and service layer. The LLM is responsible for intent understanding, business-tool selection, contextual explanation, and response composition. It must not invent tennis facts, depend on vendor response fields, or call third-party APIs directly.

The stable system center is:

```text
Provider
   ↓
Canonical Domain Model
   ↓
TennisService
   ↓
Feature / Prediction / Decision
   ↓
Chat + UI
```

Data providers, prediction models, LLMs, and frontend implementations may change. Domain semantics, service contracts, provider boundaries, and decision semantics should remain stable.

## 2. Product surfaces

### Home Page

Home is the global discovery surface:

- global player and match search
- schedules and upcoming matches
- live matches
- followed players
- recent results when a future provider or persistence layer supports them
- navigation into a specific match
- global conversational queries

A typical Home answer combines:

```text
Short answer
+
Structured match card
+
Open Match action
```

### Match Page

Match Page is the investigation surface for one match:

- current status and score
- server and match state
- statistics and point-by-point data when available
- momentum and derived insights
- market state
- prediction and decision support
- contextual conversation scoped to the current match

The server supplies an internal `match_id` to Match Page tools. Users should not need to restate which match they are discussing.

## 3. Product phases

### P1: Match information assistant

P1 proves the real end-to-end data path:

```text
User Query
→ LLM / Tool Calling
→ TennisService
→ TennisDataProvider
→ LiveTennisProvider
→ LiveTennisAPI
→ Canonical Model
→ Structured Response
→ UI / Chat
```

Required P1 information:

- today's, tonight's, and next matches
- scheduled start time
- opponent
- tournament
- round
- surface
- lifecycle status
- current score
- current server when reported by the provider

Arbitrary historical-result lookup is explicitly outside P1. When a user asks a historical question that LiveTennisAPI Free cannot answer, TennixAI returns a structured `unsupported` response and never guesses.

### P2: Live match intelligence

P2 adds higher-granularity live information, initially through API-Tennis trial access:

- first-serve percentage
- first-serve points won
- second-serve points won
- aces
- double faults
- break points
- point-by-point events
- momentum and live progression
- finer live-state interpretation

The objective is to explain how a match is developing, not merely report the current score.

### P3: Market and decision support

P3 connects tennis state to Polymarket state:

```text
Tennis Live Data                Polymarket
      ↓                              ↓
Match State                    Market State
      ↓                              │
Feature Engine                       │
      ↓                              │
Prediction Model                     │
      └──────────────┬───────────────┘
                     ↓
               Decision Engine
                     ↓
        Edge / Confidence / Recommendation
```

P3 begins with market observation, paper trading, and decision support. Automated order placement is a later, optional capability and is not part of the initial P3 scope.

## 4. Current repository state

The repository currently contains a v0-generated Next.js frontend prototype.

The prototype already demonstrates:

- Home global-query flow
- structured match cards
- Open Match navigation
- Match Page
- upcoming, live, and finished visual states
- contextual Match Page questions
- placeholder market and intelligence modules

Important current locations:

- `frontend/components/home-page.tsx`: Home state and page composition
- `frontend/components/home/home-hero.tsx`: Home search and example queries
- `frontend/components/home/home-assistant.tsx`: structured assistant result card and interaction
- `frontend/components/home/home-data.ts`: static fixtures, players, results, and mock query routing
- `frontend/app/match/page.tsx`: prototype match-state query validation
- `frontend/components/match-page.tsx`: contextual match question routing and UI state
- `frontend/components/match/match-data.ts`: static match, score, statistics, momentum, and point data
- `frontend/components/match/match-sidebar.tsx`: contextual assistant and future market boundary

The prototype currently uses a query parameter such as `?status=live` to select a visual state. Real implementation should route by internal match identity, for example:

```text
/matches/{internal_match_id}
```

Match status must come from canonical backend data. The status query parameter may remain only as an explicit development-preview mechanism.

There is currently no FastAPI backend, provider adapter, canonical domain package, database layer, or real LLM tool integration.

## 5. Provider architecture

Business code must never depend on vendor field names such as:

```text
event_first_player
event_key
score[0][1]
```

Vendor payloads are parsed into internal domain models at the provider boundary:

```text
LiveTennisAPI payload
      ↓
LiveTennisProvider DTO parsing
      ↓
Canonical Domain Model
      ↑
ApiTennisProvider DTO parsing
      ↑
API-Tennis payload
```

The provider interface exposes business-relevant data capabilities rather than arbitrary HTTP calls. P1 keeps this interface deliberately small:

```python
class TennisDataProvider:
    get_live_matches()
    get_fixtures()
    search_players()
    get_match()
    get_score()
```

P2 extends the capability surface only when the richer provider is introduced:

```python
class LiveIntelligenceProvider(TennisDataProvider):
    # P2 capabilities
    get_statistics()
    get_point_events()
```

P1 does not expose statistics or point-events methods. Canonical responses still represent unavailable optional fields explicitly, without requiring upper layers to understand provider plans or field names.

## 6. Canonical domain model

P1 domain vocabulary is limited to:

- `Player`
- `Tournament`
- `Match`
- `MatchScore`
- `SetScore`
- `LiveMatchState`
- `DataFreshness`

Later phases add domain concepts when their capabilities become real:

- P2: `MatchStatistics`, `PointEvent`, and derived momentum
- P3: `Prediction`, `MarketState`, and `Decision`

The model must distinguish at least these lifecycle states:

```text
scheduled
live
finished
cancelled
postponed
unknown
```

Missing data is not equivalent to zero. Canonical responses must be able to communicate:

- the value, when known
- whether the capability is supported
- whether data is not yet available
- the provider and source timestamp
- when TennixAI observed the value

Fields such as server, round, surface, detailed statistics, and point events may legitimately be unavailable. The application must not infer them without an explicit derivation rule and provenance.

## 7. Identity design

Third-party identifiers are provider-scoped and must not be used as primary keys.

Matches, players, and tournaments use TennixAI-owned internal IDs plus external-identifier mappings:

```text
matches
-------
id  ← internal id

match_external_ids
------------------
match_id
provider
external_id
```

The same pattern applies to players, tournaments, and markets once persistence is introduced.

P1 has no database. It uses process-local internal IDs and provider-ID mappings because its scope is current and upcoming data in a single local process. A backend restart may invalidate an old match link; that is an accepted P1 constraint. PostgreSQL becomes mandatory in P2, when stable cross-restart identity, provider migration, observed snapshots, and historical continuity are required.

Provider IDs may be stable within one provider and lifecycle without being compatible with another provider. Polymarket also exposes multiple identity forms, including event ID, market ID, condition ID, slug, and CLOB token IDs. These identities must be preserved without becoming domain primary keys.

## 8. Chat and business tools

The LLM must call TennixAI business tools:

```text
LLM
 ↓
Business Tool
 ↓
TennisService
 ↓
Provider
```

P1 exposes exactly three domain-semantic tools:

- `find_player_matches(player_name, time_scope)` where `time_scope` is `today`, `tonight`, or `next`
- `get_live_matches(player_name=None)`
- `get_match(match_id)`

There must be no generic tool such as `call_tennis_api(url, params)`.

The same `TennisService` must serve deterministic REST endpoints and LLM tools. LLM integration is not a separate source of truth.

Tool arguments are Pydantic-validated. The model may make at most two tool-call rounds for one user request. Ambiguous player names produce a clarification response. Tools return canonical data only; match cards and actions are rendered from that trusted data rather than parsed from model prose.

## 9. Verified LiveTennisAPI constraints

Official reference: <https://docs.livetennisapi.com/reference.html>

As verified on 2026-09-07, LiveTennisAPI Free includes:

- live and upcoming matches
- current scores
- players
- fixtures
- tournament catalogue
- usage information
- 30 requests per minute
- 100 requests per day

Important limitations and conventions:

- completed-match listings and historical results require Basic or a History entitlement
- `GET /matches/{matchId}` remains a Free endpoint for a known match ID
- match IDs remain stable through upcoming, live, and completed lifecycle states
- timestamps are UTC ISO 8601
- `server` is `1`, `2`, or `null`
- score arrays are player-major, not set-major
- round and surface can be null
- additive fields may appear within v1 and parsers must ignore unknown fields
- calls above the current plan return an explicit `403 upgrade_required`
- rate-limit responses include `429` and reset information

### Effect on P1 scope

Free access can reliably support current and upcoming queries. It cannot guarantee an arbitrary query such as “Did Sinner win yesterday?” unless TennixAI had already discovered the match, stored its ID, and later persisted its terminal result.

P1 intentionally does not build that persistence workaround and does not expose a recent-results business tool. General historical lookup is deferred until a later phase has an appropriate provider entitlement and persistence layer.

The Free daily quota is suitable for integration work but not unrestricted live polling. A single match polled once per minute for two hours consumes 120 requests. P1 therefore has no automatic polling. Reads happen on initial load, explicit in-app refresh, or a user query, and use server-side request coalescing, process-local caching, and explicit quota handling.

## 10. Verified API-Tennis constraints

Official documentation: <https://api-tennis.com/documentation>
Official plans: <https://api-tennis.com/>

As verified on 2026-09-07:

- registration includes a 14-day trial
- fixtures and livescore responses include `scores`, `statistics`, and `pointbypoint` inline
- unavailable detailed data is represented by empty arrays
- fixture filters include date range, match, player, event type, tournament, and season
- timezone defaults to `Europe/Berlin` unless explicitly supplied
- vendor responses expose fields such as `event_key`, `event_first_player`, `event_serve`, and string-form values

These differences from LiveTennisAPI validate the provider-adapter requirement. The API-Tennis adapter owns timezone conversion, lifecycle normalization, numeric parsing, empty-array semantics, and vendor ID extraction.

## 11. Verified Polymarket constraints

Official documentation:

- Market data overview: <https://docs.polymarket.com/market-data/overview>
- Prices and orderbook: <https://docs.polymarket.com/concepts/prices-orderbook>
- Trading authentication: <https://docs.polymarket.com/trading/overview>
- Geographic restrictions: <https://docs.polymarket.com/api-reference/geoblock>
- Market and sports behavior: <https://docs.polymarket.com/concepts/markets-events>

Public market discovery and market data do not require wallet authentication. Gamma API is used for event and market discovery; CLOB endpoints provide orderbooks, prices, spreads, and price history; the public market WebSocket provides live orderbook and price events.

Polymarket's displayed probability is not always an executable price. A normal display may use bid/ask midpoint, while wide spreads may cause the UI to show the most recent trade. Buying occurs at the ask and selling at the bid.

`MarketState` therefore must preserve at least:

- best bid
- best ask
- midpoint
- last trade
- spread
- liquidity
- market status
- observation timestamp

Prediction edge must be calculated against an explicit executable-price assumption and expected costs, not against an ambiguous display price.

Order placement requires wallet signatures and L1/L2 credentials. Geographic eligibility must be checked at execution time. Sports-market orders also have special start-time behavior, and scheduled match times can move. These constraints support the decision to keep automated order placement outside initial P3.

## 12. Frontend/backend boundary

The current Next.js App Router frontend can preserve Server Components for initial data loading and keep interactive query and live-update islands as Client Components.

Official references:

- Next.js Server and Client Components: <https://nextjs.org/docs/app/getting-started/server-and-client-components>
- Next.js Backend for Frontend guide: <https://nextjs.org/docs/app/guides/backend-for-frontend>
- FastAPI SSE: <https://fastapi.tiangolo.com/reference/sse/>

Browser Client Components call same-origin Next.js Route Handlers under `/api/*`. Those handlers are a thin proxy to FastAPI: they add no business logic, preserve HTTP status and SSE semantics, and prevent the browser from knowing the backend address. Server Components may call FastAPI directly. `TENNIX_BACKEND_URL` is server-only, and all provider and LLM credentials remain in FastAPI.

SSE is used initially for conversational streaming. Live score retrieval is request-driven in P1; no timer-based polling runs in the browser or backend. Polling and push are deferred until Redis-backed coordination is introduced in P2, while remaining hidden behind the same service and domain contracts.

The prototype is the visual source of truth. Real data is introduced incrementally by extracting mock routing, adding DTO-to-view-model mappers, and preserving the existing components and interaction states. P1 establishes Playwright screenshot baselines at desktop `1440×1000` and mobile `390×844`. The production match route is `/matches/{internal_match_id}`; the existing `/match?status=...` route may remain temporarily as an explicit visual-preview route.

## 13. P1 acceptance set

The initial acceptance questions are:

```text
今晚 Sinner 几点打？
Alcaraz 今天有比赛吗？
Djokovic 下一场对谁？
这是什么赛事？
第几轮？
什么场地？
比赛开始了吗？
现在比分多少？
谁在发球？
```

Historical questions are tested separately to verify the explicit `unsupported` behavior.

Acceptance must validate both deterministic service output and the LLM tool path. A correct service response must not be hidden by a model failure, and a fluent model response must not compensate for incorrect or missing data.

## 14. P1 scope guardrails

P1 uses:

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- Python
- FastAPI
- Pydantic
- httpx
- process-local in-memory identity and TTL cache
- native LLM tool calling
- SSE for chat streaming
- Playwright with Chromium for browser E2E and visual regression

P1 does not introduce:

- Kafka
- Kubernetes
- microservices
- LangGraph
- vector databases
- Elasticsearch
- ClickHouse
- Airflow
- feature stores
- complex event sourcing
- automated Polymarket trading
- PostgreSQL
- Redis
- automatic polling
- authentication
- arbitrary historical-result lookup

P1 runs as a local, single-user, single-process product slice. Its process-local cache uses in-flight request coalescing, a maximum of 256 entries, and these initial TTLs: 60 seconds for live lists and live match detail, 10 minutes for upcoming matches, one hour for player search, and 30 seconds for empty or not-found results. A stale live value may be served for at most five minutes and a stale upcoming value for at most 30 minutes, with freshness clearly marked. Provider `429` responses preserve `Retry-After` semantics.

Relative dates use `Asia/Macau`. `today` is the local calendar day, `next` is the earliest non-terminal match after the current time, and `tonight` is the active or next local night window from 18:00 through 05:59 the following day. Match selection excludes fixtures whose canonical start time has already passed unless their lifecycle is live.

Redis is introduced in P2 for shared cache state, coordinated polling and locks, provider-quota accounting, and event distribution across workers. PostgreSQL is introduced alongside it for stable identities, external-ID mappings, snapshots, and later history.

## 15. LLM and API configuration

P1 uses an OpenAI-compatible Chat Completions endpoint with native function calling through the OpenAI Python SDK. The initial model is `qwen3.8-max-0902`.

TennixAI owns its configuration and does not read another project's environment file at runtime:

- `TENNIX_LLM_API_KEY`
- `TENNIX_LLM_BASE_URL`
- `TENNIX_LLM_MODEL`
- `TENNIX_BACKEND_URL` for the Next.js server-side proxy

Only safe variable names and descriptions belong in `.env.example`; secret values are never committed. P1 does not require a vision model or LangGraph.

Chat is stateless on the server. The browser keeps recent messages in React state and submits them with each request. Home requests use global scope; Match Page requests use match scope plus the internal `match_id`. Refreshing or closing the browser may discard the conversation, which is accepted in P1.

The chat stream uses five event types: `status`, `data`, `text_delta`, `done`, and `error`. Structured data and generated prose remain separate. If `TennisService` succeeds but the LLM fails, the API still returns the structured match data with fixed fallback copy. If the provider fails, the LLM may not invent an answer.

FastAPI owns these P1 routes:

- `GET /api/v1/health`
- `GET /api/v1/players/search?q=...`
- `GET /api/v1/matches?status=live|upcoming&player=...`
- `GET /api/v1/matches/{match_id}`
- `POST /api/v1/chat/stream`

Next.js proxies them at `/api/players/search`, `/api/matches`, `/api/matches/[matchId]`, and `/api/chat/stream`. Errors use stable codes: `invalid_request`, `ambiguous_player`, `not_found`, `unsupported`, `provider_unavailable`, `rate_limited`, `llm_unavailable`, and `internal_error`.

## 16. Verification strategy

Deterministic unit and integration tests use fake providers and a fake LLM. Live integrations are explicit opt-in pytest markers:

- `llm_live`: real Qwen with a fake tennis provider
- `provider_live`: fake LLM with real LiveTennisAPI
- `end_to_end_live`: real LLM with real LiveTennisAPI

Real-model assertions verify the selected tool, validated arguments, and agreement with structured facts rather than exact prose. The model name is pinned for those checks.

Playwright runs full-browser Chromium E2E. Default browser tests use controlled fake dependencies; one browser smoke test exercises the real LLM, while a fully real provider-plus-LLM browser path remains an explicit manual gate because of quota and live-data variability. Failures retain screenshots, traces, and console logs. Visual regression covers Home and Match states at the approved desktop and mobile viewports.

## 17. Implementation-order principle

The deterministic data path must work before LLM integration:

```text
Provider samples and contracts
→ Canonical models
→ Provider adapter
→ TennisService
→ FastAPI endpoints
→ Real frontend structured responses
→ Business tools
→ LLM tool calling
→ Chat streaming
→ Acceptance suite
```

This ordering ensures the tennis data product remains valid if the provider, LLM, frontend, or chat experience changes.
