import { expect, test, type Page } from '@playwright/test'

// Runs against the local Medusa fixture (e2e/analytics-medusa-fixture.mjs): one or two pieces per category,
// one uncategorised piece (Yara Floor Lamp) and one made-to-order piece (Wren Coffee Table).
const categories = [
  ['Sofas & Armchairs', ['Test chair', 'Tilda Sofa']],
  ['Dining Room', ['Umbra Dining Table']],
  ['Bedroom', ['Vale Bedside Table']],
  ['Coffee & Console Tables', ['Wren Coffee Table']],
] as const
const byName = ['Test chair', 'Tilda Sofa', 'Umbra Dining Table', 'Vale Bedside Table', 'Wren Coffee Table', 'Yara Floor Lamp']
const byPrice = ['Yara Floor Lamp', 'Test chair', 'Vale Bedside Table', 'Wren Coffee Table', 'Tilda Sofa', 'Umbra Dining Table']

const grid = (page: Page) => page.getByRole('list', { name: 'Pieces' })
const titles = (page: Page) => grid(page).getByRole('heading', { level: 3 }).allTextContents()
const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

test('the menu opens each category with only its pieces; an uncategorised piece is only in Shop all', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/shop')
  await expect(page.getByRole('heading', { level: 1, name: 'Shop all' })).toBeVisible()
  expect(await titles(page)).toEqual(byName)
  for (const [name, pieces] of categories) {
    await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name, exact: true }).click()
    await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
    await expect(grid(page).getByRole('heading', { level: 3 })).toHaveText([...pieces])
    await expect(page.getByRole('status').filter({ hasText: /piece/ })).toHaveText(`${pieces.length} ${pieces.length === 1 ? 'piece' : 'pieces'}`)
    await expect(grid(page)).not.toContainText('Yara Floor Lamp')
    await expect(page.getByRole('region', { name: 'Other categories' }).getByRole('link')).toHaveCount(3)
  }
})

test('availability filter, sort and counts agree with the grid', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/shop')
  const filters = page.getByRole('complementary', { name: 'Filters' })
  const count = page.getByRole('status').filter({ hasText: /piece/ })
  const inStock = filters.getByRole('checkbox', { name: 'In stock (5)' })
  const madeToOrder = filters.getByRole('checkbox', { name: 'Made to order (1)' })
  await expect(count).toHaveText('6 pieces')

  await inStock.check()
  await expect(count).toHaveText('5 pieces')
  expect(await titles(page)).toEqual(byName.filter((title) => title !== 'Wren Coffee Table'))
  await inStock.uncheck()
  await madeToOrder.check()
  await expect(count).toHaveText('1 piece')
  await expect(grid(page).getByRole('link')).toHaveText([/Wren Coffee Table.*Made to order/])
  await inStock.check()
  await expect(count).toHaveText('6 pieces')
  await filters.getByRole('button', { name: 'Clear all' }).click()
  await expect(inStock).not.toBeChecked()

  await page.getByRole('combobox', { name: 'Sort by' }).click()
  await page.getByRole('option', { name: 'Price, low to high' }).click()
  await expect(grid(page).getByRole('heading', { level: 3 })).toHaveText(byPrice)
  await page.getByRole('combobox', { name: 'Sort by' }).click()
  await page.getByRole('option', { name: 'Price, high to low' }).click()
  await expect(grid(page).getByRole('heading', { level: 3 })).toHaveText([...byPrice].reverse())
  await inStock.check()
  await expect(grid(page).getByRole('heading', { level: 3 })).toHaveText([...byPrice].reverse().filter((title) => title !== 'Wren Coffee Table'))
})

test('an unknown category is a 404 and the old query forms move to the category path', async ({ page, request }) => {
  expect((await page.goto('/shop/garden'))?.status()).toBe(404)
  const old = await request.get('/shop?collection=dining-room', { maxRedirects: 0 })
  expect(old.status()).toBe(308)
  expect(old.headers().location).toMatch(/\/shop\/dining-room$/)
})

test('the home page links each category with its count', async ({ page }) => {
  await page.goto('/')
  const tiles = page.getByRole('region', { name: 'Shop by category' })
  await expect(tiles.getByRole('link')).toHaveText([/Sofas & Armchairs.*2 pieces/, /Dining Room.*1 piece/, /Bedroom.*1 piece/, /Coffee & Console Tables.*1 piece/])
  await tiles.getByRole('link', { name: /Bedroom/ }).click()
  await expect(page).toHaveURL(/\/shop\/bedroom$/)
})

test('at 390px the filters sit in a drawer and nothing scrolls sideways', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/shop')
  await expect(page.getByRole('complementary', { name: 'Filters' })).toBeHidden()
  await page.getByRole('button', { name: 'Filters' }).click()
  const drawer = page.getByRole('dialog', { name: 'Filters' })
  await drawer.getByRole('checkbox', { name: 'Made to order (1)' }).check()
  await drawer.getByRole('button', { name: 'Show 1 piece' }).click()
  await expect(drawer).toBeHidden()
  await expect(grid(page).getByRole('heading', { level: 3 })).toHaveText(['Wren Coffee Table'])
  await expect(page.getByRole('button', { name: 'Filters 1' })).toBeVisible()
  expect(await noHorizontalScroll(page)).toBe(true)
  await page.goto('/shop/sofas-armchairs')
  await expect(grid(page)).toBeVisible()
  expect(await noHorizontalScroll(page)).toBe(true)
})
