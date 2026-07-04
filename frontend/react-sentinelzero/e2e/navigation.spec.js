import { test, expect } from '@playwright/test'

test.describe('Dashboard', () => {
  test('loads with seeded scan stats', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /dashboard|sentinel/i }).first()).toBeVisible({ timeout: 15_000 })
    await expect(page.locator('body')).toContainText(/scan|host|network/i)
  })
})

test.describe('Navigation', () => {
  test('visits main routes', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('link', { name: 'Scan History' }).click()
    await expect(page).toHaveURL(/scan-history/)
    await page.getByRole('link', { name: 'Lab Status' }).click()
    await expect(page).toHaveURL(/lab-status/)
    await page.getByRole('link', { name: 'Settings' }).click()
    await expect(page).toHaveURL(/settings/)
    await page.getByRole('link', { name: 'Hunter Runs' }).click()
    await expect(page).toHaveURL(/hunter-runs/)
  })
})
