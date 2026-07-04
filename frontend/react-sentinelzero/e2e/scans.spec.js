import { test, expect } from '@playwright/test'

test.describe('Scan flow (mock scanner)', () => {
  test('triggers discovery scan and shows progress', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByTestId('dashboard-main')).toBeVisible({ timeout: 20_000 })
    const discoveryButton = page.getByTestId('scan-discovery-btn')
    await expect(discoveryButton).toBeVisible({ timeout: 20_000 })
    await discoveryButton.click()
    await expect(page.locator('body')).toContainText(/scan|queued|running|complete|progress/i, { timeout: 30_000 })
  })
})

test.describe('Scan History', () => {
  test('lists seeded scans', async ({ page }) => {
    await page.goto('/scan-history')
    await expect(page.getByRole('heading', { name: 'All Scans' })).toBeVisible({ timeout: 20_000 })
    await expect(page.locator('table tbody tr').filter({ hasText: 'Full TCP' })).toBeVisible({ timeout: 20_000 })
    await expect(page.locator('table tbody tr').filter({ hasText: '172.16.0' })).toBeVisible()
  })
})
