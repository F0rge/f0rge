import { devices, expect, test, type Locator, type Page } from '@playwright/test'

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
const card = (page: Page, title: string) => grid(page).getByRole('listitem').filter({ has: page.getByRole('heading', { level: 3, name: title, exact: true }) })
// The photo link sits in the horizontal scroller; its index is the photo in view.
const photoInView = (photos: Locator) => photos.evaluate((link) => Math.round(link.parentElement!.scrollLeft / link.parentElement!.clientWidth))

test('the menu opens each category with only its pieces; an uncategorised piece is only in Shop all', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/shop')
  await expect(page.getByRole('heading', { level: 1, name: 'Shop all' })).toBeVisible()
  expect(await titles(page)).toEqual(byName)
  for (const [name, pieces] of categories) {
    await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name, exact: true }).click()
    await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
    await expect(page.getByRole('heading', { level: 2, name: 'Pieces', exact: true })).toHaveCount(1)
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
  await expect(grid(page).getByRole('heading', { level: 3 })).toHaveText(['Wren Coffee Table'])
  await expect(card(page, 'Wren Coffee Table')).toContainText('Made to order')
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

test('category and price filters combine, keep counts in sync and survive reload and back', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/shop?utm_source=fixture')
  const filters = page.getByRole('complementary', { name: 'Filters' })
  await expect(filters.getByRole('link')).toHaveCount(0)
  await filters.getByRole('checkbox', { name: 'Sofas & Armchairs (2)' }).check()
  await filters.getByRole('checkbox', { name: 'Under R7 500 (1)' }).check()
  await expect(grid(page).getByRole('heading')).toHaveText(['Test chair'])
  await expect(page).toHaveURL(/utm_source=fixture&categories=sofas-armchairs&price=under-7500/)
  await page.reload()
  await expect(grid(page).getByRole('heading')).toHaveText(['Test chair'])
  await page.goBack()
  await expect(grid(page).getByRole('heading')).toHaveText(['Test chair', 'Tilda Sofa'])
  await expect(filters.getByRole('checkbox', { name: 'Under R7 500 (1)' })).not.toBeChecked()
})

test('desktop card arrows and keyboard keep the shopper on the listing', async ({ page }) => {
  await page.goto('/shop')
  const chair = card(page, 'Test chair')
  const photos = chair.getByRole('link', { name: 'Test chair, 2 photos' })
  const next = chair.getByRole('button', { name: 'Next photo of Test chair' })
  const previous = chair.getByRole('button', { name: 'Previous photo of Test chair' })
  await expect(chair.getByRole('img', { name: 'Test chair, photo 1 of 2' })).toHaveCSS('object-fit', 'contain')
  await chair.hover()
  await next.click()
  await expect.poll(() => photoInView(photos)).toBe(1)
  await expect(chair.getByText('Photo 2 of 2')).toHaveAttribute('aria-live', 'polite')
  await expect(next).toBeDisabled()
  await photos.press('ArrowLeft')
  await expect.poll(() => photoInView(photos)).toBe(0)
  await expect(previous).toBeDisabled()
  await expect(grid(page).getByRole('button', { name: 'Next photo of Tilda Sofa' })).toHaveCount(0)
  await expect(page).toHaveURL(/\/shop$/)
  await chair.getByRole('link', { name: 'Test chair', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Test chair')
})

test('a mouse drag swipes the photos without opening the piece', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/shop')
  const photos = card(page, 'Test chair').getByRole('link', { name: 'Test chair, 2 photos' })
  const box = (await photos.boundingBox())!
  await page.mouse.move(box.x + box.width * 0.8, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * 0.2, box.y + box.height / 2, { steps: 8 })
  await page.mouse.up()
  await expect.poll(() => photoInView(photos)).toBe(1)
  await expect(page).toHaveURL(/\/shop$/)
})

test('each card shows at most one alert, and finish dots switch the photos, price and link', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/shop')
  const sofa = card(page, 'Tilda Sofa')
  await expect(sofa).toContainText(/17% off, save R\s4\s000/)
  await expect(sofa.locator('s')).toHaveText(/Was R\s22\s999,00/)
  await expect(card(page, 'Test chair')).toContainText('Just arrived')
  await expect(card(page, 'Wren Coffee Table')).toContainText('Made to order')
  await expect(card(page, 'Yara Floor Lamp')).not.toContainText(/In stock|Just arrived|Made to order|% off/)
  await expect(grid(page)).not.toContainText('In stock')

  const table = card(page, 'Umbra Dining Table')
  // One dot per colour: both gold sizes share a dot, which opens the gold size in stock.
  const finishes = table.getByRole('group', { name: 'Finishes of Umbra Dining Table' })
  await expect(finishes.getByRole('button')).toHaveCount(2)
  await expect(finishes.getByRole('button', { name: 'Silver / 200 cm' })).toHaveAttribute('aria-pressed', 'true')
  await finishes.getByRole('button', { name: 'Gold', exact: true }).click()
  await expect(finishes.getByRole('button', { name: 'Gold', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(finishes.getByRole('button', { name: 'Silver / 200 cm' })).toHaveAttribute('aria-pressed', 'false')
  await expect(table.getByRole('img', { name: 'Umbra Dining Table, photo 1 of 1' })).toHaveAttribute('src', '/demo/arc-front.jpg')
  await expect(table).toContainText(/R\s37\s000,00/)
  for (const link of await table.getByRole('link').all()) await expect(link).toHaveAttribute('href', /\?variant=variant_umbra_gold_small$/)
  // A new filter result keeps the card (and the shopper's finish) rather than remounting it.
  await page.getByRole('complementary', { name: 'Filters' }).getByRole('checkbox', { name: /^In stock/ }).check()
  await expect(finishes.getByRole('button', { name: 'Gold', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(card(page, 'Tilda Sofa').getByRole('group', { name: /^Finishes/ })).toHaveCount(0)
})

test.describe('touch product cards', () => {
  test.use({ viewport: devices['iPhone 13'].viewport, hasTouch: true, isMobile: true })

  test('a native horizontal touch swipe exposes the next photo', async ({ context, page }) => {
    await page.goto('/shop')
    await page.getByRole('button', { name: 'Reject optional analytics' }).click()
    await expect(page.getByRole('region', { name: 'Your privacy choices' })).toBeHidden()
    const photos = card(page, 'Test chair').getByRole('link', { name: 'Test chair, 2 photos' })
    const track = photos.locator('..')
    await track.evaluate((element) => element.scrollIntoView({ block: 'center' }))
    const rect = await track.boundingBox()
    expect(rect).not.toBeNull()
    const { x, y, width, height } = rect!
    const session = await context.newCDPSession(page)
    const hit = (ratio: number) => ({ x: x + width * ratio, y: y + height / 2 })
    await session.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [hit(0.9)] })
    for (const ratio of [0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]) {
      await session.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [hit(ratio)] })
    }
    await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await expect.poll(() => photoInView(photos)).toBe(1)
    await expect(page).toHaveURL(/\/shop$/)
  })
})

test('an unknown category is a 404 and the old query forms move to the category path', async ({ page, request }) => {
  expect((await page.goto('/shop/garden'))?.status()).toBe(404)
  const old = await request.get('/shop?collection=dining-room', { maxRedirects: 0 })
  expect(old.status()).toBe(308)
  expect(old.headers().location).toMatch(/\/shop\/dining-room$/)
})

test('the home page links each category with its count', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveTitle('DasKasas | Furniture Store in Bedfordview')
  await expect(page.locator('meta[name="description"]')).toHaveAttribute(
    'content', 'Shop sofas, armchairs, dining tables and bedroom furniture online, or visit the DasKasas showroom at Bedford Square.',
  )
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Furniture store in Bedfordview')
  const hero = page.getByRole('img', { name: /^Ivory Salon/ })
  await expect(hero).toHaveAttribute('srcset', /home-ivory-salon\.webp.*640w/)
  await expect.poll(() => hero.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0)
  const tiles = page.getByRole('region', { name: 'Shop by category' })
  await expect(tiles.getByRole('link')).toHaveText([/Sofas & Armchairs.*2 pieces/, /Dining Room.*1 piece/, /Bedroom.*1 piece/, /Coffee & Console Tables.*1 piece/])
  expect(await tiles.getByRole('link').evaluateAll((links) => links.map((link) => link.getAttribute('href')))).toEqual([
    '/shop/sofas-armchairs', '/shop/dining-room', '/shop/bedroom', '/shop/coffee-console-tables',
  ])
  expect(await tiles.locator('img').evaluateAll((images) => images.map((image) => image.getAttribute('src')))).toEqual([
    '/merchandising/category-sofas-armchairs.webp',
    '/merchandising/category-dining-room.webp',
    '/merchandising/category-bedroom.webp',
    '/merchandising/category-coffee-console-tables.webp',
  ])
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
