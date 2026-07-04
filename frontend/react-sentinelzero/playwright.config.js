import { defineConfig, devices } from '@playwright/test'

const E2E_PORT = process.env.SENTINEL_E2E_PORT || '5099'
const E2E_BASE_URL = `http://127.0.0.1:${E2E_PORT}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 60_000,
  use: {
    baseURL: E2E_BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'npm run build',
      cwd: '.',
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'cd ../../backend && uv run python scripts/e2e_server.py',
      url: `${E2E_BASE_URL}/healthz`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
})
