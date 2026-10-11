import { expect, test } from '@playwright/test'

test('Vellano desktop navigation exposes shopping and the brand home link', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/shop')
  await expect(page.locator('.site-header').getByRole('link', { name: 'Vellano home' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Shop all' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open menu' })).toBeHidden()
  await page.locator('.site-header').getByRole('link', { name: 'Vellano home' }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page).toHaveTitle(/Vellano/)
})

for (const width of [390, 320]) {
  test(`mobile navigation supports keyboard, dismissal and route selection at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    await page.goto('/shop')
    await page.keyboard.press('Tab')
    await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.locator('#main-content')).toBeInViewport()

    const trigger = page.getByRole('button', { name: 'Open menu' })
    await trigger.focus()
    await page.keyboard.press('Enter')
    const dialog = page.getByRole('dialog', { name: /^Vellano$/i })
    await expect(dialog).toBeVisible()
    await expect.poll(() => dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true)
    await expect(dialog.getByRole('navigation', { name: 'Mobile navigation' }).getByRole('link', { name: 'Collections' })).toBeVisible()
    for (let index = 0; index < 8; index += 1) {
      await page.keyboard.press('Tab')
      await expect.poll(() => dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true)
    }
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(trigger).toBeFocused()

    await trigger.click()
    await dialog.getByRole('link', { name: 'Collections' }).click()
    await expect(page).toHaveURL(/\/collections$/)
    await expect(dialog).toBeHidden()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await expect(page.locator('.site-header').getByRole('link', { name: 'Bag', exact: true })).toBeVisible()

    await trigger.click()
    await dialog.getByRole('button', { name: 'Close', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect(trigger).toBeFocused()
  })
}

for (const width of [1440, 390]) {
  test(`section navigation leaves its heading below the sticky header at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/shop')
    if (width < 1050) {
      await page.getByRole('button', { name: 'Open menu' }).click()
      const dialog = page.getByRole('dialog', { name: /^Vellano$/i })
      await dialog.getByRole('link', { name: 'Our approach' }).click()
      await expect(dialog).toBeHidden()
    } else {
      await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Our approach' }).click()
    }
    await expect(page).toHaveURL(/\/#our-approach$/)
    const heading = page.locator('#our-approach:visible').getByRole('heading')
    await expect(heading).toBeInViewport()
    await expect.poll(() => heading.evaluate((element) => {
      const header = document.querySelector('.site-header')
      if (!header) throw new Error('Vellano header is missing')
      return element.getBoundingClientRect().top >= header.getBoundingClientRect().bottom
    })).toBe(true)
    const header = page.locator('.site-header')
    expect(await header.evaluate((element) => element.getBoundingClientRect().top)).toBeGreaterThanOrEqual(0)
    expect(await header.evaluate((element) => element.getBoundingClientRect().top)).toBeLessThanOrEqual(1)
  })
}
