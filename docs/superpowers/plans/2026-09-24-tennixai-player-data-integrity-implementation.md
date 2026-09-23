# Player Data Field Integrity Implementation Plan

> **For agentic workers:** Execute this plan task-by-task. Keep the existing P2.6 visual contract; tests must establish each regression before production edits.

**Goal:** Make current singles ranking and player fields consistent across rankings, search, match cards, profile, and season summaries, while preserving unknown supplier values as unavailable.

**Architecture:** API-Tennis `get_standings` supplies the current rank/points snapshot; `get_players.stats` supplies season/type-specific profile statistics and is not a current-ranking source. PostgreSQL `player_rankings` is authoritative for current rank, points, movement, and fetch time. Directory aliases restore canonical English/Chinese display names where match feeds supplied abbreviations; match writes must not overwrite richer directory facts. The frontend maps this existing typed data into the frozen v0 layout.

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy/PostgreSQL, pytest; TypeScript, Next.js, Vitest, Playwright.

**Spec:** [P2.6 player directory design](../specs/2026-09-12-tennixai-player-directory-multilingual-identity-design.md), [P2.6 implementation plan](2026-09-12-tennixai-player-directory-multilingual-identity-implementation.md), and the current product contracts in `PROJECT.md`.

## Global Constraints

- `.env` remains the only local credential source; never print, copy, or modify credentials.
- Third-party IDs remain private; public responses use internal `ply_` IDs only.
- The latest stored singles ranking snapshot is the only authority for current rank/points; season statistics never substitute for it.
- Blank or invalid provider numbers remain unavailable (`null`), not fabricated zeroes.
- No new dependency, migration, runtime LLM call, or visual redesign.
- Preserve the running local runtime and all user-owned untracked files.

## Review Focus

- A player’s latest seasonal doubles rank must not become their current singles world rank; cover provider and profile tests.
- A match update with abbreviated name, null locale/country, or absent rank must not erase canonical directory facts; cover PostgreSQL persistence tests.
- Search and ranking DTOs must use the same latest snapshot rank, including players missing from the newest snapshot; cover memory and PostgreSQL repository contracts.
- Blank season totals and partial surface records must remain unavailable; cover provider and frontend view-model tests.
- An empty standings response and an explicit `page_size=50` request must not silently appear as fresh success or fail valid ranking-page use; cover sync and API tests.

---

### Task 1: Make the latest ranking snapshot authoritative

**Files:**
- Modify: `backend/app/players/models.py`
- Modify: `backend/app/players/repository.py`
- Modify: `backend/app/persistence/player_directory.py`
- Modify: `backend/app/service.py`
- Test: `backend/tests/test_player_directory_repository.py`
- Test: `backend/tests/test_player_profile_service.py`
- Test: `backend/tests/integration/test_player_directory_postgres.py`

- [ ] Add regression tests: if a stored player row says rank 72 but the latest WTA snapshot says rank 70, rankings, alias search, and profile report 70; ranking-list nested `player.ranking` equals the entry’s `rank`; a player omitted from the latest snapshot has no current rank.
- [ ] Run the focused tests and confirm the assertions fail against the current implementation.
- [ ] Add one repository contract method returning the latest `RankingEntry` for a player, with identical memory/PostgreSQL semantics and deterministic ordering by snapshot/fetch time.
- [ ] Make ranking-page nested player rank come from the selected `PlayerRankingRow`; make resolver candidate rank use the latest snapshot rather than denormalized `PlayerRow.ranking`.
- [ ] Compose the profile response from the directory’s canonical identity plus the latest ranking snapshot; leave season profile details sourced from `get_players`.
- [ ] Run the focused unit and PostgreSQL integration tests; confirm latest, missing, and tied-rank cases pass.

### Task 2: Preserve canonical player facts and honest season values

**Files:**
- Modify: `backend/app/persistence/player_directory.py`
- Modify: `backend/app/persistence/repositories.py`
- Modify: `backend/app/providers/api_tennis.py`
- Modify: `backend/app/players/models.py`
- Modify: `backend/app/providers/api_tennis_dtos.py` only if a provider shape requires it
- Test: `backend/tests/test_player_directory_repository.py`
- Test: `backend/tests/test_player_ranking_provider.py`
- Test: `backend/tests/integration/test_live_reduction_persistence.py`
- Test: `backend/tests/integration/test_player_directory_postgres.py`

- [ ] Add failing persistence tests proving abbreviated match updates and `null` fields do not replace an existing full name, localized name, country, or latest rank; prove a new match-only player can still be inserted.
- [ ] Add failing provider tests proving `get_players.stats` cannot supply current rank and blank/invalid season totals/surface cells stay unavailable.
- [ ] Implement the narrowest upsert protection: standings sync owns ranking/name/country; match feeds may create a player but must not overwrite existing canonical fields with abbreviated or missing values.
- [ ] Restore display names only from existing deterministic `FULL`/`PREFERRED` aliases; make no LLM calls and preserve alias ambiguity.
- [ ] Make provider season totals and each surface cell nullable, and filter ranking-like stats by singles only if any rank remains in profile metadata.
- [ ] Add only country-name/code mappings observed missing in the current ranking dataset, with canonical three-letter codes and frontend metadata.
- [ ] Run focused unit and PostgreSQL tests; verify idempotent upserts and alias fallbacks.

### Task 3: Expose ranking metadata through profile and frontend

**Files:**
- Modify: `backend/app/players/models.py`
- Modify: `backend/app/api/routes.py`
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/player-view-models.ts`
- Modify: `frontend/components/players/player-profile-header.tsx` only for accurate existing-field labels
- Modify: `frontend/components/players/player-season-summary.tsx`
- Test: `backend/tests/test_player_api.py`
- Test: `frontend/lib/player-view-models.test.ts`
- Test: `frontend/components/players/player-profile-page.test.tsx`

- [ ] Add a profile response test requiring the same rank/points/movement/fetch timestamp as the latest rankings snapshot and the player’s actual tour.
- [ ] Add a view-model regression test proving profile rank, points, movement, tour, and snapshot time are mapped from the ranking snapshot, not hardcoded `null`/`unknown`.
- [ ] Add season tests proving incomplete totals do not produce false match counts or win rates and partial surface records do not display invented zeroes.
- [ ] Extend only the existing profile DTO/view-model; keep the v0 layout and use its existing unavailable states for missing values.
- [ ] Run frontend Vitest, typecheck, and production build.

### Task 4: Guard incomplete ranking sync and verify the whole path

**Files:**
- Modify: `backend/app/players/sync.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_player_directory_sync.py`
- Test: `backend/tests/test_player_api.py`
- Test: `backend/tests/test_player_ranking_provider.py`

- [ ] Add failing tests: an empty ATP/WTA standings response preserves the last good snapshot and increments the sync failure count; explicitly passing `page_size=50` is accepted while non-50 page sizes remain rejected.
- [ ] Implement fail-closed empty-snapshot handling and parse the fixed page-size query as an integer constrained to exactly 50.
- [ ] Run the complete deterministic backend suite, focused PostgreSQL integration tests, complete frontend unit/type/build gates, and the relevant Playwright player-directory gate.
- [ ] Recheck the currently running local API read-only. Do not stop/restart its owner or claim that the running process has loaded new code.
- [ ] Update `CURRENT.md`, `ROADMAP.md`, and `PROJECT.md` only where their authoritative facts changed; commit and push the completed T92 changes and evidence.

