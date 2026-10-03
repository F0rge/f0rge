import { expect, test } from '@playwright/test'

const sourceSkuId = process.env.STOREFRONT_TEST_SKU_ID
const otherSkuId = process.env.STOREFRONT_TEST_OTHER_SKU_ID
const draftSkuId = process.env.STOREFRONT_TEST_DRAFT_SKU_ID
const groupHandle = process.env.STOREFRONT_TEST_GROUP_HANDLE

function parseRandAmount(label: string): number {
  return Number(label.replace(/[^\d,]/g, '').replace(',', '.'))
}

test('published catalogue filters compose and price sorting orders real products', async ({ page }) => {
  test.skip(!sourceSkuId || !otherSkuId, 'Set published STOREFRONT_TEST_SKU_ID and STOREFRONT_TEST_OTHER_SKU_ID')

  await page.goto('/shop?sort=price-desc')
  const prices = await page.locator('.product-card .product-meta span').allTextContents()
  const amounts = prices.map(parseRandAmount)
  expect(amounts.length).toBeGreaterThanOrEqual(2)
  expect(amounts.every(Number.isFinite)).toBe(true)
  expect(amounts).toEqual([...amounts].sort((a, b) => b - a))

  await page.goto('/shop?category=sofas&collection=living-room&availability=in-stock&min=1&max=100000&sort=price-desc')
  await expect(page.locator(`a[href="/product/${sourceSkuId}"]`)).toBeVisible()
  await expect(page.locator(`a[href="/product/${otherSkuId}"]`)).toHaveCount(0)
  await expect(page.getByLabel('Category')).toHaveValue('sofas')
  await expect(page.getByLabel('Collection')).toHaveValue('living-room')
  await expect(page.getByLabel('Availability')).toHaveValue('in-stock')
  await page.reload()
  await expect(page.locator(`a[href="/product/${sourceSkuId}"]`)).toBeVisible()
})

test('a price-filtered card shows the qualifying group variant price', async ({ page }) => {
  test.skip(!groupHandle, 'Set STOREFRONT_TEST_GROUP_HANDLE to a published group with distinct variant prices')

  await page.goto(`/product/${groupHandle}`)
  const option = page.locator('.variant-options select').first()
  await option.selectOption({ index: 0 })
  const first = parseRandAmount(await page.locator('.price').innerText())
  await option.selectOption({ index: 1 })
  const second = parseRandAmount(await page.locator('.price').innerText())
  expect(first).not.toBe(second)

  const minimum = Math.max(first, second)
  await page.goto(`/shop?min=${minimum}&sort=price-asc`)
  const card = page.locator(`a[href="/product/${groupHandle}"]`)
  await expect(card).toBeVisible()
  const shownPrice = parseRandAmount(await card.locator('.product-meta span').innerText())
  expect(shownPrice).toBeGreaterThanOrEqual(minimum)
})

test('draft product is absent from discovery and direct navigation', async ({ page }) => {
  test.skip(!draftSkuId, 'Set STOREFRONT_TEST_DRAFT_SKU_ID to a Medusa draft source SKU ID')

  await page.goto('/shop')
  await expect(page.locator(`a[href="/product/${draftSkuId}"]`)).toHaveCount(0)
  const response = await page.goto(`/product/${draftSkuId}`)
  expect(response?.status()).toBe(404)
  await expect(page.getByRole('heading', { name: 'We can’t find this piece.' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Explore all pieces' })).toBeVisible()
})

test('catalogue metadata and non-production robots policy describe public routes', async ({ page }) => {
  await page.goto('/shop')
  await expect(page).toHaveTitle(/Shop furniture \| The Collector/)
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', 'http://localhost:3004/shop')
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', /noindex/)
  await expect(page.locator('meta[name="description"]')).toHaveAttribute('content', /furniture collection/)

  if (sourceSkuId) {
    await page.goto(`/product/${sourceSkuId}`)
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', `http://localhost:3004/product/${sourceSkuId}`)
    await expect(page.locator('meta[name="description"]')).toHaveAttribute('content', /sofa|furniture/i)
  }
})

test('mobile keyboard path reaches filters and gallery without horizontal overflow', async ({ page }) => {
  test.skip(!sourceSkuId, 'Set STOREFRONT_TEST_SKU_ID to a published product with a gallery')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/shop')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.locator('#main-content')).toBeInViewport()
  await page.getByLabel('Search furniture').focus()
  await page.keyboard.type('Arc')
  await page.getByRole('button', { name: 'Show pieces' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.locator(`a[href="/product/${sourceSkuId}"]`)).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)

  await page.locator(`a[href="/product/${sourceSkuId}"]`).focus()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(new RegExp(`/product/${sourceSkuId}$`))
  const galleryChoice = page.getByRole('button', { name: 'Show image 2 of 3' })
  await expect(galleryChoice).toBeVisible()
  const initialHeroSrc = await page.locator('.hero-study img').getAttribute('src')
  await galleryChoice.focus()
  await page.keyboard.press('Enter')
  await expect(galleryChoice).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.hero-study img')).not.toHaveAttribute('src', initialHeroSrc || '')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
