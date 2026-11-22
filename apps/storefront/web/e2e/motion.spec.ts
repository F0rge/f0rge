import { expect, test, type Locator } from '@playwright/test'

async function expectReadable(content: Locator) {
  await expect(content).toBeVisible()
  await expect.poll(() => content.evaluate((element) => {
    for (let current: Element | null = element; current; current = current.parentElement) {
      const style = getComputedStyle(current)
      if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) < 1) return false
    }
    return true
  })).toBe(true)
}

test('shopping sections remain readable when JavaScript is disabled', async ({ browser, baseURL }) => {
  const context = await browser.newContext({ baseURL, javaScriptEnabled: false })
  const page = await context.newPage()
  try {
    for (const route of ['/']) {
      await page.goto(route)
      await expectReadable(page.getByRole('heading', { level: 1 }))
      const sections = page.locator('[data-reveal]')
      expect(await sections.count()).toBeGreaterThan(0)
      for (const section of await sections.all()) {
        await section.scrollIntoViewIfNeeded()
        await expectReadable(section)
      }
    }
    await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Shop all' }).click()
    await expect(page).toHaveURL(/\/shop$/)
    await expectReadable(page.getByRole('heading', { level: 1 }))
  } finally {
    await context.close()
  }
})

test('reduced motion leaves revealed shopping content readable without animations', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  for (const route of ['/']) {
    await page.goto(route)
    const sections = page.locator('[data-reveal]')
    expect(await sections.count()).toBeGreaterThan(0)
    for (const section of await sections.all()) {
      await section.scrollIntoViewIfNeeded()
      await expectReadable(section)
      expect(await section.evaluate((element) => element.getAnimations().length)).toBe(0)
    }
  }
})

test('gallery selection remains visible and announces its image with reduced motion', async ({ page }) => {
  const sku = process.env.STOREFRONT_TEST_SKU_ID
  test.skip(!sku, 'A published SKU with multiple catalogue images is required')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto(`/product/${sku}`)
  const image = page.locator('[data-main-image] img')
  const original = await image.getAttribute('src')
  if (!original) throw new Error('Product gallery source is missing')
  await page.getByRole('button', { name: /Show image 2 of/ }).click()
  await expect(image).not.toHaveAttribute('src', original)
  await expectReadable(image)
  expect(await image.evaluate((element) => element.getAnimations().length)).toBe(0)
  await expect(page.getByRole('article').locator('[aria-live=polite]', { hasText: /Image \d of/ })).toContainText(/Image 2 of/)
})

test('focusing a shopping card ends its reveal and scrolling back does not replay it', async ({ page }) => {
  test.skip(!process.env.STOREFRONT_TEST_SKU_ID, 'A published catalogue is required')
  await page.setViewportSize({ width: 1440, height: 500 })
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  const section = page.locator('#selected-pieces')
  await expect(section).not.toBeInViewport()
  await section.scrollIntoViewIfNeeded()
  await expect.poll(() => section.evaluate((element) => element.getAnimations().length)).toBeGreaterThan(0)
  const card = section.getByRole('link').nth(1)
  await card.focus()
  await expect(card).toBeFocused()
  await expectReadable(section)
  expect(await section.evaluate((element) => element.getAnimations().length)).toBe(0)

  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
  await section.scrollIntoViewIfNeeded()
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
  expect(await section.evaluate((element) => element.getAnimations().length)).toBe(0)
  await expectReadable(section)
})
