# T117 — Markets Page Redesign Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan inline. Steps use checkbox syntax for tracking.

**Goal:** Implement the approved markets-page design so users can compare real tennis market quotes and their freshness quickly on desktop and mobile.

**Architecture:** Keep the existing three views, typed view models, API contract, URL filters, and navigation. Rework the existing market rows and filter presentation with responsive CSS; tighten opportunity, paper, and empty-state rows only where the approved design calls for it.

**Tech Stack:** Next.js, React, TypeScript, Tailwind CSS, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-29-tennixai-t116-markets-readability-design.md`

## Global Constraints

- Keep the page views `机会 / 全部市场 / 模拟记录` and their URL behavior.
- Do not change API DTOs, backend behavior, pagination size, market matching, model decisions, or Paper lifecycle.
- Keep frozen `?preview=p3` behavior and visual baselines intact unless an individually reviewed production baseline must change.
- Show only returned quote/model values; preserve partial, stale, unavailable, no-liquidity, unmapped, and pending states.
- Do not touch `.env`, `.next`, the running services, or unrelated user changes.

## Review Focus

- Long and doubles player names wrap without clipping or horizontal overflow.
- A missing model result does not leave an empty column or imply a model action.
- An unmapped market remains non-navigable; mapped rows retain keyboard-accessible navigation.
- Paper pending/missed/settled meanings and displayed values stay unchanged.
- Filters retain existing URL and loaded-page semantics on desktop and mobile.

---

### Task 1: Reshape all-market rows and compact filters

**Files:**
- Modify: `frontend/components/markets/market-row.tsx`
- Modify: `frontend/components/markets/market-filters.tsx`
- Modify: `frontend/components/markets/markets-state.tsx`
- Test: `frontend/components/markets/markets-page.test.tsx`
- Test: `frontend/e2e/p3-markets.spec.ts`

- [ ] Add a focused regression assertion for the approved quote-first order, missing-model layout, and compact/mobile filter behavior; run it and confirm it fails on the current layout.
- [ ] Reorder each row around match identity, two independent real quotes, quote state/freshness, then only available secondary metrics. Preserve model/action display only when returned. Remove truncation of player names and retain unmapped non-link behavior.
- [ ] Collapse mobile filters behind the existing controls and keep all existing choices, reset, URL synchronization, and loaded-page count semantics.
- [ ] Run the focused Vitest and Playwright checks and confirm the regression passes without breaking existing state/navigation behavior.

### Task 2: Align opportunities, Paper rows, and empty state

**Files:**
- Modify: `frontend/components/markets/opportunity-row.tsx`
- Modify: `frontend/components/markets/paper-row.tsx`
- Modify: `frontend/components/markets/opportunity-empty-state.tsx`
- Test: `frontend/components/markets/markets-page.test.tsx`
- Test: `frontend/components/markets/paper-row.test.tsx`

- [ ] Add focused assertions for compact unpromoted-model empty state and the existing Paper state/value distinctions; run them and confirm at least the layout assertion fails before implementation.
- [ ] Put action and target player first for opportunities; display `$10` simulated average price, model probability, edge, and freshness only from existing data.
- [ ] Group Paper display by current ledger priority and make status/direction lead each row without recalculating ledger values.
- [ ] Run the focused Vitest suite and confirm existing Paper pending/missed/settled assertions still pass.

### Task 3: Verify responsive behavior and protected surfaces

**Files:**
- Test: existing markets component and E2E suites; no new runtime dependency.

- [ ] Run frontend Vitest and TypeScript typecheck.
- [ ] Run `frontend/e2e/p3-markets.spec.ts` at its desktop/mobile viewports; verify no horizontal overflow, correct tab/filter state, accessible row navigation, and quote state labels.
- [ ] Review any changed visual baselines individually. Do not update frozen preview baselines or adjust snapshots to conceal layout defects.
- [ ] Inspect the final diff and run `git diff --check` before completion.
