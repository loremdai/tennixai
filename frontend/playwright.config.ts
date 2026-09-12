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
        const realProvider =
          configuredEnvironment.TENNIX_E2E_REAL_PROVIDER === '1' &&
          Boolean(configuredEnvironment.TENNIX_LIVETENNIS_API_KEY)
        const realLlm =
          configuredEnvironment.TENNIX_E2E_REAL_LLM === '1' &&
          Boolean(configuredEnvironment.TENNIX_LLM_API_KEY) &&
          Boolean(configuredEnvironment.TENNIX_LLM_BASE_URL)
        return {
          ...configuredEnvironment,
          TENNIX_PROVIDER_MODE: replayEnabled ? 'replay' : realProvider ? 'live' : 'fake',
          TENNIX_LLM_MODE: realLlm ? 'openai_compatible' : 'fake',
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
      reuseExistingServer: !process.env.CI && !replayEnabled,
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
