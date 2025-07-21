import { test, expect } from '@playwright/test'

const baseUrl = process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:5173'

test.describe('SentinelZero Dashboard', () => {
  test('should load the dashboard and display the title', async ({ page }) => {
    await page.goto(baseUrl)
    await expect(page.getByTestId('main-header-title')).toHaveText(/SentinelZero/i)
  })
}) 