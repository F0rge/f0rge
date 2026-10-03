import { expect, test } from '@playwright/test'

const sourceSkuId = process.env.STOREFRONT_TEST_BAG_MULTI_SKU_ID || process.env.STOREFRONT_TEST_SKU_ID
const lastUnitSkuId = process.env.STOREFRONT_TEST_LAST_UNIT_SKU_ID
const publishableKey = process.env.STOREFRONT_TEST_MEDUSA_PUBLISHABLE_KEY

test('direct Medusa cart access requires the server-only credential', async ({ request }) => {
  test.skip(!publishableKey, 'Set STOREFRONT_TEST_MEDUSA_PUBLISHABLE_KEY for the direct API security check')
  const response = await request.get(`${process.env.MEDUSA_BACKEND_URL || 'http://127.0.0.1:9000'}/store/carts/cart_other_shopper`, {
    headers: { 'x-publishable-api-key': publishableKey! },
  })
  expect(response.status()).toBe(403)
})

test('a shopper can restore, edit, and remove a server-backed bag across navigation', async ({ page }) => {
  test.skip(!sourceSkuId, 'Set STOREFRONT_TEST_SKU_ID to a published SKU with at least two units')

  await page.goto(`/product/${sourceSkuId}`)
  await page.getByRole('button', { name: 'Add to bag' }).click()
  await expect(page.getByText('Added to bag. Review your bag when ready.')).toBeVisible()
  await page.getByRole('link', { name: 'View bag' }).click()
  await expect(page).toHaveURL(/\/bag$/)
  await expect(page.getByRole('spinbutton')).toHaveValue('1')
  const initialTotal = await page.locator('[data-testid="bag-total"]').innerText()
  const bag = await (await page.request.get('/api/bag')).json() as { items: { id: string }[] }
  for (const invalidQuantity of [0, -1, 1.5, 100]) {
    const rejected = await page.request.patch('/api/bag', {
      data: { item_id: bag.items[0].id, quantity: invalidQuantity },
    })
    expect(rejected.status()).toBe(400)
  }
  expect((await (await page.request.get('/api/bag')).json()).items[0].quantity).toBe(1)

  await page.reload()
  await expect(page.getByRole('spinbutton')).toHaveValue('1')
  await page.getByRole('link', { name: /Shop/i }).first().click()
  await page.getByRole('link', { name: 'Bag' }).click()
  await expect(page.getByRole('spinbutton')).toHaveValue('1')

  await page.getByRole('spinbutton').fill('2')
  await page.getByRole('spinbutton').press('Tab')
  await expect(page.getByRole('spinbutton')).toHaveValue('2')
  await expect(page.locator('[data-testid="bag-total"]')).not.toHaveText(initialTotal)
  await page.reload()
  await expect(page.getByRole('spinbutton')).toHaveValue('2')

  await page.getByRole('button', { name: 'Continue to checkout' }).click()
  await expect(page.getByText(/reserved until/i)).toBeVisible()
  await page.getByRole('button', { name: 'Change bag' }).click()
  await expect(page.getByRole('button', { name: 'Continue to checkout' })).toBeVisible()
  await page.getByRole('spinbutton').fill('1')
  await page.getByRole('spinbutton').press('Tab')
  await expect(page.locator('[data-testid="bag-total"]')).toHaveText(initialTotal)

  await page.getByRole('button', { name: 'Remove' }).click()
  await expect(page.getByText(/your bag is empty/i)).toBeVisible()
  await page.reload()
  await expect(page.getByText(/your bag is empty/i)).toBeVisible()
})

test('two independent shoppers cannot both reserve the final unit', async ({ browser }) => {
  test.skip(!lastUnitSkuId, 'Set STOREFRONT_TEST_LAST_UNIT_SKU_ID to a published SKU with exactly one free unit')

  const first = await browser.newContext()
  const second = await browser.newContext()
  try {
    const firstPage = await first.newPage()
    const secondPage = await second.newPage()
    await Promise.all([firstPage.goto(`/product/${lastUnitSkuId}`), secondPage.goto(`/product/${lastUnitSkuId}`)])
    await Promise.all([
      firstPage.getByRole('button', { name: 'Add to bag' }).click(),
      secondPage.getByRole('button', { name: 'Add to bag' }).click(),
    ])
    await Promise.all([
      expect(firstPage.getByText('Added to bag. Review your bag when ready.')).toBeVisible(),
      expect(secondPage.getByText('Added to bag. Review your bag when ready.')).toBeVisible(),
    ])
    await Promise.all([firstPage.goto('/bag'), secondPage.goto('/bag')])
    await Promise.all([
      firstPage.getByRole('button', { name: 'Continue to checkout' }).click(),
      secondPage.getByRole('button', { name: 'Continue to checkout' }).click(),
    ])
    await Promise.all([
      expect(firstPage.locator('.bag-summary [role="status"]')).toBeVisible(),
      expect(secondPage.locator('.bag-summary [role="status"]')).toBeVisible(),
    ])
    const firstReserved = await firstPage.getByText(/reserved until/i).isVisible()
    const secondReserved = await secondPage.getByText(/reserved until/i).isVisible()
    expect(Number(firstReserved) + Number(secondReserved)).toBe(1)
    await expect(firstPage.getByRole('spinbutton')).toHaveValue('1')
    await expect(secondPage.getByRole('spinbutton')).toHaveValue('1')
  } finally {
    await Promise.allSettled([
      first.request.delete('/api/bag/checkout'),
      second.request.delete('/api/bag/checkout'),
    ])
    await first.close()
    await second.close()
  }
})

test('one shopper cannot edit a different shopper’s bag line by its ID', async ({ browser }) => {
  test.skip(!sourceSkuId, 'Set STOREFRONT_TEST_SKU_ID to a published SKU')

  const first = await browser.newContext()
  const second = await browser.newContext()
  try {
    const firstPage = await first.newPage()
    const secondPage = await second.newPage()
    for (const page of [firstPage, secondPage]) {
      await page.goto(`/product/${sourceSkuId}`)
      await page.getByRole('button', { name: 'Add to bag' }).click()
      await expect(page.getByText('Added to bag. Review your bag when ready.')).toBeVisible()
    }
    const firstBag = await (await first.request.get('/api/bag')).json() as { id: string; items: { id: string; quantity: number }[] }
    const secondBag = await (await second.request.get('/api/bag')).json() as { id: string; items: { id: string; quantity: number }[] }
    expect(firstBag.id).not.toBe(secondBag.id)
    const denied = await second.request.patch('/api/bag', {
      data: { item_id: firstBag.items[0].id, quantity: 2 },
    })
    expect(denied.status()).toBe(404)
    expect((await (await first.request.get('/api/bag')).json()).items[0].quantity).toBe(1)
    expect((await (await second.request.get('/api/bag')).json()).items[0].quantity).toBe(1)
  } finally {
    await first.close()
    await second.close()
  }
})
