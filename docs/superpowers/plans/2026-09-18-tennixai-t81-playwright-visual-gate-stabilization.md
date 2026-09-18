# T81 Playwright 视觉门并行稳定性收口计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Preserve the approved visual baselines; do not use `--update-snapshots` unless the user separately approves a reviewed visual change.

**Goal:** 让默认 `pnpm test:e2e` 在不改变产品 UI、快照基线或断言宽容度的前提下稳定通过：功能 E2E 仍可并行，所有像素快照测试在独立的串行通道执行。

**Architecture:** 使用 Playwright 原生 `@visual` tag 标记全部 `toHaveScreenshot` 测试；`package.json` 将默认 E2E 拆为两个顺序启动的 Playwright 进程：先运行排除 `@visual` 的功能门，再以 `--workers=1` 运行全部 `@visual` 门。第二个进程只会在第一个完成后启动，因此视觉渲染既不会与功能浏览器并发，也不会与另一张视觉快照并发。保留现有 desktop/mobile projects、假数据默认模式、测试断言和所有 PNG 基线。

**Why this boundary:** 2026-09-18 后验复跑中，完整 suite 两次均只在 mobile `home-answer` 快照失败（265 像素）；相同用例单独串行重复 10 次全部通过，且 P4.1 关闭后影响路径没有产品代码变更。`fullyParallel: false` 不会禁止不同文件的并行 worker；Playwright 官方文档确认默认按文件并行、`--workers=1` 才会关闭并行，且 tag 可由 `--grep` / `--grep-invert` 选择。[Parallelism](https://playwright.dev/docs/test-parallel) · [Tags](https://playwright.dev/docs/test-annotations)

## Scope and non-goals

- 只改 `frontend/e2e` 的测试元数据与 `frontend/package.json` 的运行命令；不改组件、CSS、Next.js 配置、FastAPI、真实运行时或 P1–P4 产品语义。
- 不更新、删除、mask、裁剪或重录任何 `frontend/e2e/__screenshots__` PNG。
- 不调高 `maxDiffPixels` / `maxDiffPixelRatio` / screenshot threshold，不隐藏产品 Header，不把失败标记为 `skip` / `fixme`，也不以重试掩盖问题。
- 不运行会消耗 LLM / API-Tennis / Polymarket 配额的 live gate；本任务只验证确定性 fake E2E。
- 已知未跟踪 `.codex/`、`.superpowers/`、`REALTIME_LATENCY_INVESTIGATION.md`、`frontend/next-env.d.ts` 必须原样保留。

## File map

| File | Change |
|---|---|
| `frontend/e2e/prototype.visual.spec.ts` | 为五个原型快照测试加组级 `@visual` tag。 |
| `frontend/e2e/p1.visual.spec.ts` | 为六个 P1 快照测试加组级 `@visual` tag。 |
| `frontend/e2e/p2.visual.spec.ts` | 为 P2 replay 快照 describe 加 `@visual` tag；其 replay-off skip 语义不变。 |
| `frontend/e2e/p3.visual.spec.ts` | 为 P3 三组 capture 测试加 `@visual` tag。 |
| `frontend/e2e/player-directory.visual.spec.ts` | 为两个 Player 快照测试加组级 `@visual` tag。 |
| `frontend/e2e/home-history.spec.ts` | 只给现有 `Home history visual` describe 加 `@visual` tag；同文件两个功能测试不加。 |
| `frontend/package.json` | 新增功能/视觉两个显式命令，并让默认 E2E 顺序运行它们。 |
| `PROJECT.md` / `ROADMAP.md` / `CURRENT.md` | 记录 T81 的范围、计划、完成证据和交接状态。 |

## Task 1 — T81: Give every screenshot test an explicit visual identity

**Files:**

- Modify: `frontend/e2e/prototype.visual.spec.ts`
- Modify: `frontend/e2e/p1.visual.spec.ts`
- Modify: `frontend/e2e/p2.visual.spec.ts`
- Modify: `frontend/e2e/p3.visual.spec.ts`
- Modify: `frontend/e2e/player-directory.visual.spec.ts`
- Modify: `frontend/e2e/home-history.spec.ts`

**Implementation:**

1. Before editing, prove that the tag lane does not yet exist:

   ```bash
   cd frontend
   pnpm exec playwright test --list --grep @visual
   ```

   Expected: no selected tests, because no current test owns the tag.

2. Add a group-level native Playwright tag without changing any test title, route, readiness wait, screenshot option, project, or PNG name. Use the supported details-object form:

   ```ts
   test.describe('P3 visual preview baselines', { tag: '@visual' }, () => {
     // existing tests unchanged
   })
   ```

   Wrap the top-level generator loops in `prototype.visual.spec.ts`, `p1.visual.spec.ts`, and `player-directory.visual.spec.ts` in equivalent `test.describe(..., { tag: '@visual' }, () => { ... })` blocks. Add the details object to the existing P2, P3, and Home-history visual describes. Do not tag `Home history answer` functional coverage.

3. Confirm selection rather than trusting file names:

   ```bash
   pnpm exec playwright test --list --grep @visual
   pnpm exec playwright test --list --grep-invert @visual
   ```

   The visual list must contain only the six known screenshot surfaces above (19 test declarations × desktop/mobile projects; P2 replay cases may still be skipped when replay is off). The inverse list must retain all ordinary browser flows, including the functional tests in `home-history.spec.ts`.

4. Run the tagged lane directly, serially, without updating snapshots:

   ```bash
   pnpm exec playwright test --grep @visual --workers=1
   ```

   Expected under the current deterministic configuration: `34 passed, 4 skipped, 0 failed`. If it fails, stop at the failure artifact and diagnose it; do not advance to Task 2 by weakening an assertion.

5. Commit only the test metadata after the focused proof:

   ```bash
   git add frontend/e2e
   git commit -m "test: tag visual e2e baselines"
   ```

## Task 2 — T81: Split the default command into an isolated functional lane and a serial visual lane

**Files:**

- Modify: `frontend/package.json`

**Implementation:**

1. Establish the red boundary: `pnpm run test:e2e:functional` and `pnpm run test:e2e:visual` do not exist before this change.

2. Replace the single default script with these commands exactly (retain `test:e2e:update`, but confine it to the serial visual lane):

   ```json
   {
     "test:e2e:functional": "playwright test --grep-invert @visual",
     "test:e2e:visual": "playwright test --grep @visual --workers=1",
     "test:e2e": "pnpm run test:e2e:functional && pnpm run test:e2e:visual",
     "test:e2e:update": "pnpm run test:e2e:visual -- --update-snapshots"
   }
   ```

   This is intentionally two CLI invocations, not merely `test.describe.configure({ mode: 'serial' })`: separate process lifecycles guarantee that visual browsers do not overlap with functional browser workers. Do not change `playwright.config.ts`; existing two viewports and `fullyParallel: false` remain correct.

3. Prove lane separation with normal commands:

   ```bash
   pnpm run test:e2e:functional
   pnpm run test:e2e:visual
   ```

   Expected baseline counts are `76 passed, 40 skipped, 0 failed` for the functional lane and `34 passed, 4 skipped, 0 failed` for the visual lane. A changed count requires explaining which test moved; it is not permission to tag a functional test just to make counts match.

4. Commit the runner boundary:

   ```bash
   git add frontend/package.json
   git commit -m "test: isolate serial visual e2e lane"
   ```

## Task 3 — T81: Prove stability, preserve visual truth, and close the task

**Files:**

- Modify: `PROJECT.md`
- Modify: `ROADMAP.md`
- Modify: `CURRENT.md`

**Implementation and gates:**

1. Use the repository's Node 22 / pnpm 10 toolchain. If a shell-provided pnpm rejects the existing `node_modules`, locate the configured fnm Node 22 toolchain; do not reinstall, delete, or rewrite dependencies as a workaround.

2. Run the affected frontend verification in this order:

   ```bash
   cd frontend
   pnpm test
   pnpm typecheck
   pnpm build
   pnpm run test:e2e:visual
   pnpm test:e2e
   pnpm test:e2e
   git diff --exit-code -- e2e/__screenshots__
   cd ..
   git diff --check
   git status --short
   ```

   Both full invocations must finish `110 passed, 44 skipped, 0 failed`; the two sub-lane totals must reconcile exactly to that result. A visual PNG diff, a single remaining flaky failure, or an accidental snapshot update blocks completion.

3. Update controls with only verified facts:

   - `PROJECT.md`: P4.1 remains a historical closed runtime milestone; add that T81 is a non-product visual-gate follow-up, not a reopening of the real-runtime design.
   - `ROADMAP.md`: set T81 `done`, cite the implementation commit(s), the isolated-before/serial-after diagnosis, both full successful runs, and explicit zero PNG changes.
   - `CURRENT.md`: return to no active task; retain the protected untracked-file list and show the actual commands/counts. Keep at most five recent entries.

4. Perform a final secret/scope check before committing:

   ```bash
   git diff --check
   git diff --name-only
   git status --short
   ```

   The intended tracked changes are only the six E2E specs, `frontend/package.json`, and the three control documents. Never stage `.env`, a screenshot PNG, test artifacts, or the protected untracked files.

5. Commit, push, and report the actual output:

   ```bash
   git add PROJECT.md ROADMAP.md CURRENT.md frontend/e2e frontend/package.json
   git commit -m "test: stabilize visual e2e gate"
   git push origin main
   ```

**Completion condition:** The default command is green twice in a row with the approved snapshots byte-for-byte unchanged, and controls accurately distinguish the historical P4.1 runtime closure from this independent test-harness hardening task.
