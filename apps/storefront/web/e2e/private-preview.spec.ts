import { expect, request, test } from '@playwright/test'

const previewUrl = process.env.PLAYWRIGHT_BASE_URL
const username = process.env.STOREFRONT_PREVIEW_USERNAME
const password = process.env.STOREFRONT_PREVIEW_PASSWORD

test('private preview challenges anonymous traffic and serves no-index pages to its preview user', async () => {
  test.skip(!previewUrl || !username || !password, 'Set preview URL and server-side credentials for the hosted private-preview check')

  const anonymous = await request.newContext({ baseURL: previewUrl })
  const authenticated = await request.newContext({
    baseURL: previewUrl,
    httpCredentials: { username: username!, password: password! },
  })

  try {
    const denied = await anonymous.get('/shop')
    expect(denied.status()).toBe(401)
    expect(denied.headers()['www-authenticate']).toContain('Basic')
    expect(denied.headers()['x-robots-tag']).toContain('noindex')

    const health = await anonymous.get('/api/health')
    expect(health.status()).toBe(200)
    expect(await health.json()).toEqual({ status: 'ok' })
    expect(health.headers()['x-robots-tag']).toContain('noindex')

    const page = await authenticated.get('/shop')
    expect(page.status()).toBe(200)
    expect(page.headers()['x-robots-tag']).toContain('noindex')
    expect(await page.text()).toMatch(/<meta[^>]+name="robots"[^>]+noindex/i)
  } finally {
    await Promise.all([anonymous.dispose(), authenticated.dispose()])
  }
})
