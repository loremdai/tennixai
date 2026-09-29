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
- Follow the approved mockup's compact hierarchy and green quote cards. Per the user's clarification, keep the existing page background instead of changing it to deep ink green.
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
- Modify: `frontend/components/markets/markets-tabs.tsx`
- Test: `frontend/components/markets/markets-page.test.tsx`
- Test: `frontend/e2e/p3-markets.spec.ts`

- [x] Add focused regressions for the reference hierarchy, two independent quotes, missing-model layout, and compact/mobile filters; verify the new assertions fail before the layout changes.
- [x] Reorder each row around match identity, two independent real quotes, quote state/freshness, then available secondary metrics. Preserve model/action display only when returned, wrap player names, and retain unmapped non-link behavior.
- [x] Collapse mobile filters behind the existing controls and keep all choices, reset, URL synchronization, and loaded-page count semantics.
- [x] Remove tab subtitles to match the mockup; retain the simulation disclosure in the page header/footer.
- [x] Run focused Vitest checks and attempt targeted Playwright checks. If browser startup is blocked, record the cause and verify the live desktop/mobile page and filter URL behavior directly.

### Task 2: Align opportunities, Paper rows, and empty state

**Files:**
- Modify: `frontend/components/markets/opportunity-row.tsx`
- Modify: `frontend/components/markets/paper-row.tsx`
- Modify: `frontend/components/markets/opportunity-empty-state.tsx`
- Test: `frontend/components/markets/markets-page.test.tsx`
- Test: `frontend/components/markets/paper-row.test.tsx`

- [x] Add focused assertions for the compact unpromoted-model empty state and existing Paper state/value distinctions; verify the layout assertion fails before implementation.
- [x] Put action and target player first for opportunities; display `$10` simulated average price, model probability, edge, and freshness only from existing data.
- [x] Group Paper display by current ledger priority and make status/direction lead each row without recalculating ledger values.
- [x] Run the focused Vitest suite and confirm existing Paper pending/missed/settled assertions still pass.

### Task 3: Verify responsive behavior and protected surfaces

**Files:**
- Test: existing markets component and E2E suites; no new runtime dependency.

- [x] Run the focused frontend Vitest suites and TypeScript typecheck.
- [x] Attempt targeted `frontend/e2e/p3-markets.spec.ts` desktop/mobile scenarios. Chromium could not start in this environment (`bootstrap_check_in ... Permission denied`); verify the live page at 375, 390, 768, 1024, and 1440 px and exercise the mobile filter, URL update, and reset in the browser.
- [x] Review visual changes; no frozen `?preview=p3` baseline was modified.
- [x] Inspect the final diff and run `git diff --check` before completion.

## Implementation and verification record

- The production `/markets` page now follows the mockup's compact header, underline tabs, filter-first hierarchy, paired quote cards, and status/metrics area. The quote cards use the mockup's dark-green treatment while the existing page background remains unchanged, as requested.
- Market, opportunity, and Paper values remain sourced from existing DTO/view-model data. Existing preview fixtures and visual baselines were not edited.
- Independent review caught three responsive/accessibility issues: opportunity/Paper columns activated too early, and two mobile buttons fell below 44px. Added regressions, confirmed them RED, fixed the row breakpoint and touch sizes, then confirmed GREEN.
- Verification: focused market, Paper, and header Vitest suites `3 files / 38 tests passed`; `tsc --noEmit` and `git diff --check` passed. Live market-page inspection covered 375/390/768/1024/1440 px and mobile filter selection/reset with URL synchronization. The actual runtime has no Paper rows or opportunities to render for visual inspection; row breakpoint behavior is covered by component regression tests.
- Limitation: targeted Playwright scenarios could not launch Chromium because the sandbox denied `bootstrap_check_in` for Chromium. The live browser checks above cover the corresponding visible responsive layout and filter interaction, but do not replace the unavailable automated E2E run.
