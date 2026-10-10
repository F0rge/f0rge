import { hostedLocalFileOptions, publicFileBackendUrl } from './file-storage-url'

describe('publicFileBackendUrl', () => {
  it('uses the Railway public host for product image URLs', () => {
    expect(publicFileBackendUrl({
      RAILWAY_PUBLIC_DOMAIN: 'storefront-commerce-production.up.railway.app',
    })).toBe('https://storefront-commerce-production.up.railway.app/static')
  })

  it('keeps the local Medusa static URL in development', () => {
    expect(publicFileBackendUrl({})).toBe('http://localhost:9000/static')
    expect(publicFileBackendUrl({ RAILWAY_PUBLIC_DOMAIN: '  ' })).toBe('http://localhost:9000/static')
  })
})

describe('hostedLocalFileOptions', () => {
  it('writes hosted uploads into the volume mount', () => {
    expect(hostedLocalFileOptions({
      RAILWAY_PUBLIC_DOMAIN: 'storefront-commerce-production.up.railway.app',
    })).toEqual({
      backend_url: 'https://storefront-commerce-production.up.railway.app/static',
      upload_dir: '/app/apps/storefront/commerce/.medusa/server/static',
      private_upload_dir: '/app/apps/storefront/commerce/.medusa/server/static',
    })
  })

  it('leaves the upload directory to Medusa locally', () => {
    expect(hostedLocalFileOptions({})).toEqual({
      backend_url: 'http://localhost:9000/static',
    })
  })
})
