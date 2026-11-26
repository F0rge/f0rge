import { expect, test, type Page } from '@playwright/test'

// Runs against the local Medusa fixture (e2e/analytics-medusa-fixture.mjs); see the storefront README.
// Pella Dining Chair is sold in pairs with five in stock; Pella Counter Stool is sold in pairs with one left.
const pella = '/product/77777777-7777-4777-8777-777777777777'
const stool = '/product/88888888-8888-4888-8888-888888888888'
const tilda = '/product/22222222-2222-4222-8222-222222222222'

const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

test('a pair-sold piece starts at two, steps by two, caps at rounded-down stock and says so in the price', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto(pella)
  await expect(page.locator('#product-price')).toHaveText(/^R\s2\s450,00$/)
  await expect(page.locator('#product-batch')).toHaveText(/^R\s2\s450,00 each · sold in pairs · R\s4\s900,00 per pair$/)

  const decrease = page.getByRole('button', { name: 'Decrease Quantity' })
  const increase = page.getByRole('button', { name: 'Increase Quantity' })
  await expect(page.getByLabel('Quantity: 2')).toBeVisible()
  await expect(decrease).toBeDisabled()
  await increase.click()
  await expect(page.getByLabel('Quantity: 4')).toBeVisible()
  // Five in stock: a sixth chair would break the pair, so four is the most.
  await expect(increase).toBeDisabled()
  await decrease.click()
  await expect(page.getByLabel('Quantity: 2')).toBeVisible()
  await expect(decrease).toBeDisabled()
  expect(await noHorizontalScroll(page)).toBe(true)

  await increase.click()
  const added = page.waitForRequest((request) => request.url().endsWith('/api/bag') && request.method() === 'POST')
  await page.getByRole('button', { name: 'Add to bag' }).click()
  expect((await added).postDataJSON()).toEqual({ variant_id: 'variant_pella_chair', quantity: 4 })
  await expect(page.getByRole('dialog', { name: 'Your bag' }).getByLabel('Quantity of Pella Dining Chair: 4')).toBeVisible()
  await page.keyboard.press('Escape')
  // One chair left after four in the bag: no quantity is offered.
  await expect(page.getByText('You have the available quantity of this option in your bag.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Increase Quantity' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Add to bag' })).toBeDisabled()
})

test('stock that cannot make up the minimum is stated instead of offering a quantity', async ({ page }) => {
  await page.goto(stool)
  await expect(page.getByText('Only 1 available, fewer than the minimum order of 2.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Increase Quantity' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Add to bag' })).toBeDisabled()
})

test('the bag steps a pair-sold line by two and never below the minimum', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto(pella)
  await page.getByRole('button', { name: 'Add to bag' }).click()
  const drawer = page.getByRole('dialog', { name: 'Your bag' })
  await expect(drawer.getByLabel('Quantity of Pella Dining Chair: 2')).toBeVisible()
  const decrease = drawer.getByRole('button', { name: 'Decrease Quantity of Pella Dining Chair' })
  const increase = drawer.getByRole('button', { name: 'Increase Quantity of Pella Dining Chair' })
  await expect(decrease).toBeDisabled()

  const patched = page.waitForRequest((request) => request.url().endsWith('/api/bag') && request.method() === 'PATCH')
  await increase.click()
  expect((await patched).postDataJSON()).toEqual({ item_id: 'cali_variant_pella_chair', quantity: 4 })
  await expect(drawer.getByLabel('Quantity of Pella Dining Chair: 4')).toBeVisible()
  await expect(drawer.getByTestId('bag-subtotal')).toHaveText(/^R\s9\s800,00$/)
  await expect(increase).toBeDisabled()
  expect(await noHorizontalScroll(page)).toBe(true)

  await drawer.getByRole('link', { name: 'View bag' }).click()
  const main = page.getByRole('main')
  await main.getByRole('button', { name: 'Decrease Quantity of Pella Dining Chair' }).click()
  await expect(main.getByLabel('Quantity of Pella Dining Chair: 2')).toBeVisible()
  await expect(main.getByRole('button', { name: 'Decrease Quantity of Pella Dining Chair' })).toBeDisabled()
  await expect(main.getByTestId('bag-total')).toHaveText(/^R\s4\s900,00$/)
  await main.getByRole('button', { name: 'Remove Pella Dining Chair' }).click()
  await expect(main.getByText('Your bag is empty.')).toBeVisible()
})

test('a piece with no selling rules is unchanged: no batch line, steps by one from one', async ({ page }) => {
  await page.goto(tilda)
  await expect(page.locator('#product-batch')).toHaveCount(0)
  await expect(page.getByLabel('Quantity: 1')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Decrease Quantity' })).toBeDisabled()
  await page.getByRole('button', { name: 'Increase Quantity' }).click()
  await expect(page.getByLabel('Quantity: 2')).toBeVisible()
})
