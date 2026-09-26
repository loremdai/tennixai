# T105 全站球员双语姓名展示实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全站结构化球员身份统一显示英文主名、可用的中文辅名，并让 P3 API 明确分开传递两种名称。

**Architecture:** 复用现有 canonical `Player.name` / `localized_name`，不改身份或翻译服务。P3 公共 DTO 明确以 `player_names` 传英文主名，并增加 `player_localized_names`；前端以一个共享 `PlayerName` 呈现两行姓名，并贯通已有 player/match/market view model。

**Tech Stack:** Python 3、FastAPI/Pydantic、PostgreSQL 既有玩家目录；Next.js、TypeScript、React、Vitest、Playwright。

**Spec:** [T105 设计规格](../specs/2026-09-26-tennixai-t105-global-bilingual-player-names-design.md)

## Global Constraints

- 只修改姓名展示和 P3 名称响应字段；禁止改变比分、市场报价、模型判断、机会筛选、Paper 语义或 player ID 关联。
- 中文名缺失时只显示英文；未映射市场只显示供应商给出的 outcome label，不推测翻译。
- AI 自然语言回答不重写；结构化球员字段和卡片需统一。
- 不新增依赖、数据库 migration、供应商/LLM 请求；不读取或输出根 `.env`。
- 工作于 `main`；只暂存 T105 文件，不纳入用户已有工作区改动。

## Review Focus

- 新增中文名 tuple 与 `player_ids` / `player_names` 顺序错位：在后端 query-service 测试中以反向 outcome 顺序验证。
- 空中文名导致空白第二行：在共享组件测试中验证 null 与空白字符串均隐藏。
- market-only 行被错误归入球员目录：在 P3 service 测试中验证供应商名保留且中文为 null。
- 旧 P3 响应暂缺新增键：在 runtime decoder 测试中验证返回 null 而不是解码失败。
- 两行姓名挤压窄视口比分/市场卡：使用现有桌面和移动 Playwright 页面检查，避免改变比赛比分字段布局。

---

### Task 1: 将英文名和中文名作为独立的 P3 API 字段

**Files:**
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/service.py`
- Test: `backend/tests/integration/test_p3_query_service.py`
- Test: `backend/tests/test_p3_api.py`
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/api/p3-types.ts`
- Test: `frontend/lib/api/p3-types.test.ts`

**Interfaces:**
- `player_names: tuple[str, str] | None` 是 canonical English 名称；
- 新增 `player_localized_names: tuple[str | None, str | None] | None`，顺序与 `player_ids` 一致；
- `P3QueryService._match_facts()` 同时提供 `player_names` 和 `player_localized_names`。

- [ ] 先扩展集成测试：给已有两名玩家写入中英文名，再对 `markets()` 返回项断言 `player_names == ("Player A", "Player B")`、中文 tuple 与 `player_ids` 相同顺序；对机会、Paper、Pulse 增加相同顺序断言。

```python
assert summary2.player_names == ("Player A", "Player B")
assert summary2.player_localized_names == ("甲球员", "乙球员")
```

- [ ] 在后端 `test_p3_api.py` 中断言新增的 tuple 以 JSON 二元组原顺序返回；在前端 decoder 测试中断言可空中文名、缺键兼容和畸形长度/元素仍失败。
- [ ] 运行 RED：`cd backend && uv run pytest tests/integration/test_p3_query_service.py::test_enriched_fields_and_pulse_selection tests/test_p3_api.py -q`；预期新增英文/中文断言失败，因为服务目前中文优先且 DTO 无新字段。
- [ ] 实现 `player_localized_names` schema/type；`_match_facts()` 分别按目录行 `name` / `localized_name` 建映射，所有 P3 response 构造器以同一 outcome 顺序填充两组名称。未映射 outcome 只使用供应商标签，不追加推断中文。
- [ ] 在 `frontend/lib/api/p3-types.ts` 增加 null-safe 二元组解码；缺字段按 `null` 处理以兼容旧响应，但畸形数组继续抛 `P3DecodeError`。
- [ ] 运行 GREEN：`cd backend && uv run pytest tests/integration/test_p3_query_service.py::test_enriched_fields_and_pulse_selection tests/test_p3_api.py -q`，以及 `cd frontend && ./node_modules/.bin/vitest run lib/api/p3-types.test.ts`；预期通过。

### Task 2: 建立共享双语姓名组件并统一页面 view model

**Files:**
- Create: `frontend/components/player-name.tsx`
- Test: `frontend/components/player-name.test.tsx`
- Modify: `frontend/lib/view-models.ts`
- Test: `frontend/lib/view-models.test.ts`
- Modify: `frontend/lib/player-view-models.ts`
- Test: `frontend/lib/player-view-models.test.ts`
- Modify: `frontend/lib/p3-view-models.ts`
- Test: `frontend/lib/p3-view-models.test.ts`

**Interfaces:**
- `PlayerName({ name, localizedName, className, primaryClassName, secondaryClassName })` 输出英文主名与可选中文辅名；
- `PlayerViewModel.nameZh` 来自 DTO 的 `localized_name`；
- P3 row model 保留两名对齐 tuple，不将两种语言预先拼成一个字符串。

- [ ] 先写共享组件测试：

```tsx
render(<PlayerName name="Jannik Sinner" localizedName="扬尼克·辛纳" />)
expect(screen.getByText('Jannik Sinner')).toBeVisible()
expect(screen.getByText('扬尼克·辛纳')).toBeVisible()
```

- [ ] 再断言 `localizedName={null}` 与 `localizedName="  "` 都不渲染中文节点；运行 `cd frontend && ./node_modules/.bin/vitest run components/player-name.test.tsx`，确认因组件缺失/行为缺失而失败。
- [ ] 实现最小共享组件，不引入依赖：英文名始终是第一行；trim 后非空中文名才输出第二行；支持 primary/secondary className 以适配现有字体层级。
- [ ] 在 `view-models.test.ts` 断言 `toMatchViewModel()` 保留 `PlayerDto.localized_name`；在 `p3-view-models.test.ts` 断言两种名称数组映射到各自 player index，目标球员仍由 `player_ids` 解析。
- [ ] 将 `nameZh` 映射进 match/home `PlayerViewModel`；P3 row view model 保留英文和中文 pair，不提前拼字符串。
- [ ] 运行 GREEN：`cd frontend && ./node_modules/.bin/vitest run components/player-name.test.tsx lib/view-models.test.ts lib/player-view-models.test.ts lib/p3-view-models.test.ts`；预期通过。

### Task 3: 贯通 Home 与 Match 的结构化球员显示

**Files:**
- Modify: `frontend/components/home/home-match-sections.tsx`, `frontend/components/home/home-match-result-card.tsx`, `frontend/components/home/home-assistant.tsx`, `frontend/components/home-player-history.tsx`
- Modify: `frontend/components/match-page.tsx`, `frontend/components/match/match-preview-data.ts`, `frontend/components/match/probability-market-trajectory.tsx`, `frontend/components/match/match-hero.tsx`, `frontend/components/match/match-main.tsx`, `frontend/components/match/match-sidebar.tsx`, `frontend/components/match/match-points.tsx`, `frontend/components/match/match-statistics.tsx`, `frontend/components/match/match-momentum.tsx`, `frontend/components/match/decision-summary.tsx`, `frontend/components/match/decision-summary-live.tsx`
- Modify: `frontend/lib/p3-workbench-models.ts`
- Test: `frontend/components/home-page.test.tsx`, `frontend/components/match-page.test.tsx`, `frontend/components/match-decision-page.test.tsx`, and `frontend/lib/p3-workbench-models.test.ts`

- [ ] Add a Home structured match assertion and a Match score/decision assertion. Each proves both strings render in one player region, for example:

```tsx
expect(within(playerRow).getByText('Jannik Sinner')).toBeVisible()
expect(within(playerRow).getByText('扬尼克·辛纳')).toBeVisible()
```

- [ ] Run RED: `cd frontend && ./node_modules/.bin/vitest run components/home-page.test.tsx components/match-page.test.tsx components/match-decision-page.test.tsx lib/p3-workbench-models.test.ts`; confirm failure specifically on missing localized-name nodes.
- [ ] Map `PlayerDto.localized_name` through Home/Match models already updated in Task 2. Replace player-name JSX in Home match/result/history/candidate cards and Match hero, preview/live score rows, point winners, statistics, momentum, key facts, trajectory preview and selected-player summary with `PlayerName`. Use existing preview translations for the two preview players; do not add new translations.
- [ ] Keep existing English short labels only where the score/event layout is compact; render localized name beneath them when present. Preserve match order, server indicators, score columns, all decision text and natural-language AI answers.
- [ ] Pass the selected player's localized name separately from `match-page.tsx` to `toDecisionSummaryModel`; render the structured “关注球员” field with `PlayerName`. Keep generated/templated prose as existing English-primary text rather than concatenating Chinese into sentences.
- [ ] Run GREEN with the same Vitest command; confirm the Home/Match regression assertions pass.

### Task 4: 贯通 Markets、Opportunities、Paper 与 Home 市场脉搏

**Files:**
- Modify: `frontend/components/home/live-market-pulse.tsx`, `frontend/components/home/market-pulse.tsx`
- Modify: `frontend/components/markets/markets-state.tsx`, `frontend/components/markets/market-row.tsx`, `frontend/components/markets/all-markets-view.tsx`, `frontend/components/markets/opportunity-row.tsx`, `frontend/components/markets/opportunities-view.tsx`, `frontend/components/markets/paper-row.tsx`
- Test: `frontend/components/home/market-pulse.test.tsx`, `frontend/components/markets/markets-page.test.tsx`

- [ ] Add regression assertions that a known P3 market/pulse/paper row shows English and localized names for both players, while an unmatched provider outcome shows only its supplied label.
- [ ] Run RED: `cd frontend && ./node_modules/.bin/vitest run components/home/market-pulse.test.tsx components/markets/markets-page.test.tsx`; confirm the missing localized-name assertions fail.
- [ ] Pass `player_localized_names` from the P3 DTO through row models created in Task 2; keep each Chinese name aligned by index with its English name, internal player ID, and existing image URL.
- [ ] Replace English-only player and target-selection labels in Home market pulse, All Markets, Opportunities and Paper cards with `PlayerName`; do not derive a localized name from the market question or provider label.
- [ ] Run GREEN using the same focused test command; verify model values, quote values, state labels, and row navigation remain unchanged.

### Task 5: 贯通球员目录、资料和历史记录

**Files:**
- Modify: `frontend/components/players/rankings-table.tsx`, `frontend/components/players/player-search-results.tsx`, `frontend/components/players/player-profile-header.tsx`, `frontend/components/players/player-current-status.tsx`, `frontend/components/players/player-results.tsx`
- Test: `frontend/components/players/players-page.test.tsx`, `frontend/components/players/player-profile-page.test.tsx`, `frontend/components/players/player-results.test.tsx`

- [ ] Add one ranking/search assertion and one profile/history assertion proving English primary and Chinese secondary are visible.
- [ ] Run RED: `cd frontend && ./node_modules/.bin/vitest run components/players/players-page.test.tsx components/players/player-profile-page.test.tsx components/players/player-results.test.tsx`; confirm the new component-level display assertions fail.
- [ ] Replace existing duplicated markup in ranking, search, profile, current-opponent and history-result cards with `PlayerName`; keep existing aria-labels descriptive and avoid duplicate spoken labels.
- [ ] Run GREEN with the same command; verify missing localized names still leave a readable English-only row.

### Task 6: Close T105 and preserve unrelated work

**Files:**
- Modify: `PROJECT.md`, `ROADMAP.md`, `CURRENT.md`

- [ ] Record the global English-primary/Chinese-secondary rule in PROJECT; mark T105 done in ROADMAP and CURRENT only after verification.
- [ ] Run complete frontend Vitest (`cd frontend && pnpm test`), typecheck (`cd frontend && pnpm typecheck`), and existing relevant Playwright desktop/mobile routes against the running local app. Inspect actual/expected/diff and update only intentional visual snapshots.
- [ ] Record commits, exact test counts, browser/device coverage, restart outcome, and any gates not run. Do not call unrun checks passed.
- [ ] Review staged diff and commit file lists; confirm pre-existing `backend/app/service.py` freshness hunks and the documented untracked files remain outside T105 commits.
- [ ] Run `git diff --check`, push T105 commits to `origin/main`, then verify `git status --short --branch` and remote HEAD.
