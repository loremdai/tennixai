# TennixAI Home Historical Player Query Closure Design

**Date:** 2026-09-13

**Status:** Approved approach A; written design awaiting final user review

**Task:** T54 — Close Home Historical Player Queries

**Baseline:** `259235c` (T54 claim; implementation starts from the later approved-plan baseline)

**Extends:** [P2.6 Player Directory, Multilingual Identity, and Historical Results Design](./2026-09-12-tennixai-player-directory-multilingual-identity-design.md)

## 1. Purpose

Close the verified gap between P2.6's approved Home historical-question contract and the shipped Chat behavior. The repair must make Home answer limited player-history questions with structured canonical facts while preserving the existing PlayerResolver, provider abstraction, SSE route, visual language, and P2 scope.

This is a P2.6 corrective gate, not P3 work.

## 2. Verified Baseline and Failure

The multilingual identity layer is working:

- `辛纳` resolves to Jannik Sinner's internal player ID;
- `郑钦文` resolves to Qinwen Zheng's internal player ID;
- API-Tennis returns finished results for both players when queried through the existing internal-ID path.

The Home query still fails because the layers after identity resolution do not form a complete product contract:

1. `is_historical_query()` recognizes phrases such as `上一场` but not natural variants such as `上一次` or bare `赛果`.
2. Optional history tools are removed from the model catalog when that phrase gate returns false.
3. The existing Chat `recent` result path is a fixed 30-day window, which cannot implement “the last match” for an active player whose latest match is older than 30 days.
4. The orchestrator can emit multiple structured `data` events, but `useChatStream` overwrites the previous event, so a multi-player answer retains only the last payload.
5. The Home title maps every non-resolution empty payload to “没有符合条件的比赛”, regardless of whether the question concerned current matches, recent results, or season records.
6. Existing live gates accept non-empty prose plus SSE `done`; they do not require the expected structured historical facts.

The resulting failure path is:

```text
limited historical question
        ↓
history capability gate misses the wording
        ↓
history business tools are absent from the model catalog
        ↓
model can only query live/upcoming matches
        ↓
empty current-match facts
        ↓
honest but incorrect “资料不足” prose
        ↓
generic current-match empty title
```

## 3. Goals

T54 must deliver all of the following:

1. Recognize common Chinese and English wording for yesterday, last result, recent results, season record, and H2H capability routing.
2. Give “last” and “recent” result scopes result-count semantics rather than a fixed 30-day meaning.
3. Reuse the existing on-demand current-plus-four-prior-season provider path and cache; do not mirror supplier history.
4. Return typed structured player-history facts that identify the resolved player and requested scope.
5. Preserve every distinct SSE `data` event in the frontend so one question can render multiple players.
6. Render player-history results and per-player empty states in the existing Home answer shell.
7. Validate factual content with deterministic, real API-Tennis, real LLM, and real-browser gates.
8. Reopen and then truthfully re-close P2.6 before P3 design begins.

## 4. Non-goals

T54 must not add:

- Polymarket, odds, prediction, edge, confidence, paper trading, or any other P3 capability;
- automated order placement;
- a database migration or full supplier-history mirror;
- runtime translation LLM, RAG, vector search, or another name resolver;
- doubles;
- a Player Page chatbot;
- a second routing model;
- cloud deployment, cron, queue, worker, or scheduled history ingestion;
- arbitrary career-history answers outside the existing five-season product window;
- a Home redesign.

## 5. Approved User Semantics

All dates use the existing `Asia/Macau` product timezone. Only finished canonical matches are historical results.

| User wording | Business meaning | Structured scope | Default amount |
|---|---|---|---|
| `昨天`、`昨日`、`yesterday` | Results whose local calendar date is yesterday | `yesterday` | up to 10, normally all returned by the bounded day query |
| `上一场`、`上一次比赛`、`上场比赛`、`last match`、`previous match` | Latest known finished match inside the product history window | `last` | exactly 1 |
| `最近`、`近期`、`最近赛果`、bare `赛果`、`recent results` | Latest finished matches inside the product history window | `recent` | 5 unless the user asks for 1–10 |
| `本赛季`、`这个赛季`、`当前赛季`、`今年`、`赛季战绩`、`season record` | Supplier-backed season wins/losses, win rate, titles, and available surface records | `season` | current Macau calendar year unless explicitly supplied |
| `交手`、`对战`、`H2H`、`head-to-head` | Existing limited H2H tool | `head_to_head` | existing limit behavior |
| `全部历史`、`完整历史`、`生涯战绩`、`all-time` | Outside the bounded P2 contract | `unsupported` | no provider call |

The word `结果` alone is not enough to route to player history because it can describe a current Match Page question. `比赛结果` combined with a player identity is a limited-results signal in Home scope.

A single Home prompt may contain multiple players and different scopes. For example:

```text
辛纳上一次比赛是什么时候？郑钦文最近赛果如何？
```

must produce one `last` result fact for Jannik Sinner and one `recent` result fact for Qinwen Zheng. One empty result must not erase or downgrade the other player's successful result.

## 6. Capability Routing

### 6.1 Deterministic gate, semantic execution

The deterministic gate only decides which business capabilities the model may see. It must not parse player names, fabricate tool arguments, or answer the question itself.

Replace the current single narrow phrase check with one tested capability classifier that can return a set containing:

```text
limited_results
season_record
head_to_head
broad_history
```

When a limited history signal is present, expose the relevant optional business tool. The LLM remains responsible for splitting natural-language clauses and choosing one call per player, while the tool executor remains responsible for PlayerResolver and canonical data access.

If a prompt contains only broad-history intent, return the existing typed unsupported result without model or provider calls. If a prompt contains both supported limited history and broad-history wording, allow the supported calls and require the generated answer to identify the unsupported portion instead of rejecting the whole request.

No routing LLM is added. The classifier must be deterministic and covered by a Chinese/English phrase matrix.

### 6.2 Business tool catalog

Keep `get_head_to_head` unchanged. Use these player-history tools:

```python
get_player_results(
    player_name: str,
    scope: Literal["yesterday", "last", "recent"],
    limit: int = 5,
)

get_player_season_record(
    player_name: str,
    season: int | None = None,
)
```

Rules:

- `last` always returns at most one match; a model-supplied larger limit is normalized to 1.
- `recent` accepts 1–10 and defaults to 5.
- `yesterday` accepts 1–10 and keeps the existing local-calendar meaning.
- `season=None` means the current Macau calendar year.
- An explicit season outside current year through current year minus four is rejected as `invalid_request` and can be replanned within the existing tool budget.
- Every name-bearing call first uses the shared PlayerResolver and then queries by internal ID.

The system prompt and tool descriptions must state these semantics directly, including “bare 赛果 means recent” and “one call per requested player”.

## 7. Service and Provider Behavior

### 7.1 Yesterday

Preserve the current yesterday semantics and bounded API behavior. The service filters by `Asia/Macau` date and returns a successful typed empty result when the provider call succeeds but the player has no match that day.

### 7.2 Last and recent

Do not use `RECENT_RESULTS_WINDOW_DAYS` to implement `last` or `recent`.

Reuse the existing cached `_load_season_results(player_id, season)` path:

```text
current season
    ↓ sort finished matches newest first
enough matches? ── yes → stop
    ↓ no
previous season
    ↓
repeat through current_year - 4
```

The algorithm must:

- query seasons newest to oldest;
- stop as soon as the requested result count is reached;
- never inspect more than the approved five-season window;
- deduplicate by canonical internal match ID;
- exclude future, live, cancelled, postponed, and unknown-status matches;
- sort the final set by `scheduled_at` descending with deterministic internal-ID tie-breaking;
- return at most 1 for `last` and at most the requested 1–10 for `recent`;
- reuse the existing ten-minute non-empty and sixty-second empty per-season caches;
- make no database schema or storage change.

For an active player, the normal path remains one cached/provider season lookup. Additional provider calls occur only when the newer season does not contain enough finished results.

### 7.3 Season record

Add a service method that loads the existing cached player profile and selects the requested `PlayerSeasonRecord` without also fetching live/upcoming state. Do not call `get_player_profile_view()` because that method performs unrelated current-match requests.

The supplier-backed fields are:

- `matches_won`;
- `matches_lost`;
- derived win rate when wins plus losses is non-zero;
- `titles`;
- available hard, clay, and grass records.

Missing supplier season data remains unavailable. Do not infer titles or surface records from incomplete result lists. A zero-match supplied season is distinct from an unavailable season record.

## 8. Typed Chat Result Contract

Extend `StructuredToolResult.kind` and the public frontend union with:

```text
player_history
```

Add a typed `PlayerHistoryContext` alongside the existing top-level canonical `matches` list:

```python
class PlayerHistoryContext(BaseModel):
    player: Player
    scope: Literal["yesterday", "last", "recent", "season"]
    season: int | None
    availability: CapabilityStatus
    season_record: PlayerSeasonRecord | None
    empty_reason: Literal[
        "no_results_in_scope",
        "season_record_unavailable",
    ] | None
```

`StructuredToolResult` uses:

```python
kind="player_history"
matches=[...]
player_history=PlayerHistoryContext(...)
```

This keeps canonical Match objects in the existing place while removing reliance on untyped metadata for player identity and history semantics.

Contract rules:

- public player and match IDs are Tennix internal IDs only;
- English name remains primary and Chinese name secondary;
- successful empty results are `player_history`, not `unsupported` and not an exception;
- `ambiguous` and `not_found` remain recoverable `player_resolution` results ending with SSE `done`;
- provider/database failures retain the existing typed failure and optional degradation behavior;
- compact model facts include the same player, scope, season, availability, season record, and bounded matches;
- no supplier ID, raw payload, alias provenance, provider URL, or credential enters REST, SSE, HTML, logs, fixtures, or model facts.

## 9. Multi-result SSE Consumption

Do not change the SSE wire protocol or Next.js proxy. The backend continues to emit one `data` event per distinct successful tool outcome before synthesis.

Extend `ChatViewState` with:

```typescript
dataItems: StructuredData[]
```

On a `data` event:

- append the payload to `dataItems` in emission order;
- retain `data` as the latest payload for compatibility during T54;
- keep the first non-null `answerContext` behavior;
- reset `dataItems` on a new send and on `reset()`;
- preserve already received facts when the user cancels, matching the current partial-answer behavior.

The orchestrator already suppresses duplicate tool outcomes; the frontend must not discard distinct results merely because they share `kind="player_history"`.

Existing current-match and Match Page behavior must remain compatible. T54 may use `dataItems` to combine or group results, but must not silently change the frozen-answer or `answer_context` contract.

## 10. Home Presentation

Preserve the existing Home answer shell, typography, colors, spacing language, Markdown answer, warnings, progress, retry, and “Open Match” behavior. Do not redesign the page.

When `dataItems` contains player history:

- render one section per `player_history` result in tool-result order;
- section heading uses `English Name（中文名）` when both are available;
- label the scope as `昨日赛果`, `上一场比赛`, `近期赛果`, or `<year> 赛季战绩`;
- render finished canonical matches with the existing card vocabulary and existing internal Match Page link;
- render season wins, losses, win rate, titles, and only available surface records;
- render a per-player empty message: `该范围暂无赛果信息` or `该赛季战绩暂不可用`;
- never let one empty player hide another player's matches or summary.

Query-level title rules:

- one history result: `<player display name> · <scope label>`;
- multiple history results: `球员赛果与战绩`;
- current/live/upcoming queries keep their existing title behavior;
- broad unsupported history keeps its existing unsupported title;
- `没有符合条件的比赛` is reserved for current/live/upcoming match discovery, not player history.

No existing approved snapshot may be updated merely to make a regression pass. Add dedicated desktop `1440×1000` and mobile `390×844` history-answer states. Existing Home/Match/player snapshots must remain unchanged unless a separately proven and documented task-caused correction requires review.

## 11. Error and Partial-result Policy

| Situation | Required behavior |
|---|---|
| Resolved player, no matching finished result | Typed successful `player_history`, per-player empty copy, SSE `done` |
| Season record absent | Typed `player_history` with unavailable record and honest copy, SSE `done` |
| One of multiple optional history calls fails | Warning for that item; preserve and render successful items; SSE `done` when existing core/optional policy allows |
| Ambiguous player | Candidate list with internal player links; no guess; SSE `done` |
| Unknown player | Helpful clarification; SSE `done` |
| Broad career history only | Typed `unsupported`; no provider call |
| Provider rate limit or infrastructure failure with no usable data | Existing typed error/retry policy |
| LLM synthesis fails after structured data | Preserve structured history sections, fixed friendly fallback, warning, SSE `done` |

The generated prose must not claim that data is absent when structured facts contain matches or a season record.

## 12. Acceptance and Regression Gates

### 12.1 Deterministic backend

Add tests that prove:

- the Chinese/English capability phrase matrix, including `上一次`, `赛果`, `赛季战绩`, and broad unsupported wording;
- relevant history tools enter the global catalog and unrelated questions do not expose/call them;
- `last` returns exactly the newest finished match even when older than 30 days;
- `recent` collects up to the requested count across a year boundary and stops early;
- five-season exhaustion is bounded and returns a successful empty result;
- season records use the profile cache without live/upcoming calls;
- mixed multi-player tool outcomes emit distinct `player_history` data events before synthesis;
- successful empty and successful non-empty outcomes coexist;
- compact facts and public SSE contain no supplier fields or credentials;
- broad-history-only questions make zero provider/model calls;
- existing current-match, Match Chat, H2H, resolver, and frozen-answer tests remain green.

### 12.2 Deterministic frontend and browser

Add tests that prove:

- `useChatStream` accumulates multiple `dataItems` and resets them correctly;
- latest `data` and first `answerContext` compatibility remain intact;
- one and multiple player-history sections render correctly;
- a mixed empty/non-empty response preserves the non-empty section;
- history titles never use `没有符合条件的比赛`;
- finished result links use internal `/matches/<id>` routes;
- desktop and mobile history-answer states follow the approved Home visual language;
- existing visual baselines and functional journeys remain green.

### 12.3 Real service and content assertions

With the root `.env`, real API-Tennis, the configured real OpenAI-compatible LLM, PostgreSQL, Redis, backend, and frontend, verify at minimum:

1. `辛纳上一次比赛是什么时候？`
2. `郑钦文最近赛果如何？`
3. `辛纳上一次比赛是什么时候？郑钦文赛果如何？`
4. `郑钦文这个赛季战绩如何？`
5. `Shelton last match`
6. one controlled mixed empty/non-empty deterministic browser case

The gates must assert structured content, not merely non-empty prose or `done`:

- expected `player_history` count;
- expected resolved internal player identities;
- `scope` values;
- non-empty matches or non-null season record where the provider probe established availability;
- all returned matches are finished and correctly ordered;
- multi-player sections are simultaneously visible;
- no generic current-match empty title;
- SSE ends with `done` and no terminal error;
- no browser console error and no supplier ID/key leakage.

If live supplier data changes, assertions must validate invariants and compare against a direct provider/service result captured in the same test run; they must not freeze volatile opponent names or dates.

## 13. Rollout and Rollback

Implementation order must keep every commit independently testable:

1. intent and service semantics;
2. typed Chat result and orchestrator facts;
3. frontend accumulation and Home presentation;
4. real content gates and full regression;
5. control-document closure.

No migration is required. Rollback is the reversal of T54 product commits; existing player directory, aliases, ranking snapshots, provider history endpoints, and P2 realtime data remain compatible.

## 14. Control-document Closure

T53 remains `done` as a historical fact. It is not rewritten as though its checks never passed.

T54 may be marked `done` only when:

- the exact real-service content gates above pass;
- all affected deterministic and full regression gates pass;
- dedicated history-answer visuals are reviewed at both approved viewports;
- the repository and public-output leakage scans pass;
- product commits and a final control-only commit are pushed to `origin/main`;
- `PROJECT.md`, `ROADMAP.md`, and `CURRENT.md` record exact commits and actual test evidence;
- P2/P2.6 return to `done` and P3 returns to `planned` / `ready for design`, still requiring explicit user authorization.

Until then, P3 is not ready to start.
