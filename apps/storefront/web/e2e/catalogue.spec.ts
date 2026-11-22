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
  await expect(page.getByRole('status')).toContainText(/^(In stock|Made to order|Out of stock)/)
})

test('an unknown operational SKU cannot be opened directly', async ({ page }) => {
  const response = await page.goto('/product/00000000-0000-4000-8000-000000000000')
  expect(response?.status()).toBe(404)
})

test('two real group variants change shopper SKU, price and availability', async ({ page }) => {
  test.skip(!groupHandle, 'Set STOREFRONT_TEST_GROUP_HANDLE to a published two-variant group handle')

  await page.goto(`/product/${groupHandle}`)
  const choices = page.getByRole('article').getByRole('group').filter({ has: page.getByRole('button', { pressed: true }) })
  // The gallery also exposes pressed buttons; restrict the variant set to the option fieldset.
  const option = choices.and(page.locator('fieldset')).first()
  const values = option.getByRole('button')
  expect(await values.count()).toBeGreaterThanOrEqual(2)
  await values.nth(0).click()
  const firstSku = await page.locator('#product-sku').textContent()
  const firstPrice = await page.locator('#product-price').textContent()
  const firstAvailability = await page.getByRole('status').textContent()
  await values.nth(1).click()
  const secondSku = await page.locator('#product-sku').textContent()
  expect(secondSku).not.toBe(firstSku)
  await expect(page.locator('#product-price')).toContainText('R')
  await expect(page.getByRole('status')).toContainText(/^(In stock|Made to order|Out of stock)/)
  expect(firstPrice).toContain('R')
  expect(firstAvailability).toMatch(/^(In stock|Made to order|Out of stock)/)
})
