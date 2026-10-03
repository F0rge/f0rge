import { expect, test, type Page } from '@playwright/test'
import { CONSENTED_MEASUREMENT_DISCLAIMER, consentedBrowsingReports } from '../src/lib/analytics/reports'

const consentKey = 'storefront-analytics-consent-v1'
const productHandle = '11111111-1111-4111-8111-111111111111'
const productUrl = `/product/${productHandle}`
const captured: { api_key: string; event: string; distinct_id: string; properties: Record<string, unknown> }[] = []
const captureHeaders: Record<string, string>[] = []

test.skip(!process.env.STOREFRONT_ANALYTICS_E2E, 'Set STOREFRONT_ANALYTICS_E2E=true with the local Medusa fixture and test-only public PostHog token')

test.beforeEach(async ({ page }) => {
  captured.length = 0
  captureHeaders.length = 0
  await page.route('https://eu.i.posthog.com/i/v0/e/', async (route) => {
    captured.push(route.request().postDataJSON())
    captureHeaders.push(route.request().headers())
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' })
  })
})

async function chooseStoredConsent(page: Page, choice: 'accepted' | 'rejected') {
  await page.addInitScript(({ key, saved }) => {
    if (!localStorage.getItem(key)) localStorage.setItem(key, saved)
    Object.defineProperty(document, 'referrer', { configurable: true, value: 'https://www.example.com/private?email=secret%40example.com&token=private-referrer-token' })
  }, { key: consentKey, saved: choice })
}

test('rejected visitors send nothing; later acceptance sends sanitized acquisition and search signals', async ({ page }) => {
  await page.addInitScript(({ key }) => {
    localStorage.clear()
    Object.defineProperty(document, 'referrer', { configurable: true, value: 'https://www.example.com/private?email=secret%40example.com&token=private-referrer-token' })
    localStorage.removeItem(key)
  }, { key: consentKey })
  await page.goto('/shop?q=alice%40example.com&utm_source=Spring_News&utm_campaign=bedroom-sale&token=private-token-value')
  await expect(page.getByRole('heading', { name: 'Explore the collection.' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Reject optional analytics' })).toBeVisible()
  await page.getByRole('button', { name: 'Reject optional analytics' }).click()
  await expect(page.getByRole('button', { name: 'Privacy settings' })).toBeVisible()
  expect(captured).toHaveLength(0)
  expect(await page.evaluate((key) => localStorage.getItem(key), consentKey)).toBe('rejected')

  await page.getByRole('button', { name: 'Privacy settings' }).click()
  await page.getByRole('button', { name: 'Accept optional analytics' }).click()
  await expect.poll(() => captured.some((event) => event.event === 'storefront_page_viewed')).toBe(true)
  await expect.poll(() => captured.some((event) => event.event === 'storefront_search_results_viewed')).toBe(true)
  const pageView = captured.find((event) => event.event === 'storefront_page_viewed')
  expect(pageView?.properties).toMatchObject({ page_key: 'shop', utm_source: 'spring_news', utm_campaign: 'bedroom-sale', referrer_host: 'example.com' })
  expect(JSON.stringify(captured)).not.toContain('alice@example.com')
  expect(JSON.stringify(captured)).not.toContain('secret@example.com')
  expect(JSON.stringify(captured)).not.toContain('private-token-value')
  expect(JSON.stringify(captured)).not.toContain('private-referrer-token')
  expect(JSON.stringify(captured)).not.toContain('/private')
  expect(captured.every((event) => !('email' in event.properties) && !('token' in event.properties) && !('search_query' in event.properties))).toBe(true)
  expect(captureHeaders.every((headers) => !headers.cookie && !headers.referer)).toBe(true)
})

test('withdrawal revokes an accepted visitor and leaves no persisted analytics identity or attribution', async ({ page }) => {
  await chooseStoredConsent(page, 'accepted')
  await page.goto('/shop?utm_source=first-campaign&q=private-search')
  await expect(page.getByRole('heading', { name: 'Explore the collection.' })).toBeVisible()
  await expect.poll(() => captured.length).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Privacy settings' }).click()
  await page.getByRole('button', { name: 'Withdraw optional analytics' }).click()
  await expect(page.getByRole('button', { name: 'Privacy settings' })).toBeVisible()
  const requestsBeforeNextPage = captured.length
  await page.goto('/shop?utm_source=after-withdrawal&q=next-private-search')
  await expect(page.getByRole('heading', { name: 'Explore the collection.' })).toBeVisible()
  await page.waitForTimeout(250)
  expect(captured).toHaveLength(requestsBeforeNextPage)
  expect(await page.evaluate((key) => localStorage.getItem(key), consentKey)).toBe('rejected')
  const storageAndCookies = await page.evaluate(() => ({ localStorage: Object.keys(localStorage), cookie: document.cookie }))
  expect(storageAndCookies.localStorage.some((key) => /distinct|attribution|posthog|ph_/i.test(key))).toBe(false)
  expect(storageAndCookies.cookie).not.toMatch(/(?:^|;\s*)(?:ph_|distinct_id)/i)
})

test('product attention excludes hidden and idle time and sends one visit summary', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await chooseStoredConsent(page, 'accepted')
  await page.clock.install()
  await page.goto(productUrl)
  await expect(page.getByRole('heading', { name: /Test chair/ })).toBeVisible()
  await expect(page.locator('.hero-study')).toBeInViewport({ ratio: 0.5 })
  await expect(page.locator('.product-attention-region')).toBeInViewport({ ratio: 0.5 })
  await page.evaluate(() => document.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })))
  await page.clock.runFor(5_000)
  await page.evaluate(() => {
    let state = 'hidden'
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
    Object.defineProperty(document, 'hasFocus', { configurable: true, value: () => true })
    Object.assign(window, { setAnalyticsTestVisibility: (next: string) => {
      state = next
      document.dispatchEvent(new Event('visibilitychange'))
      window.dispatchEvent(new Event(next === 'visible' ? 'focus' : 'blur'))
    } })
    document.dispatchEvent(new Event('visibilitychange'))
    window.dispatchEvent(new Event('blur'))
  })
  await page.clock.runFor(60_000)
  await page.evaluate(() => {
    (window as unknown as { setAnalyticsTestVisibility(next: string): void }).setAnalyticsTestVisibility('visible')
    document.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
  })
  await page.clock.runFor(5_000)
  await page.getByRole('link', { name: /All pieces/ }).click()
  await expect(page.getByRole('heading', { name: 'Explore the collection.' })).toBeVisible()
  await expect.poll(() => captured.filter((event) => event.event === 'storefront_product_attention_summary').length).toBe(1)
  const summary = captured.find((event) => event.event === 'storefront_product_attention_summary')
  expect(summary?.properties).toMatchObject({ product_id: 'prod_test_chair', active_seconds: 10, visibility_threshold: 'half_visible' })
})

test('shop impressions and reports stay on the consented allowlist', async ({ page }) => {
  await chooseStoredConsent(page, 'accepted')
  await page.goto('/shop?utm_source=spring_news&utm_campaign=bedroom-sale')
  await expect(page.getByRole('heading', { name: 'Explore the collection.' })).toBeVisible()
  await page.locator('a.product-card').first().scrollIntoViewIfNeeded()
  await expect.poll(() => captured.some((event) => event.event === 'storefront_product_impressed')).toBe(true)
  await page.locator('a.product-card').first().click()
  await expect(page.getByRole('heading', { name: /Test chair/ })).toBeVisible()
  await expect(page.locator('.product-attention-region')).toBeVisible()
  const names = captured.map((event) => event.event)
  expect(names).toContain('storefront_product_selected')
  expect(names.filter((name) => name === 'storefront_search_results_viewed')).toHaveLength(1)
  const reports = consentedBrowsingReports(captured.map((event) => ({ name: event.event, properties: event.properties })))
  expect(reports.acquisition.disclaimer).toBe(CONSENTED_MEASUREMENT_DISCLAIMER)
  expect(reports.product.scope).toBe('consented_visitors')
  expect(reports.search.rows[0]).toMatchObject({ result_count: 1, query_present: false })
})

test('analytics transport failure does not block browsing', async ({ page }) => {
  await page.unroute('https://eu.i.posthog.com/i/v0/e/')
  await page.route('https://eu.i.posthog.com/i/v0/e/', async (route) => {
    await route.fulfill({ status: 500, contentType: 'application/json', body: '{"status":"error"}' })
  })
  await chooseStoredConsent(page, 'accepted')
  await page.goto('/shop')
  await expect(page.getByRole('heading', { name: 'Explore the collection.' })).toBeVisible()
  await page.getByRole('link', { name: /Test chair/ }).first().click()
  await expect(page.getByRole('heading', { name: /Test chair/ })).toBeVisible()
})
