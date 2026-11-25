import { expect, test, type Page } from '@playwright/test'

// Runs against the local Medusa fixture (e2e/analytics-medusa-fixture.mjs), which has no card provider; see the storefront README.
const tilda = '/product/22222222-2222-4222-8222-222222222222'
const chair = '/product/11111111-1111-4111-8111-111111111111'

const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)
const bagButton = (page: Page) => page.getByRole('banner').getByRole('button', { name: /^Bag, / })

async function addToBag(page: Page, path: string) {
  await page.goto(path)
  await page.getByRole('button', { name: 'Add to bag' }).click()
  const drawer = page.getByRole('dialog', { name: 'Your bag' })
  await expect(drawer).toBeVisible()
  return drawer
}

async function fillContact(page: Page) {
  await page.getByLabel('Email').fill('fixture-guest@example.com')
  await page.getByLabel('First name').fill('Fixture')
  await page.getByLabel('Last name').fill('Guest')
  await page.getByLabel('Phone').fill('+27110000000')
}

async function expectUnavailableAndReleased(page: Page) {
  const step = page.getByTestId('card-payment-unavailable')
  await expect(step.getByRole('heading', { name: 'Card payment isn’t available yet' })).toBeFocused()
  for (const fact of ['+27 63 025 4010', '010 745 1980', 'Cindy@daskasas.co.za', 'call us or visit the showroom', 'No order was placed']) await expect(step).toContainText(fact)
  await expect(step.getByRole('link', { name: '+27 63 025 4010' })).toHaveAttribute('href', 'tel:+27630254010')
  await expect(step).toContainText('Your pieces are no longer reserved.')
  const bag = await (await page.request.get('/api/bag')).json() as { items: unknown[]; hold: { status: string } | null }
  expect(bag.hold?.status).toBe('cancelled')
  expect(bag.items).toHaveLength(1)
  expect((await page.request.get('/api/order/confirmation')).status()).toBe(404)
}

test('adding opens the drawer; quantity is capped at stock; remove empties the bag; the bag survives a reload', async ({ page }) => {
  await page.goto('/')
  await expect(bagButton(page)).toHaveAccessibleName('Bag, 0 items')

  const drawer = await addToBag(page, tilda)
  await expect(drawer.getByRole('heading', { name: 'Tilda Sofa' })).toBeVisible()
  await expect(drawer.getByTestId('bag-subtotal')).toHaveText(/^R\s18\s999,00$/)
  await expect(drawer).toContainText('Confirmed before payment')

  // Two in stock: the second unit is the last one the stepper allows.
  const increase = drawer.getByRole('button', { name: 'Increase Quantity of Tilda Sofa' })
  await increase.click()
  await expect(drawer.getByLabel('Quantity of Tilda Sofa: 2')).toBeVisible()
  await expect(increase).toBeDisabled()
  await expect(drawer.getByTestId('bag-subtotal')).toHaveText(/^R\s37\s998,00$/)
  // The modal drawer hides the header from assistive tech while it is open.
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()
  await expect(bagButton(page)).toHaveAccessibleName('Bag, 2 items')
  await expect(page.getByTestId('bag-count')).toHaveText('2')

  await page.reload()
  await expect(bagButton(page)).toHaveAccessibleName('Bag, 2 items')
  await bagButton(page).click()
  await expect(drawer.getByLabel('Quantity of Tilda Sofa: 2')).toBeVisible()
  await drawer.getByRole('link', { name: 'View bag' }).click()
  await expect(page).toHaveURL(/\/bag$/)
  await expect(drawer).toBeHidden()

  const main = page.getByRole('main')
  await expect(main.getByRole('heading', { name: 'Your bag', level: 1 })).toBeVisible()
  await expect(main).toContainText('2 items in your bag')
  await main.getByRole('button', { name: 'Decrease Quantity of Tilda Sofa' }).click()
  await expect(main.getByLabel('Quantity of Tilda Sofa: 1')).toBeVisible()
  await expect(main.getByTestId('bag-total')).toHaveText(/^R\s18\s999,00$/)
  await page.reload()
  await expect(main.getByLabel('Quantity of Tilda Sofa: 1')).toBeVisible()

  await main.getByRole('button', { name: 'Remove Tilda Sofa' }).click()
  await expect(main.getByText('Your bag is empty.')).toBeVisible()
  await expect(bagButton(page)).toHaveAccessibleName('Bag, 0 items')
  await page.reload()
  await expect(main.getByText('Your bag is empty.')).toBeVisible()
})

test('reduces a stale bag line directly to an available quantity', async ({ page }) => {
  const fixture = {
    id: 'cart_stale',
    currency_code: 'zar',
    items: [{
      id: 'cali_stale', variant_id: 'variant_tilda', title: 'Tilda Sofa',
      quantity: 4, max_quantity: 2, unit_price: 18_999, total: 75_996,
    }],
    subtotal: 75_996,
    hold: null,
  }
  await page.route('**/api/bag', async (route) => {
    if (route.request().method() === 'PATCH') {
      expect(route.request().postDataJSON()).toEqual({ item_id: 'cali_stale', quantity: 2 })
      await route.fulfill({ json: { ...fixture, items: [{ ...fixture.items[0], quantity: 2 }] } })
    } else {
      await route.fulfill({ json: fixture })
    }
  })
  await page.goto('/bag')
  const main = page.getByRole('main')
  await expect(main.getByLabel('Quantity of Tilda Sofa: 4')).toBeVisible()
  await main.getByRole('button', { name: 'Decrease Quantity of Tilda Sofa' }).click()
  await expect(main.getByLabel('Quantity of Tilda Sofa: 2')).toBeVisible()
})

test('checkout with delivery reaches the card-payment-unavailable step and releases the hold', async ({ page }) => {
  const drawer = await addToBag(page, chair)
  await drawer.getByRole('button', { name: 'Checkout' }).click()
  await expect(page).toHaveURL(/\/checkout$/)
  await expect(page.getByRole('heading', { name: 'Checkout', level: 1 })).toBeVisible()
  await expect(page.getByRole('main')).toContainText('Your pieces are reserved until')

  await fillContact(page)
  await expect(page.getByLabel('Delivery', { exact: true })).toBeChecked()
  await expect(page.getByLabel('Delivery', { exact: true })).toHaveAccessibleDescription('Johannesburg: R1,100 · Pretoria: R1,300, VAT included. Coverage and the charge are confirmed before payment.')
  await expect(page.getByRole('main').getByText('Confirmed before payment', { exact: true })).toBeVisible()
  await page.getByLabel('Street address').fill('1 Fixture Street')
  await page.getByLabel('Suburb or area').fill('Bedfordview')
  await page.getByLabel('City').fill('Johannesburg')
  await expect(page.getByLabel('Province')).toHaveValue('Gauteng')
  await page.getByLabel('Postal code').fill('2007')

  await expect(page.getByRole('button', { name: 'Continue to payment' })).toHaveCount(0)
  await expect(page.getByTestId('card-payment-unavailable')).toHaveCount(0)
  const prepared = page.waitForRequest((request) => request.url().endsWith('/api/checkout/prepare'))
  await page.getByRole('button', { name: 'Review order' }).click()
  expect((await prepared).postDataJSON()).toMatchObject({ step: 'review', fulfillment_type: 'delivery', province: 'Gauteng', city: 'Johannesburg', address_2: 'Bedfordview', postal_code: '2007' })
  await expectUnavailableAndReleased(page)

  // The released bag is editable again.
  await page.getByRole('link', { name: 'Back to bag' }).click()
  await expect(page.getByRole('main').getByRole('button', { name: 'Continue to checkout' })).toBeEnabled()
  await expect(page.getByRole('main').getByRole('button', { name: 'Remove Test chair' })).toBeVisible()
  await expect(bagButton(page)).toHaveAccessibleName('Bag, 1 item')
})

test('checkout shows free Wynberg collection by appointment and reaches the unavailable step', async ({ page }) => {
  await addToBag(page, chair)
  await page.goto('/bag')
  await expect(page.getByRole('main')).toContainText(/If you buy online, you may cancel within 7 days.+Our own policy: .+within 30 days after delivery or collection/)
  await expect(page.getByRole('main')).not.toContainText('Draft for owner and legal review before go-live.')
  await page.getByRole('main').getByRole('button', { name: 'Continue to checkout' }).click()
  await expect(page).toHaveURL(/\/checkout$/)
  await fillContact(page)
  await page.getByLabel('Collection', { exact: true }).check()
  const collection = page.getByRole('region', { name: 'Collect in Wynberg' })
  await expect(collection).toContainText('32 4th Street, Wynberg, Sandton, Gauteng, 2090')
  await expect(collection).toContainText('Collection is free and by appointment.')
  await expect(collection).toContainText('Bring your order confirmation.')
  await expect(page.getByLabel('Street address')).toHaveCount(0)
  await expect(page.getByRole('main').getByText('Free', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Review order' }).click()
  await expectUnavailableAndReleased(page)
})

test('review shows the full delivery price and terms before payment and lets a customer correct their details', async ({ page }) => {
  const checkoutSteps: string[] = []
  await page.route('**/api/checkout/prepare', async (route) => {
    const input = route.request().postDataJSON() as { step: string; city: string; review_token?: string }
    checkoutSteps.push(input.step)
    if (input.step === 'review') {
      const delivery = input.city === 'Johannesburg' ? 1100 : 1300
      return route.fulfill({ json: { quote: {
        amount: 5000 + delivery, currency_code: 'zar', delivery_amount: delivery, review_token: input.city,
        hold_expires_at: new Date(Date.now() + 5 * 60_000).toISOString(),
        items: [{ id: 'cali_latest', title: 'Latest chair', quantity: 2, total: 5000 }],
      } } })
    }
    expect(input).toMatchObject({ step: 'payment', city: 'Pretoria', review_token: 'Pretoria' })
    return route.fulfill({ status: 409, json: { code: 'checkout_review_changed', message: 'Your total changed. Review your order again.' } })
  })
  await page.setViewportSize({ width: 390, height: 844 })
  const drawer = await addToBag(page, chair)
  await drawer.getByRole('button', { name: 'Checkout' }).click()
  await fillContact(page)
  await page.getByLabel('Street address').fill('1 Fixture Street')
  await page.getByLabel('Suburb or area').fill('Example')
  await page.getByLabel('City').fill('Johannesburg')
  await page.getByLabel('Postal code').fill('2007')
  await page.getByRole('button', { name: 'Review order' }).click()
  await expect(page.getByRole('heading', { name: 'Review your order' })).toBeFocused()
  await expect(page.getByTestId('checkout-review-delivery')).toHaveText(/^R\s1\s100,00$/)
  await expect(page.getByTestId('checkout-review-total')).toHaveText(/^R\s6\s100,00$/)
  await expect(page.getByText('2 × Latest chair', { exact: true })).toBeVisible()
  await expect(page.getByText('Test chair', { exact: true })).toHaveCount(0)
  expect(checkoutSteps).toEqual(['review'])
  expect(await noHorizontalScroll(page)).toBe(true)

  const beforeYouPay = page.getByRole('region', { name: 'Before you pay' })
  const pay = page.getByRole('button', { name: 'Continue to payment' })
  await expect(beforeYouPay).toContainText('Wood, leather and natural fabrics vary')
  await expect(beforeYouPay.getByRole('link', { name: 'Read our full terms of sale' })).toHaveAttribute('href', '/policies/terms')
  await expect(pay).toHaveAccessibleDescription('By continuing you accept our terms of sale.')
  expect(await beforeYouPay.evaluate((box, button) => Boolean(box.compareDocumentPosition(button!) & Node.DOCUMENT_POSITION_FOLLOWING), await pay.elementHandle())).toBe(true)

  await page.getByRole('button', { name: 'Edit details' }).click()
  await expect(page.getByLabel('Street address')).toHaveValue('1 Fixture Street')
  await page.getByLabel('City').fill('Pretoria')
  await page.getByRole('button', { name: 'Review order' }).click()
  await expect(page.getByTestId('checkout-review-delivery')).toHaveText(/^R\s1\s300,00$/)
  await expect(page.getByTestId('checkout-review-total')).toHaveText(/^R\s6\s300,00$/)
  await page.getByRole('button', { name: 'Continue to payment' }).click()
  await expect(page.getByText('Your total changed. Review your order again.')).toBeFocused()
  await expect(page.getByLabel('City')).toHaveValue('Pretoria')
  await expect(pay).toHaveCount(0)
  expect(checkoutSteps).toEqual(['review', 'review', 'payment'])
})

test('bag, drawer and checkout fit 390px without horizontal scroll', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const drawer = await addToBag(page, tilda)
  expect(await drawer.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
  await drawer.getByRole('link', { name: 'View bag' }).click()
  await expect(page.getByRole('main').getByRole('heading', { name: 'Tilda Sofa' })).toBeVisible()
  expect(await noHorizontalScroll(page)).toBe(true)
  await page.getByRole('main').getByRole('button', { name: 'Continue to checkout' }).click()
  await expect(page.getByLabel('Email')).toBeVisible()
  expect(await noHorizontalScroll(page)).toBe(true)
  await page.getByLabel('Collection', { exact: true }).check()
  expect(await noHorizontalScroll(page)).toBe(true)
})
