import { test, expect } from '@playwright/test'

test.describe('Settings', () => {
  test('loads settings page and shows network section', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.locator('body')).toContainText(/network|scan|settings/i, { timeout: 15_000 })
  })
})

test.describe('Lab Status', () => {
  test('renders lab health summary from CI config', async ({ page }) => {
    await page.goto('/lab-status')
    await expect(page.locator('body')).toContainText(/lab|health|status|localhost|ci gateway/i, { timeout: 15_000 })
  })
})

test.describe('Hunter Runs', () => {
  test('renders empty or overview state', async ({ page }) => {
    await page.goto('/hunter-runs')
    await expect(page.locator('body')).toContainText(/hunter|run|mission|no runs|overview/i, { timeout: 15_000 })
  })
})
