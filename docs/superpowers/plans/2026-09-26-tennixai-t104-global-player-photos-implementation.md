# T104 全站球员照片实施计划

> **For agentic workers:** 按任务顺序实施。保留根目录工作区既有修改；当前项目流程要求在 `main` 上逐项提交，仅暂存本计划所属文件。

**Goal:** 用 API-Tennis 的真实球员照片统一覆盖 TennixAI 中所有球员头像位，并为原本没有头像的页面补上照片。

**Architecture:** 用现有 `PlayerRow.image_url` 作为持久缓存，新增 canonical `Player.image_url` 将 provider、排名、比赛和目录输出统一起来。排名页按当前 50 人页面为缺图球员有界调用既有 profile 能力；Market/Paper 只通过已有内部球员 ID 传图。前端新增单一 `PlayerAvatar`，缺图/损坏图一律显示中性人像，不再用首字母。

**Tech Stack:** Python 3.12、FastAPI、Pydantic、SQLAlchemy/PostgreSQL、Next.js、TypeScript、React、现有 Base UI Avatar 与 lucide-react。

**Spec:** [T104 全站球员照片设计](../specs/2026-09-26-tennixai-t104-global-player-photos-design.md)

## Global Constraints

- 只使用 API-Tennis 明确返回的 `player_logo` / 赛事球员 logo；不加图片来源、抓取、下载、生成或 LLM 流程。
- 图片必须按内部 `player_id` 关联；不能对未匹配市场或双打姓名猜测身份。
- 复用 `players.image_url`，不新增 migration；`init/up` 不批量拉取排名照片。
- 上游无图、身份未知或图片加载失败时只显示中性人像，不显示姓名首字母。
- 不修改市场匹配、模型/预测、Paper 或网球数据事实语义。
- 保留所有预先存在的工作区差异，尤其 `backend/app/service.py` 中 P3 freshness 修改及未跟踪文件。
- 不重启或停止当前本地服务；不读或输出根 `.env`；验证失败需按原样报告，不改用户配置/数据规避。

## Review Focus

- 旧 API 消费方不含 `image_url`：默认 `null`，不得造成 DTO 解码失败。
- standings 不提供图：仅当前排名页缺图条目按需查 profile，超时/错误不影响排名。
- 供应商返空图或坏 URL：中性占位，不发起无界重试。
- 已有目录照片遇到稀疏比赛 feed：空 incoming 值不得清掉缓存照片。
- market-only、双打/复合 outcome 无可靠内部 ID：不按名字模糊套图。

---

### Task 1: Canonicalize and persist provider photos

**Files:**
- Modify: `backend/app/domain.py`
- Modify: `backend/app/providers/api_tennis_dtos.py`
- Modify: `backend/app/providers/api_tennis.py`
- Modify: `backend/app/persistence/repositories.py`
- Modify: `backend/app/persistence/player_directory.py`
- Modify: `backend/app/players/models.py`
- Modify: `backend/app/players/repository.py`
- Test: `backend/tests/test_api_tennis_provider.py`
- Test: `backend/tests/test_runtime_catalog.py`
- Test: `backend/tests/test_player_directory_repository.py`
- Test: `backend/tests/integration/test_player_directory_postgres.py`

**Interfaces:** `Player.image_url: str | None = None`; repository method `upsert_player_images(images: dict[str, str]) -> int`; no database migration because `PlayerRow.image_url` already exists.

- [ ] Add provider tests for `event_first_player_logo` / `event_second_player_logo` mapping to the corresponding canonical players, including null logo and stable player order.
- [ ] Add directory repository tests proving nonempty URLs persist by internal ID, ranking upserts preserve them, and null/empty image updates never erase a known URL.
- [ ] Extend provider DTO and `map_match`; map `PlayerDto.player_logo` into profile/player photo output.
- [ ] Remove redundant `DirectoryPlayer.image_url` storage in favor of `DirectoryPlayer.player.image_url`, updating memory and PostgreSQL projections while preserving profile `image_url` response compatibility.
- [ ] Extend match catalog player upsert/load so feed photos fill `PlayerRow.image_url` with `COALESCE` semantics and round-trip through `Match`.
- [ ] Run focused provider, catalog, player-directory and PostgreSQL integration tests; run Ruff on changed Python files and `git diff --check`.
- [ ] Commit only task files with `feat: persist canonical player photos`.

### Task 2: Hydrate player photos for rankings, profiles and P3 reads

**Files:**
- Modify: `backend/app/service.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/persistence/player_directory.py`
- Test: `backend/tests/test_player_profile_service.py`
- Test: `backend/tests/test_p3_api.py`
- Test: `backend/tests/integration/test_p3_query_service.py`

**Interfaces:** `P3QueryService._match_facts()` returns ordered `player_images` aligned with `player_ids`; public P3 rows expose optional `[str | None, str | None]`. `TennisService.get_rankings_page()` returns the existing `RankingPage` shape with `entry.player.image_url` filled for photos found.

- [ ] Add service tests: only missing images on requested ranking page invoke cached profiles; maximum profile-fetch concurrency is five; a profile failure/empty image still returns the full ranking page; successful image is persisted and reused.
- [ ] Add API/P3 tests: images follow internal player order for mapped markets, opportunities, paper positions and pulse; unmapped market retains null images.
- [ ] Implement page-scoped ranking hydration with `asyncio.Semaphore(5)`, reuse `_load_profile()` cache, save only nonempty provider URLs through directory repository, and return entries hydrated in the same response.
- [ ] On profile view, persist a newly received nonempty image while keeping an existing directory image if provider returns null; directory image takes precedence for all other player fields.
- [ ] Add ordered images to `_match_facts()` and each P3 response constructor without changing any matching/decision calculation.
- [ ] Run focused backend service/API/P3 tests and directory PostgreSQL integration; run Ruff on changed Python files and `git diff --check`.
- [ ] Commit only task files with `feat: expose player photos in API views`.

### Task 3: Add one reusable frontend avatar and wire every player surface

**Files:**
- Create: `frontend/components/player-avatar.tsx`
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/api/p3-types.ts`
- Modify: `frontend/lib/view-models.ts`
- Modify: `frontend/lib/player-view-models.ts`
- Modify: `frontend/lib/p3-view-models.ts`
- Modify: `frontend/components/home/home-match-sections.tsx`
- Modify: `frontend/components/home/home-match-result-card.tsx`
- Modify: `frontend/components/home/home-assistant.tsx`
- Modify: `frontend/components/home/home-player-history.tsx`
- Modify: `frontend/components/home/live-market-pulse.tsx`
- Modify: `frontend/components/home/market-pulse.tsx`
- Modify: `frontend/components/match/match-hero.tsx`
- Modify: `frontend/components/markets/market-row.tsx`
- Modify: `frontend/components/markets/opportunity-row.tsx`
- Modify: `frontend/components/markets/opportunities-view.tsx`
- Modify: `frontend/components/markets/paper-row.tsx`
- Modify: `frontend/components/markets/all-markets-view.tsx`
- Modify: `frontend/components/players/rankings-table.tsx`
- Modify: `frontend/components/players/player-search-results.tsx`
- Modify: `frontend/components/players/player-profile-header.tsx`
- Modify: `frontend/components/players/player-current-status.tsx`
- Modify: `frontend/components/players/player-results.tsx`
- Modify: `frontend/components/players/player-preview-data.ts`
- Modify: `frontend/components/match/match-preview-data.ts`
- Test: `frontend/lib/view-models.test.ts`
- Test: `frontend/lib/player-view-models.test.ts`
- Test: `frontend/lib/p3-view-models.test.ts`
- Test: `frontend/lib/api/p3-types.test.ts`
- Test: `frontend/components/home-page.test.tsx`
- Test: `frontend/components/match-page.test.tsx`
- Test: `frontend/components/markets/markets-page.test.tsx`
- Test: `frontend/components/players/players-page.test.tsx`
- Test: `frontend/components/players/player-profile-page.test.tsx`
- Test: `frontend/components/players/player-results.test.tsx`

**Interfaces:** `PlayerAvatar({name, imageUrl, size, className})`; `PlayerViewModel.avatarUrl`; P3 row view models contain ordered `playerImages`.

- [ ] Add focused component/model expectations: real image renders `AvatarImage`; null/broken image renders neutral `UserRound` fallback and never initials; P3 decoders reject malformed image tuples.
- [ ] Extend frontend API DTOs and strict P3 runtime decoders for `image_url` and `player_images`; map ranking/search/profile/result/match/P3 data to existing view models.
- [ ] Implement `PlayerAvatar` with existing `Avatar` primitives and neutral silhouette; remove duplicated initials helpers from profile/search UI.
- [ ] Use the shared component for Home live/upcoming/finished/structured match cards and player-disambiguation candidates, Match hero, rankings, search, player profile/history/current match, market rows, both opportunity renderers, paper rows, and production/preview Home pulse.
- [ ] Add small headshots beside the two named outcomes in market/paper rows and beside each ranking entry; keep responsive layouts and names readable.
- [ ] Preserve all current preview/live data semantics; static preview entries with no real provider photo use the same silhouette fallback.
- [ ] Run affected frontend Vitest suites and full `pnpm test`, `pnpm typecheck`; run Playwright only against an isolated/local-safe target that does not rebuild or restart the user's running service; inspect global desktop/mobile avatar coverage.
- [ ] Commit only task files with `feat: show player photos across the product`.

### Task 4: Close task records and verify untouched scope

**Files:**
- Modify: `PROJECT.md`
- Modify: `ROADMAP.md`
- Modify: `CURRENT.md`

- [ ] Update the stable product rule: photos are supplier-backed, canonical-ID-bound; missing/ambiguous photos use a neutral fallback.
- [ ] Record implementation commits, actual verification commands/results, unavailable real-browser gates, request/cache behavior, and preserved user worktree changes in the three control documents.
- [ ] Review `git status` and `git diff` to prove known P3 freshness edits and the listed untracked files were not staged or altered by this task; inspect commit file lists.
- [ ] Run `git diff --check`, then push only T104 commits to `origin/main` as required by the repository startup/hand-off rules.
