# TennixAI Consumer-Facing Frontend Design

**Date:** 2026-09-24
**Status:** Authorized by user for direct Codex design and implementation; v0 is unavailable.

## Purpose

Make TennixAI understandable and useful to tennis fans, not only to developers or project operators. Keep the product's structured tennis data and match intelligence; simplify how that information is introduced, prioritized, and explained.

## Audience and product promise

- Audience: a tennis fan who wants to find matches, understand player and match facts, and inspect market information without knowing the implementation roadmap.
- Promise: show useful tennis facts first, tell the truth when information is missing or delayed, and let the user move from discovery to match detail naturally.
- Preserve the existing dark visual identity, tennis-court green accent, and high-contrast live indicator. Do not add a UI dependency or invent data to fill visual space.

## Information architecture

- **Home:** today's live and upcoming matches are primary. Keep one clear global question/search entry; show the answer and structured match cards in the same user journey. Remove phase toggles, duplicate prompts, unsupported watchlist/history shortcuts, demo identity, decorative probability content, and nonfunctional notification/settings controls.
- **Players:** present the available ATP/WTA singles ranking list and search. Counts and coverage must reflect the actual response; do not promise “Top 200” when fewer records were returned. Player profiles prioritize identity, current ranking/snapshot date, current match, and readable results.
- **Match:** lead with the two players, event, Beijing-local start time, status, and score. Group secondary detail (statistics, point history, market/decision, paper record) with plain-language labels and honest missing/stale states. A failed match load must offer a working way back to Home or the relevant player.
- **Markets:** clearly separate real market quotes from model output. Use consumer labels for the three views: “机会”, “全部市场”, and “模拟记录”. If model coverage is unavailable or not approved, say so in ordinary Chinese and show the real quotes only where available. Paper activity is explicitly simulation, never a real order.

## Language and data rules

- User-visible product copy is natural Chinese by default. Keep standard tennis terms and player names where useful; do not expose phase numbers, raw enum names, internal IDs, provider jargon, or developer-only test controls in production surfaces.
- Translate decision states without changing their meaning: eligible actions, waiting, no recommendation, pending simulation, open simulation, exit, missed fill, and settlement remain distinct.
- Preserve exact values, units, event times, and source freshness. Unknown data stays unknown; stale data remains visible only with a clear “更新较慢/最后更新时间” cue. Never render missing statistics as zero.
- Empty, unavailable, partial, stale, and error states each explain what happened and offer a useful next step when one exists.

## Visual and interaction rules

- Keep the current brand colors and shared components; improve hierarchy through spacing, typography, section ordering, and progressive disclosure rather than new decoration.
- Avoid oversized promotional copy, repeated cards, fake live indicators, English developer headings, and duplicated assistant inputs.
- Responsive behavior must work at 375, 768, 1024, and 1440 px without horizontal overflow. Interactive controls need visible keyboard focus, clear labels, and reduced-motion support.

## Acceptance

- A consumer can identify the page purpose, the current match state, and what to do next without understanding P1/P2/P3, provider, canonical, market-only, or lifecycle terminology.
- No visible control claims functionality that does not exist.
- Match, player, market, and paper facts remain source-backed and are not fabricated to improve the presentation.
- Unit tests, TypeScript checks, and browser checks cover changed copy, supported interactions, empty/error states, keyboard use, and narrow-screen layout.
