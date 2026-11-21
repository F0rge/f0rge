import { expect, test, type Page } from '@playwright/test'

// Runs against the local Medusa fixture (e2e/analytics-medusa-fixture.mjs); see the storefront README.
const tilda = '/product/22222222-2222-4222-8222-222222222222'
const vale = '/product/44444444-4444-4444-8444-444444444444'
const wren = '/product/55555555-5555-4555-8555-555555555555'

const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)
const relatedTitles = (page: Page) => page.getByRole('region', { name: 'More pieces' }).getByRole('heading', { level: 3 }).allTextContents()

test('an in-stock piece shows its facts, caps quantity at stock and adds to the bag', async ({ page }) => {
  await page.goto(tilda)
  const article = page.getByRole('article')
  await expect(article.getByRole('heading', { level: 1 })).toHaveText('Tilda Sofa')
  await expect(article).toContainText('Sofas & Armchairs')
  await expect(page.locator('#product-price')).toHaveText(/^R\s18\s999,00$/)
  await expect(article).toContainText('incl. VAT')
  await expect(page.locator('#product-sku')).toHaveText('SKU TILDA-SOFA')
  await expect(article.getByRole('status')).toHaveText('2 in stock')
  await expect(article.getByRole('definition')).toHaveText(['Bouclé', '220 × 95 × 80 cm'])
  await expect(page.locator('[data-main-image] img')).toHaveAttribute('alt', 'Tilda Sofa, view 1 of 1')

  const increase = page.getByRole('button', { name: 'Increase Quantity' })
  await increase.click()
  await expect(page.getByLabel('Quantity: 2')).toBeVisible()
  await expect(increase).toBeDisabled()

  const added = page.waitForRequest((request) => request.url().endsWith('/api/bag') && request.method() === 'POST')
  await page.getByRole('button', { name: 'Add to bag' }).click()
  expect((await added).postDataJSON()).toEqual({ variant_id: 'variant_tilda_sofa', quantity: 2 })
  const drawer = page.getByRole('dialog', { name: 'Your bag' })
  await expect(drawer.getByLabel('Quantity of Tilda Sofa: 2')).toBeVisible()
  await page.keyboard.press('Escape')

  await expect(page.getByRole('region', { name: 'Delivery and returns' })).toContainText('selected Gauteng areas')
  await expect(page.getByRole('region', { name: 'Delivery and returns' })).toContainText('confirmed in your order total before payment')
  expect((await relatedTitles(page))[0]).toBe('Test chair')
})

test('a made-to-order piece shows its lead time before adding', async ({ page }) => {
  await page.goto(wren)
  const article = page.getByRole('article')
  await expect(article.getByRole('heading', { level: 1 })).toHaveText('Wren Coffee Table')
  await expect(article.getByRole('status')).toHaveText('Made to order · 42–56 days')
  await expect(article).toContainText(/estimated ready between .+\. 3 made-to-order places currently available\./)
  await expect(page.getByRole('button', { name: 'Add to bag' })).toBeEnabled()
  const increase = page.getByRole('button', { name: 'Increase Quantity' })
  await increase.click()
  await increase.click()
  await expect(page.getByLabel('Quantity: 3')).toBeVisible()
  await expect(increase).toBeDisabled()
})

test('a piece without a photo gets a named tile, and related pieces start with its category', async ({ page }) => {
  await page.goto(vale)
  await expect(page.locator('[data-main-image] [data-placeholder]')).toHaveText('Vale Bedside Table')
  await expect(page.getByRole('button', { name: /Show image/ })).toHaveCount(0)
  await expect(page.getByRole('article').getByRole('status')).toHaveText('1 in stock')
  await expect(page.getByRole('button', { name: 'Increase Quantity' })).toBeDisabled()
  // Nothing else is in Bedroom, so related pieces fall back to the rest in catalogue order.
  expect(await relatedTitles(page)).toEqual(['Test chair', 'Tilda Sofa', 'Umbra Dining Table', 'Wren Coffee Table'])
})

test('the gallery and add to bag work from the keyboard', async ({ page }) => {
  await page.goto('/product/11111111-1111-4111-8111-111111111111')
  const second = page.getByRole('button', { name: 'Show image 2 of 2' })
  await second.focus()
  await page.keyboard.press('Enter')
  await expect(second).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('[data-main-image] img')).toHaveAttribute('alt', 'Test chair, view 2 of 2')

  // One unit in stock, so both quantity buttons are disabled and Tab goes straight to Add to bag.
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'Add to bag' })).toBeFocused()
  await page.keyboard.press('Enter')
  const drawer = page.getByRole('dialog', { name: 'Your bag' })
  await expect(drawer.getByRole('heading', { name: 'Test chair' })).toBeVisible()
  await expect.poll(() => drawer.evaluate((element) => element.contains(document.activeElement))).toBe(true)
})

for (const path of [tilda, wren, vale]) {
  test(`${path} fits 390px without horizontal scroll`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(path)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await page.getByRole('region', { name: 'More pieces' }).scrollIntoViewIfNeeded()
    expect(await noHorizontalScroll(page)).toBe(true)
  })
}

test('an unknown piece is not found', async ({ page }) => {
  const response = await page.goto('/product/99999999-9999-4999-8999-999999999999')
  expect(response?.status()).toBe(404)
})
