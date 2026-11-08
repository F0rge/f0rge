import { existsSync } from 'node:fs'

jest.mock('node:fs', () => ({
  ...jest.requireActual('node:fs'),
  existsSync: jest.fn(jest.requireActual('node:fs').existsSync),
}))

import { assertHostedCommerceConfig } from './hosted-commerce-config'

const originalArgv = process.argv
beforeEach(() => { process.argv = [originalArgv[0], 'medusa', 'develop', '--host', '127.0.0.1'] })
afterEach(() => { process.argv = originalArgv })

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

  it('requires real configuration when local isolation has not been established', () => {
    expect(() => assertHostedCommerceConfig({})).toThrow(/DATABASE_URL/)
    expect(() => assertHostedCommerceConfig({ STOREFRONT_RUNTIME_KIND: 'local', NODE_ENV: 'development' })).toThrow(/DATABASE_URL/)
  })

  it('keeps a complete loopback development setup available without hosted secrets', () => {
    const local = {
      NODE_ENV: 'development', HOST: '127.0.0.1', STOREFRONT_RUNTIME_KIND: 'local',
      DATABASE_URL: 'postgres://test:test@localhost/storefront', REDIS_URL: 'redis://localhost:6379',
      STOREFRONT_PUBLIC_URL: 'http://localhost:3004', STORE_CORS: 'http://localhost:3004',
      ADMIN_CORS: 'http://localhost:9000', AUTH_CORS: 'http://localhost:3004',
    }
    expect(() => assertHostedCommerceConfig(local)).not.toThrow()
    const actualExists = jest.requireActual('node:fs').existsSync
    jest.mocked(existsSync).mockImplementation((path) => path === '/usr/local/share/daskasas/hosted-artifact' || actualExists(path))
    try {
      expect(() => assertHostedCommerceConfig(local)).toThrow(/JWT_SECRET/)
      expect(() => assertHostedCommerceConfig({ ...local, ...hosted, STOREFRONT_RUNTIME_KIND: 'local' })).not.toThrow()
    } finally {
      jest.mocked(existsSync).mockImplementation(actualExists)
    }
  })

  it('fails closed in Railway even if the runtime-kind flag is missing', () => {
    expect(() => assertHostedCommerceConfig({ RAILWAY_PROJECT_ID: 'local-test' })).toThrow(/DATABASE_URL/)
  })
})
