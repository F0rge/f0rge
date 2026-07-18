import { expect, test } from '@playwright/test'

test('signup → check-in golden path', async ({ page }) => {
  const stamp = Date.now()
  const email = `e2e-${stamp}@example.com`
  const password = 'e2e-password-12'
  const handle = `e2e_${stamp}`

  await page.goto('/signup')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Handle').fill(handle)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page).toHaveURL(/\/checkin/, { timeout: 30_000 })
  await expect(page.getByTestId('checkin-header')).toBeVisible({ timeout: 30_000 })
})
