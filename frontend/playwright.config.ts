import { defineConfig } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parseEnv } from 'node:util'

const rootEnvironmentFile = resolve(__dirname, '../.env')
let rootEnvironment: Record<string, string | undefined> = {}
try {
  rootEnvironment = parseEnv(readFileSync(rootEnvironmentFile, 'utf8'))
} catch (error) {
  if (!(error instanceof Error && 'code' in error && error.code === 'ENOENT')) throw error
}
const configuredEnvironment = { ...rootEnvironment, ...process.env }
const replayEnabled = configuredEnvironment.TENNIX_E2E_REPLAY === '1'
const replayIdentityNamespace =
  configuredEnvironment.TENNIX_REPLAY_IDENTITY_NAMESPACE ??
  (replayEnabled ? `replay-e2e-${Date.now()}` : 'replay')

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 0,
  // Dev-machine CPU contention (shared with the user's browser) can stretch
  // first-paint and `load` far beyond defaults; timeouts are infrastructure
  // headroom only and never relax an assertion or snapshot.
  timeout: 180_000,
  expect: { timeout: 30_000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:3100',
    colorScheme: 'dark',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  snapshotPathTemplate: '{testDir}/__screenshots__/{projectName}/{arg}{ext}',
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: [
    {
      cwd: '../backend',
      command: 'uv run uvicorn app.main:app --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/api/v1/health',
      env: (() => {
        // TENNIX_E2E_API_TENNIS=1 selects the real API-Tennis directory mode
        // for the bounded live directory gate; TENNIX_E2E_REAL_PROVIDER=1 keeps
        // the legacy P1 LiveTennisAPI selection.
        const apiTennis =
          configuredEnvironment.TENNIX_E2E_API_TENNIS === '1' &&
          Boolean(configuredEnvironment.TENNIX_API_TENNIS_API_KEY)
        const realProvider =
          (configuredEnvironment.TENNIX_E2E_REAL_PROVIDER === '1' &&
            Boolean(configuredEnvironment.TENNIX_LIVETENNIS_API_KEY)) ||
          apiTennis
        const realLlm =
          configuredEnvironment.TENNIX_E2E_REAL_LLM === '1' &&
          Boolean(configuredEnvironment.TENNIX_LLM_API_KEY) &&
          Boolean(configuredEnvironment.TENNIX_LLM_BASE_URL)
        // P4.1 spec §11: Playwright keeps its own explicit isolated config; the
        // launcher never rewrites it, and the default deterministic suite never
        // inherits the developer's local runtime mode choices from the root
        // `.env` (which may now legitimately carry TENNIX_P3_MODE=paper /
        // TENNIX_PROVIDER_MODE=api_tennis / TENNIX_LOCAL_RUNTIME_* for
        // ./scripts/tennix-live). TENNIX_PROVIDER_MODE/TENNIX_LLM_MODE below are
        // already computed purely from the explicit TENNIX_E2E_* opt-in flags,
        // never read back from the root `.env`; P3 mode and the local-runtime
        // role follow the same rule here. Only an explicit per-invocation
        // override (set directly in this command's own environment, e.g.
        // e2e/p3-live.spec.ts's documented `TENNIX_P3_MODE=shadow` gate) may
        // select a non-default value; anything inherited solely from the root
        // `.env` is pinned back to the deterministic default the suite's
        // assertions (e.g. the honest p3_disabled panel in
        // e2e/p3-markets.spec.ts, whose server-side probe cannot be
        // intercepted) were written against. Credentials are untouched and
        // still flow through `...configuredEnvironment` for opt-in live specs;
        // only MODE variables are pinned here.
        const p3Mode = process.env.TENNIX_P3_MODE ?? 'disabled'
        const localRuntimeRole = process.env.TENNIX_LOCAL_RUNTIME_ROLE ?? 'off'
        return {
          ...configuredEnvironment,
          TENNIX_PROVIDER_MODE: replayEnabled
            ? 'replay'
            : apiTennis
              ? 'api_tennis'
              : realProvider
                ? 'live'
                : 'fake',
          TENNIX_LLM_MODE: realLlm ? 'openai_compatible' : 'fake',
          TENNIX_P3_MODE: p3Mode,
          TENNIX_LOCAL_RUNTIME_ROLE: localRuntimeRole,
          ...(replayEnabled
            ? {
                TENNIX_REPLAY_SPEED: configuredEnvironment.TENNIX_REPLAY_SPEED ?? '1',
                TENNIX_REPLAY_IDENTITY_NAMESPACE: replayIdentityNamespace,
                TENNIX_REDIS_URL:
                  configuredEnvironment.TENNIX_E2E_REDIS_URL ?? 'redis://127.0.0.1:6379/10',
              }
            : {}),
          ...(realProvider ? {} : { TENNIX_FIXED_NOW: '2026-09-08T10:00:00Z' }),
        }
      })(),
      reuseExistingServer:
        !process.env.CI &&
        !replayEnabled &&
        process.env.TENNIX_E2E_API_TENNIS !== '1',
    },
    {
      command: 'pnpm dev --hostname 127.0.0.1 --port 3100',
      url: 'http://127.0.0.1:3100',
      env: {
        ...process.env,
        TENNIX_BACKEND_URL:
          configuredEnvironment.TENNIX_BACKEND_URL ?? 'http://127.0.0.1:8000',
      },
      reuseExistingServer: !process.env.CI,
    },
  ],
})
