import { expect, test, type Locator, type Page } from '@playwright/test'

// Runs against the local Medusa fixture (e2e/analytics-medusa-fixture.mjs); see the storefront README.
const consentKey = 'storefront-analytics-consent-v1'
const chair = '/product/11111111-1111-4111-8111-111111111111'
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)
const choices = (page: Page) => page.getByRole('region', { name: 'Your privacy choices' })

// True when the element is what a click at its bottom-right corner (and centre) would hit, i.e. nothing floats over it.
async function uncovered(target: Locator) {
  return target.evaluate((element) => {
    const box = element.getBoundingClientRect()
    return [[box.right - 12, box.bottom - 12], [box.left + box.width / 2, box.top + box.height / 2]]
      .every(([x, y]) => element.contains(document.elementFromPoint(x, y)))
  })
}

test('analytics is off by default, Reject is as prominent as Accept, and Reject sends nothing', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const analytics: string[] = []
  await page.route('https://eu.i.posthog.com/**', async (route) => {
    analytics.push(route.request().url())
    await route.fulfill({ status: 200, body: '{}' })
  })
  await page.goto('/shop')
  const accept = choices(page).getByRole('button', { name: 'Accept optional analytics' })
  const reject = choices(page).getByRole('button', { name: 'Reject optional analytics' })
  await expect(accept).toBeVisible()
  await expect(reject).toBeVisible()
  expect(await page.evaluate((key) => localStorage.getItem(key), consentKey)).toBeNull()
  await expect(choices(page).getByRole('link', { name: 'Privacy notice' })).toHaveAttribute('href', '/policies/privacy')
  const look = (button: Locator) => button.evaluate((element) => {
    const style = getComputedStyle(element)
    const box = element.getBoundingClientRect()
    return [style.backgroundColor, style.color, style.fontSize, style.fontWeight, box.height, Math.round(box.width), box.top]
  })
  expect(await look(reject)).toEqual(await look(accept))

  expect(await choices(page).evaluate((panel) => panel.getBoundingClientRect().height)).toBeLessThan(170)
  await reject.click()
  await expect(choices(page)).toBeHidden()
  expect(await page.evaluate((key) => localStorage.getItem(key), consentKey)).toBe('rejected')
  await page.reload()
  await expect(page.getByRole('heading', { level: 1, name: 'Shop all' })).toBeVisible()
  await expect(choices(page)).toBeHidden()
  expect(analytics).toHaveLength(0)
})

test('the footer reopens the choice, and no consent control floats over the first piece or the bag drawer', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await choices(page).getByRole('button', { name: 'Reject optional analytics' }).click()
  await expect(choices(page)).toBeHidden()
  await expect(page.getByRole('button', { name: 'Privacy settings' })).toHaveCount(0)

  const firstPiece = page.locator('#selected-pieces a').first()
  await firstPiece.evaluate((element) => element.scrollIntoView({ block: 'end' }))
  await expect.poll(() => uncovered(firstPiece)).toBe(true)

  await page.getByRole('contentinfo').getByRole('button', { name: 'Cookie settings' }).click()
  await expect(choices(page)).toBeVisible()
  await expect(choices(page).getByRole('button', { name: 'Accept optional analytics' })).toBeVisible()
  await choices(page).getByRole('button', { name: 'Keep analytics off' }).click()
  await expect(choices(page)).toBeHidden()

  await page.goto(chair)
  await page.getByRole('button', { name: 'Add to bag' }).click()
  const drawer = page.getByRole('dialog', { name: 'Your bag' })
  await expect(drawer).toBeVisible()
  await expect.poll(() => uncovered(drawer.getByRole('link', { name: 'View bag' }))).toBe(true)
})

test('the bag drawer sits above the consent panel before a choice is made', async ({ page }) => {
  await page.goto(chair)
  await expect(choices(page)).toBeVisible()
  await page.getByRole('button', { name: 'Add to bag' }).click()
  const drawer = page.getByRole('dialog', { name: 'Your bag' })
  await expect(drawer).toBeVisible()
  await expect.poll(() => uncovered(drawer.getByRole('link', { name: 'View bag' }))).toBe(true)
})

test('privacy and PAIA pages render, link each other and fit 390px', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/policies/privacy')
  const privacy = page.locator('article')
  for (const heading of ['What we collect', 'Information sent outside South Africa', 'Your right to object', 'Complaints to the Information Regulator']) {
    await expect(privacy.getByRole('heading', { name: heading })).toBeVisible()
  }
  await expect(privacy).toContainText('Woodmead North Office Park, 54 Maxwell Drive')
  await expect(privacy).not.toContainText('JD House')
  expect(await noHorizontalScroll(page)).toBe(true)

  await page.getByRole('contentinfo').getByRole('link', { name: 'PAIA manual' }).click()
  await expect(page).toHaveURL(/\/policies\/paia$/)
  await expect(page.getByRole('heading', { level: 1, name: 'PAIA manual' })).toBeVisible()
  for (const heading of ['Information Officer and PAIA requests', 'How to request a record', 'Personal information we process']) {
    await expect(page.locator('article').getByRole('heading', { name: heading })).toBeVisible()
  }
  expect(await noHorizontalScroll(page)).toBe(true)
  await page.locator('article').getByRole('link', { name: 'Privacy', exact: true }).click()
  await expect(page).toHaveURL(/\/policies\/privacy$/)
  await expect(page.locator('article').getByRole('link', { name: 'PAIA manual' })).toHaveAttribute('href', '/policies/paia')
})

test('checkout shows the short privacy notice before the contact details are sent', async ({ page }) => {
  await page.goto(chair)
  await page.getByRole('button', { name: 'Add to bag' }).click()
  await page.getByRole('dialog', { name: 'Your bag' }).getByRole('button', { name: 'Checkout' }).click()
  await expect(page).toHaveURL(/\/checkout$/)
  const contact = page.getByRole('group', { name: 'Contact' })
  await expect(contact).toContainText('They are required: without them we cannot complete the order.')
  await expect(contact).toContainText('the right to object')
  await expect(contact.getByRole('link', { name: 'Our privacy policy' })).toHaveAttribute('href', '/policies/privacy')
})
