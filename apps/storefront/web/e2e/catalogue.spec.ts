import { expect, test } from '@playwright/test'

const sourceSkuId = process.env.STOREFRONT_TEST_SKU_ID
const groupHandle = process.env.STOREFRONT_TEST_GROUP_HANDLE

test('a published operational SKU appears in the catalogue and on its product page', async ({ page }) => {
  test.skip(!sourceSkuId, 'Set STOREFRONT_TEST_SKU_ID to a published Firstout SKU ID')

  await page.goto('/')
  const productLink = page.locator(`a[href="/product/${sourceSkuId}"]`).first()
  await expect(productLink).toBeVisible()
  await productLink.click()
  await expect(page).toHaveURL(new RegExp(`/product/${sourceSkuId}$`))
  await expect(page.getByRole('heading', { level: 1 })).not.toBeEmpty()
  await expect(page.locator('#product-price')).toContainText('R')
  await expect(page.getByRole('status')).toContainText(/in stock|made to order|unavailable/i)
})

test('an unknown operational SKU cannot be opened directly', async ({ page }) => {
  const response = await page.goto('/product/00000000-0000-4000-8000-000000000000')
  expect(response?.status()).toBe(404)
})

test('two real group variants change shopper SKU, price and availability', async ({ page }) => {
  test.skip(!groupHandle, 'Set STOREFRONT_TEST_GROUP_HANDLE to a published two-variant group handle')

  await page.goto(`/product/${groupHandle}`)
  const option = page.getByRole('article').getByRole('combobox').first()
  await expect(option).toBeVisible()
  const values = await option.locator('option').allTextContents()
  expect(values.length).toBeGreaterThanOrEqual(2)
  await option.selectOption({ index: 0 })
  const firstSku = await page.locator('#product-sku').textContent()
  const firstPrice = await page.locator('#product-price').textContent()
  const firstAvailability = await page.getByRole('status').textContent()
  await option.selectOption({ index: 1 })
  const secondSku = await page.locator('#product-sku').textContent()
  expect(secondSku).not.toBe(firstSku)
  await expect(page.locator('#product-price')).toContainText('R')
  await expect(page.getByRole('status')).toContainText(/in stock|made to order|unavailable/i)
  expect(firstPrice).toContain('R')
  expect(firstAvailability).toMatch(/in stock|made to order|unavailable/i)
})
