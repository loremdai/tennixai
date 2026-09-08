import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 0,
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
      env: {
        ...process.env,
        TENNIX_PROVIDER_MODE: 'fake',
        TENNIX_LLM_MODE: 'fake',
        TENNIX_FIXED_NOW: '2026-09-08T10:00:00Z',
      },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'pnpm dev --hostname 127.0.0.1 --port 3100',
      url: 'http://127.0.0.1:3100',
      env: { ...process.env, TENNIX_BACKEND_URL: 'http://127.0.0.1:8000' },
      reuseExistingServer: !process.env.CI,
    },
  ],
})
