import { expect, test } from '@playwright/test'

const sourceSkuId = process.env.STOREFRONT_TEST_SKU_ID

test('a published operational SKU appears in the catalogue and on its product page', async ({ page }) => {
  test.skip(!sourceSkuId, 'Set STOREFRONT_TEST_SKU_ID to a published Firstout SKU ID')

  await page.goto('/')
  const productLink = page.locator(`a[href="/product/${sourceSkuId}"]`)
  await expect(productLink).toBeVisible()
  await productLink.click()
  await expect(page).toHaveURL(new RegExp(`/product/${sourceSkuId}$`))
  await expect(page.getByRole('heading', { level: 1 })).not.toBeEmpty()
  await expect(page.locator('.price')).toContainText('R')
  await expect(page.getByRole('status')).toContainText(/available|unavailable/)
})

test('an unknown operational SKU cannot be opened directly', async ({ page }) => {
  const response = await page.goto('/product/00000000-0000-4000-8000-000000000000')
  expect(response?.status()).toBe(404)
})
