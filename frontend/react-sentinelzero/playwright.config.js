import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 60_000,
  use: {
    baseURL: 'http://127.0.0.1:5000',
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
      url: 'http://127.0.0.1:5000/healthz',
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
})
