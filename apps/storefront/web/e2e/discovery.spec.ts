import { expect, test } from '@playwright/test'

const sourceSkuId = process.env.STOREFRONT_TEST_SKU_ID
const draftSkuId = process.env.STOREFRONT_TEST_DRAFT_SKU_ID

test('draft product is absent from discovery and direct navigation', async ({ page }) => {
  test.skip(!draftSkuId, 'Set STOREFRONT_TEST_DRAFT_SKU_ID to a Medusa draft source SKU ID')

  await page.goto('/shop')
  await expect(page.locator(`a:visible[href="/product/${draftSkuId}"]`)).toHaveCount(0)
  const response = await page.goto(`/product/${draftSkuId}`)
  expect(response?.status()).toBe(404)
  await expect(page.getByRole('heading', { name: 'We can’t find this piece.' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Explore all pieces' })).toBeVisible()
})

test('catalogue metadata and non-production robots policy describe public routes', async ({ page }) => {
  await page.goto('/shop')
  await expect(page).toHaveTitle(/Shop furniture \| DasKasas/)
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', 'http://localhost:3004/shop')
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', /noindex/)
  await expect(page.locator('meta[name="description"]')).toHaveAttribute('content', /Browse sofas and armchairs.*Filter by price and availability/)
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute('content', 'Shop furniture | DasKasas')
  await expect(page.locator('meta[property="og:url"]')).toHaveAttribute('content', 'http://localhost:3004/shop')
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute('content', 'http://localhost:3004/hero-sofas.jpg')

  if (sourceSkuId) {
    await page.goto(`/product/${sourceSkuId}`)
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', `http://localhost:3004/product/${sourceSkuId}`)
    await expect(page.locator('meta[name="description"]')).toHaveAttribute('content', /\S.{14,}/)
  }
})

test('mobile keyboard path reaches a piece and its gallery without horizontal overflow', async ({ page }) => {
  test.skip(!sourceSkuId, 'Set STOREFRONT_TEST_SKU_ID to a published product with a gallery')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/shop')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.locator('#main-content')).toBeInViewport()
  const productLink = page.getByRole('list', { name: 'Pieces' }).getByRole('heading', { level: 3 })
    .getByRole('link').and(page.locator(`[href="/product/${sourceSkuId}"]`))
  await expect(productLink).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)

  await productLink.focus()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(new RegExp(`/product/${sourceSkuId}$`))
  const galleryChoice = page.getByRole('button', { name: /^Show image 2 of / })
  await expect(galleryChoice).toBeVisible()
  const initialHeroSrc = await page.locator('[data-main-image] img').getAttribute('src')
  await galleryChoice.focus()
  await page.keyboard.press('Enter')
  await expect(galleryChoice).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('[data-main-image] img')).not.toHaveAttribute('src', initialHeroSrc || '')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
