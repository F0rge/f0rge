import { expect, test, type Page } from '@playwright/test'

const menu = [
  ['Sofas & Armchairs', '/shop/sofas-armchairs'],
  ['Dining Room', '/shop/dining-room'],
  ['Bedroom', '/shop/bedroom'],
  ['Coffee & Console Tables', '/shop/coffee-console-tables'],
  ['Shop all', '/shop'],
  ['Help', '/help'],
] as const

const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

async function expectLogoOnlyHomeLink(page: Page) {
  const homeLink = page.getByRole('banner').getByRole('link', { name: 'DasKasas home' })
  const logo = homeLink.locator('img')
  await expect(homeLink).toHaveText('')
  await expect(logo).toBeVisible()
  await expect.poll(() => logo.evaluate((image) => image instanceof HTMLImageElement && image.naturalWidth)).toBeGreaterThan(0)
  return homeLink
}

test('DasKasas serves the browser-tab icon as a PNG', async ({ page }) => {
  await page.goto('/shop')
  const icon = page.locator('head link[rel="icon"]')
  await expect(icon).toHaveCount(1)
  await expect(icon).toHaveAttribute('type', 'image/png')
  await expect(icon).toHaveAttribute('sizes', '64x64')

  const url = await icon.evaluate((link) => link instanceof HTMLLinkElement ? link.href : '')
  const response = await page.request.get(url)
  await expect(response).toBeOK()
  expect(response.headers()['content-type']).toMatch(/^image\/png(?:;|$)/)
})

test('DasKasas desktop navigation shows the four categories, Shop all and Help', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/shop')
  const header = page.getByRole('banner')
  const nav = page.getByRole('navigation', { name: 'Main navigation' })
  await expect(nav.getByRole('link')).toHaveText(menu.map(([label]) => label))
  for (const [label, href] of menu) await expect(nav.getByRole('link', { name: label, exact: true })).toHaveAttribute('href', href)
  await expect(header.getByRole('button', { name: 'Bag, 0 items' })).toBeVisible()
  await expect(header.getByRole('link', { name: 'Account', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open menu' })).toBeHidden()
  const homeLink = await expectLogoOnlyHomeLink(page)
  await homeLink.click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page).toHaveTitle(/DasKasas/)
})

for (const width of [390, 320]) {
  test(`mobile navigation supports keyboard, dismissal and route selection at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    await page.goto('/shop')
    await expectLogoOnlyHomeLink(page)
    await page.keyboard.press('Tab')
    await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.locator('#main-content')).toBeInViewport()

    const trigger = page.getByRole('button', { name: 'Open menu' })
    await trigger.focus()
    await page.keyboard.press('Enter')
    const dialog = page.getByRole('dialog', { name: /^DasKasas$/i })
    await expect(dialog).toBeVisible()
    await expect.poll(() => dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true)
    const mobileNav = dialog.getByRole('navigation', { name: 'Mobile navigation' })
    await expect(mobileNav.getByRole('link')).toHaveText([...menu.map(([label]) => label), 'Account'])
    for (let index = 0; index < 10; index += 1) {
      await page.keyboard.press('Tab')
      await expect.poll(() => dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true)
    }
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(trigger).toBeFocused()

    await page.goto('/')
    await trigger.click()
    await mobileNav.getByRole('link', { name: 'Shop all' }).click()
    await expect(page).toHaveURL(/\/shop$/)
    await expect(dialog).toBeHidden()
    expect(await noHorizontalScroll(page)).toBe(true)
    await expect(page.getByRole('banner').getByRole('button', { name: 'Bag, 0 items' })).toBeVisible()

    await trigger.click()
    await dialog.getByRole('button', { name: 'Close', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect(trigger).toBeFocused()
  })
}

for (const width of [1440, 390]) {
  test(`the showroom link leaves its heading below the sticky header at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/shop')
    await page.getByRole('link', { name: 'Visit our showroom at Bedford Square, Bedfordview.' }).click()
    await expect(page).toHaveURL(/\/#visit$/)
    const heading = page.getByRole('heading', { name: 'Visit the showroom' })
    await expect(heading).toBeInViewport()
    const header = page.getByRole('banner')
    await expect.poll(async () => {
      const [top, bottom] = await Promise.all([heading.evaluate((element) => element.getBoundingClientRect().top), header.evaluate((element) => element.getBoundingClientRect().bottom)])
      return top >= bottom
    }).toBe(true)
    const headerTop = await header.evaluate((element) => element.getBoundingClientRect().top)
    expect(headerTop).toBeGreaterThanOrEqual(0)
    expect(headerTop).toBeLessThanOrEqual(1)
  })
}

test('the footer carries the showroom facts and the published privacy policy names the Information Officer', async ({ page }) => {
  for (const route of ['/', '/shop', '/bag', '/policies/privacy']) {
    await page.goto(route)
    const footer = page.getByRole('contentinfo')
    await expect(footer).toContainText('Shop GL15, Bedford Square, Smith Road, Bedfordview, Johannesburg, 2007')
    for (const fact of ['Mon–Fri 09:00–18:00', 'Sat 09:00–17:00', 'Sun 09:00–15:00', '+27 63 025 4010', '010 745 1980', 'Cindy@daskasas.co.za']) {
      await expect(footer).toContainText(fact)
    }
  }
  const policy = page.locator('article')
  const emails = await policy.evaluate((element) => [...new Set((element as HTMLElement).innerText.match(/[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g) ?? [])])
  expect(emails).toEqual(['Cindy@daskasas.co.za', 'enquiries@inforegulator.org.za', 'POPIAComplaints@inforegulator.org.za'])
  await expect(policy).toContainText('Our Information Officer is Cindy Gomes.')
  await expect(policy).not.toContainText(/\[PLACEHOLDER:|Draft for owner/)
})

test('the footer reopens the cookie choice', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('storefront-analytics-consent-v1', 'rejected'))
  await page.goto('/')
  const choices = page.getByRole('region', { name: 'Your privacy choices' })
  await expect(choices).toBeHidden()
  await expect(page.getByRole('button', { name: 'Privacy settings' })).toHaveCount(0)
  await page.getByRole('contentinfo').getByRole('button', { name: 'Cookie settings' }).click()
  await expect(choices).toBeVisible()
  await expect(choices.getByRole('button', { name: 'Accept optional analytics' })).toBeVisible()
})

test('old routes redirect permanently', async ({ request }) => {
  for (const [from, to] of [['/collections', '/shop'], ['/support', '/help']]) {
    const response = await request.get(from, { maxRedirects: 0 })
    expect(response.status()).toBe(308)
    expect(new URL(response.headers().location, 'http://localhost').pathname).toBe(to)
  }
})

for (const width of [1280, 390]) {
  test(`the home page fits ${width}px without horizontal scroll`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(page.locator('#selected-pieces [data-placeholder]')).toHaveText('Vale Bedside Table')
    expect(await noHorizontalScroll(page)).toBe(true)
  })
}
