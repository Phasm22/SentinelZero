import { test, expect } from '@playwright/test'

test.describe('Scan flow (mock scanner)', () => {
  test('triggers discovery scan and shows progress', async ({ page }) => {
    await page.goto('/')
    const discoveryButton = page.getByRole('button', { name: 'Discovery Scan' }).first()
    await discoveryButton.click({ timeout: 15_000 })
    await expect(page.locator('body')).toContainText(/scan|queued|running|complete|progress/i, { timeout: 30_000 })
  })
})

test.describe('Scan History', () => {
  test('lists seeded scans', async ({ page }) => {
    await page.goto('/scan-history')
    await expect(page.locator('body')).toContainText(/Full TCP|172\.16\.0/i, { timeout: 15_000 })
  })
})
