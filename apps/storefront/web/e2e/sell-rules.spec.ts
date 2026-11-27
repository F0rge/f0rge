import { expect, test, type Page } from '@playwright/test'

// Runs against the local Medusa fixture (e2e/analytics-medusa-fixture.mjs); see the storefront README.
// Pella Dining Chair is sold in pairs with five in stock; Pella Counter Stool is sold in pairs with one left.
const pella = '/product/77777777-7777-4777-8777-777777777777'
const stool = '/product/88888888-8888-4888-8888-888888888888'
const tilda = '/product/22222222-2222-4222-8222-222222222222'
// Pella Side Chair is sold in pairs with a minimum of four and nine in stock.
const side = '/product/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'

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
  await expect(page.getByRole('article').getByRole('status')).toHaveText('Not available to order')
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

test('a minimum above the batch size starts the page at the minimum and keeps the bag total valid', async ({ page }) => {
  await page.goto(side)
  await expect(page.locator('#product-batch')).toHaveText(/^R\s1\s990,00 each · sold in pairs · minimum 4 · from R\s7\s960,00$/)
  const decrease = page.getByRole('button', { name: 'Decrease Quantity' })
  const increase = page.getByRole('button', { name: 'Increase Quantity' })
  await expect(page.getByLabel('Quantity: 4')).toBeVisible()
  await expect(decrease).toBeDisabled()
  await increase.click()
  await expect(page.getByLabel('Quantity: 6')).toBeVisible()
  await increase.click()
  await expect(page.getByLabel('Quantity: 8')).toBeVisible()
  await expect(increase).toBeDisabled()
  await decrease.click()
  await decrease.click()
  await expect(page.getByLabel('Quantity: 4')).toBeVisible()

  // With four in the bag the minimum is met, so a further pair is enough.
  await page.getByRole('button', { name: 'Add to bag' }).click()
  await expect(page.getByRole('dialog', { name: 'Your bag' }).getByLabel('Quantity of Pella Side Chair: 4')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByLabel('Quantity: 2')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Decrease Quantity' })).toBeDisabled()
  await page.getByRole('button', { name: 'Increase Quantity' }).click()
  await expect(page.getByLabel('Quantity: 4')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Increase Quantity' })).toBeDisabled()
})

test('an off-rule bag (one chair, sold in pairs) is only offered quantities that make a whole pair', async ({ page }) => {
  await page.goto(pella)
  // The rule tightened after this chair went in the bag: the fixture accepts any quantity.
  const seeded = await page.evaluate(async () => (await fetch('/api/bag', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ variant_id: 'variant_pella_chair', quantity: 1 }),
  })).status)
  expect(seeded).toBe(200)
  await page.reload()
  await expect(page.getByLabel('Quantity: 1')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Decrease Quantity' })).toBeDisabled()
  await page.getByRole('button', { name: 'Increase Quantity' }).click()
  await expect(page.getByLabel('Quantity: 3')).toBeVisible()
  // Five in stock: 1 + 3 = 4 is the last whole pair.
  await expect(page.getByRole('button', { name: 'Increase Quantity' })).toBeDisabled()
  const added = page.waitForRequest((request) => request.url().endsWith('/api/bag') && request.method() === 'POST')
  await page.getByRole('button', { name: 'Add to bag' }).click()
  expect((await added).postDataJSON()).toEqual({ variant_id: 'variant_pella_chair', quantity: 3 })
  await expect(page.getByRole('dialog', { name: 'Your bag' }).getByLabel('Quantity of Pella Dining Chair: 4')).toBeVisible()
})
