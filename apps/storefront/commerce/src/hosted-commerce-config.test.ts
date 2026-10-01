import { assertHostedCommerceConfig } from './hosted-commerce-config'

const hosted = {
  STOREFRONT_RUNTIME_KIND: 'hosted',
  DATABASE_URL: 'postgres://storefront:test@localhost/storefront',
  REDIS_URL: 'redis://localhost:6379',
  JWT_SECRET: 'jwt-secret-with-at-least-32-characters-here',
  COOKIE_SECRET: 'cookie-secret-with-at-least-32-characters-here',
  STOREFRONT_BFF_SECRET: 'storefront-bff-secret-with-at-least-32-characters',
}

describe('assertHostedCommerceConfig', () => {
  it('accepts a dedicated database, Redis, and server secrets in hosted mode', () => {
    expect(() => assertHostedCommerceConfig(hosted)).not.toThrow()
  })

  it('requires Redis rather than Medusa’s in-memory fallback in hosted mode', () => {
    expect(() => assertHostedCommerceConfig({ ...hosted, REDIS_URL: undefined })).toThrow(/REDIS_URL/)
  })

  it('requires a strong BFF secret in hosted mode', () => {
    expect(() => assertHostedCommerceConfig({ ...hosted, STOREFRONT_BFF_SECRET: 'short' })).toThrow(/STOREFRONT_BFF_SECRET/)
  })

  it('requires strong Medusa auth secrets in hosted mode', () => {
    expect(() => assertHostedCommerceConfig({ ...hosted, JWT_SECRET: 'short' })).toThrow(/JWT_SECRET/)
    expect(() => assertHostedCommerceConfig({ ...hosted, COOKIE_SECRET: 'short' })).toThrow(/COOKIE_SECRET/)
  })

  it('does not change local development configuration', () => {
    expect(() => assertHostedCommerceConfig({})).not.toThrow()
  })

  it('fails closed in Railway even if the runtime-kind flag is missing', () => {
    expect(() => assertHostedCommerceConfig({ RAILWAY_PROJECT_ID: 'local-test' })).toThrow(/DATABASE_URL/)
  })
})
