import { expect, test, type Page } from '@playwright/test'

const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

test('help covers delivery and collection, returns and contact with the showroom facts and policy links', async ({ page }) => {
  await page.goto('/help')
  await expect(page.getByRole('heading', { level: 1, name: 'Help' })).toBeVisible()
  const main = page.getByRole('main')
  await expect(main).not.toContainText('[PLACEHOLDER')

  const delivery = page.getByRole('region', { name: 'Delivery and collection' })
  await expect(delivery).toContainText('confirmed in your order total before payment')
  await expect(delivery).toContainText('Shop GL15, Bedford Square, Smith Road, Bedfordview, Johannesburg, 2007')
  await expect(page.getByRole('region', { name: 'Returns' })).toContainText('Within 30 days of delivery or collection')

  const contact = page.getByRole('region', { name: 'Contact us' })
  for (const fact of ['Shop GL15, Bedford Square', 'Monday to Friday', '09:00–18:00', '09:00–17:00', '09:00–15:00', 'Cindy@daskasas.co.za']) {
    await expect(contact).toContainText(fact)
  }
  await expect(contact.getByRole('link', { name: '+27 63 025 4010' })).toHaveAttribute('href', 'tel:+27630254010')
  await expect(contact.getByRole('link', { name: '010 745 1980' })).toHaveAttribute('href', 'tel:0107451980')
  await expect(contact.getByRole('link', { name: 'Cindy@daskasas.co.za' })).toHaveCount(0)
  await expect(contact.getByRole('textbox')).toHaveCount(0)

  const policies = page.getByRole('navigation', { name: 'Full policies' })
  for (const href of ['/policies/delivery', '/policies/returns', '/policies/refunds', '/policies/terms', '/policies/privacy']) {
    await expect(policies.locator(`a[href="${href}"]`)).toBeVisible()
  }
})

test('/support and /contact land on help', async ({ page }) => {
  await page.goto('/support')
  await expect(page).toHaveURL(/\/help$/)
  await page.goto('/contact')
  await expect(page).toHaveURL(/\/help#contact$/)
  await expect(page.getByRole('heading', { name: 'Contact us' })).toBeInViewport()
})

test('the listing banner links delivery and returns to help', async ({ page }) => {
  await page.goto('/shop')
  await expect(page.getByRole('link', { name: 'Delivery and returns' })).toHaveAttribute('href', '/help')
})

for (const route of ['/help', '/account', '/account/sign-in', '/sign-in', '/sign-up', '/policies/terms']) {
  test(`${route} fits 390px without horizontal scroll`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(route)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    expect(await noHorizontalScroll(page)).toBe(true)
  })
}
