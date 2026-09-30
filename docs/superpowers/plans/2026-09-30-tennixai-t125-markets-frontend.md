# T125 Markets Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring production `/markets` into the approved Home visual language while making the default ATP/WTA selection and level/phase order correct across database-paginated results.

**Architecture:** Keep the existing three production views and DTOs. Send active listing filters to the existing bounded markets endpoint, let PostgreSQL apply multi-tier filters and deterministic tier/phase ordering before the 50-row page, and render each market with existing identity, quote, and freshness data. Keep the frozen `?preview=p3` page untouched.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, Next.js, React, TypeScript, Tailwind CSS, Vitest, pytest, Playwright.

**Spec:** User-approved visual reference: `docs/mockups/2026-09-30-markets-home-style.png`; confirmed choices in the T125 conversation: Home is the visual source, tabs stay compact and left-aligned with an underline, ATP and WTA are selected by default, rows retain real player avatars and bilingual names plus quote status, and competition tier sorts before phase (`live → prematch → closed`).

## Global Constraints

- The production page retains the three views: opportunities, all markets, and paper records.
- The default all-markets tier selection is ATP + WTA; gender and phase default to all.
- Tier sort order is ATP, WTA, Challenger, ITF, other, then unlinked/unknown; within each tier phase order is live, prematch, closed, then unknown.
- Page size stays capped at 50 and filters, ordering, total, and offset apply in PostgreSQL before materializing summaries.
- Never invent quotes, identities, images, decisions, or real-time status; absent values remain explicit and quote-state wording remains truthful.
- Show the live set only when the canonical match is live and its snapshot is connected and at most 60 seconds old; show the final score only for a canonically finished match, aligned to market outcome IDs. Invalid optional score/set values are omitted without failing the market page.
- `/markets?preview=p3` and its frozen fixtures remain unchanged.
- Keep all existing user-owned working-tree changes; stage only files owned by T125.

## Review Focus

- No `tier` query parameter means ATP + WTA; explicit `tier=all` means every tier. Test both so an empty selection does not silently revert to the default.
- Repeated `tier` parameters filter multiple tiers before pagination; test the API contract and a page boundary.
- Filter changes reset pagination and late responses for an older filter cannot replace the selected result. Test query parameters, reset, and selected totals.
- Closed market status and finished match status both sort as ended; unlinked or unknown rows sort after known competitions and phases. Test database ordering.
- Only a realtime quote gets the realtime label and lime dot; snapshots and degraded states keep their truthful label. Test at least realtime, snapshot, and stale.

---

### Task 1: Canonical market filters and database ordering

**Files:**
- Modify: `backend/app/api/routes.py` — accept repeated `tier` query parameters.
- Modify: `backend/app/persistence/market_repositories.py` — apply multiple-tier filters and tier/phase SQL ordering before `LIMIT/OFFSET`.
- Test: `backend/tests/test_p3_api.py` — repeated-tier route contract.
- Test: `backend/tests/integration/test_p3_query_service.py` — tier filter, phase order, and database page boundary.

**Interfaces:**
- Consumes: existing `/api/markets` query contract and `MarketRepository.list_market_overview_page`.
- Produces: `tier: list[Literal["atp", "wta", "challenger", "itf", "other"]] | None` at the REST boundary; a string or sequence remains accepted by the repository for internal compatibility.
- Sort key: circuit rank, phase rank (`live=0`, `scheduled/prematch=1`, `finished/closed=2`, unknown=3`), then `MarketRow.updated_at DESC`, `MarketRow.id ASC`.

- [x] **Step 1: Write failing tests** — route accepts `tier=atp&tier=wta` and forwards both; integration rows sort ATP live, ATP prematch, ATP ended, WTA live, WTA ended, Challenger live, and page 1/page 2 preserve that order while excluding tiers outside the filter.
- [x] **Step 2: Run tests and verify RED** — repeated tiers and update-time ordering failed before implementation.
- [x] **Step 3: Implement the query contract and SQL order** — add repeated-tier parsing at the route and `.in_(...)` filtering plus SQL `CASE` order before limit/offset.
- [x] **Step 4: Run tests and verify GREEN** — backend API/integration tests passed with the configured PostgreSQL schema.
- [x] **Step 5: Commit** — `a9dd266 feat: sort market pages by tier and phase`.

### Task 2: Home-style production markets page

**Files:**
- Modify: `frontend/lib/api/client.ts` — serialize selected tiers as repeated query parameters and include active listing filters.
- Modify: `frontend/app/markets/page.tsx` — default missing tier selection to ATP/WTA and recognize explicit `tier=all`.
- Modify: `frontend/components/markets/markets-state.tsx` — request filtered pages, reset page state on filter changes, show tab counts and approved heading/sort hierarchy.
- Modify: `frontend/components/markets/markets-tabs.tsx` — compact left-aligned tabs, counts, active lime label and underline.
- Modify: `frontend/components/markets/market-filters.tsx` — match the approved filter panel while keeping defaults and all filter controls accessible.
- Modify: `frontend/components/markets/market-row.tsx` — use provider images when present, neutral fallback avatars, bilingual names, cents quote pills, truthful per-row status and navigation chevron.
- Test: `frontend/components/markets/markets-page.test.tsx` and a focused `frontend/app/markets/page.test.tsx` if needed for route defaults.
- Test: `frontend/e2e/p3-markets.spec.ts` — update default filter assertions and exercise filter reset/pagination behavior.

**Interfaces:**
- Consumes: Task 1 repeated-tier REST contract, current `MarketSummaryDto`, `PlayerAvatar`, `PlayerName`, and quote-state view model.
- Produces: default tiers `['atp', 'wta']`; `tier=all` encodes an explicit unfiltered selection; selected tiers, gender, and phase are sent to `listMarkets` and server totals describe that filter set.
- Visual: plain left-aligned tab row with a shared baseline; Home black/lime palette; filters before count/sort summary; stacked match rows with tournament/phase, two avatar/name rows, rounded cents prices, truthful quote status and chevron.

- [x] **Step 1: Write failing tests** — cover default ATP/WTA chips and request params, `tier=all`, filter changes/reset reloading page 1, tab alignment/counts, bilingual avatar rows, cents formatting, realtime versus snapshot/stale wording, canonical phase context, and absence of fabricated market data.
- [x] **Step 2: Run tests and verify RED** — new route, filter, context, decoder, and score-safety assertions failed before their implementations.
- [x] **Step 3: Implement the approved layout and filtered paging** — reuse existing components, keep DTO values authoritative, and leave the preview page unchanged.
- [x] **Step 4: Run tests and verify GREEN** — 553 Vitest tests, TypeScript check, 20 focused desktop/mobile Playwright tests, and a production Webpack build passed.
- [x] **Step 5: Verify the visual result** — production `/markets` viewport was visually inspected and the 20 focused desktop/mobile browser checks passed; preview baselines were not changed.
- [x] **Step 6: Commit** — `71c3584 feat: align markets page with home design`.

### Task 3: Close T125 with verification evidence

**Files:**
- Modify: `CURRENT.md` — record completion commit(s) and actual validation results.
- Modify: `ROADMAP.md` — mark T125 done with implementation and validation evidence.
- Include: `docs/mockups/2026-09-30-markets-home-style.png` — archive the approved reference used by the implementation.

**Interfaces:**
- Consumes: committed Tasks 1–2 and their test results.
- Produces: a T125 completion record that names tested commands and any environment-limited checks honestly.

- [x] **Step 1: Run final focused backend and frontend tests**, frontend typecheck/build, and `git diff --check`; inspect staged paths to exclude user-owned changes.
- [x] **Step 2: Update `CURRENT.md` and `ROADMAP.md`** with actual commits and command results.
- [x] **Step 3: Commit only T125 artifacts and docs.**
- [x] **Step 4: Verify pushed HEAD, clean T125 diff, and preservation of pre-existing user changes** — `HEAD == origin/main == 1e0ea1a`; only documented user-owned working-tree changes remain.
