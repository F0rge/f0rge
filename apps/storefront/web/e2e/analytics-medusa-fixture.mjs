import { createServer } from 'node:http'

const port = Number(process.env.STOREFRONT_ANALYTICS_MEDUSA_PORT || 9011)
const sku = '11111111-1111-4111-8111-111111111111'
const product = {
  id: 'prod_test_chair',
  handle: `firstout-${sku}`,
  title: 'Test chair',
  description: 'Local analytics browser fixture.',
  status: 'published',
  thumbnail: '/demo/arc-front.jpg',
  images: [{ id: 'img_test', url: '/demo/arc-front.jpg' }],
  variants: [{
    id: 'var_test_chair',
    sku: 'TEST-CHAIR',
    title: 'Default',
    inventory_quantity: 1,
    calculated_price: { calculated_amount: 2400, currency_code: 'zar' },
    options: [],
  }],
  categories: [{ id: 'cat_test', name: 'Chairs', handle: 'chairs' }],
  collection: { id: 'col_test', title: 'Living', handle: 'living' },
}

createServer((request, response) => {
  const url = new URL(request.url || '/', `http://127.0.0.1:${port}`)
  response.setHeader('content-type', 'application/json')
  if (url.pathname === '/store/regions') {
    response.end(JSON.stringify({ regions: [{ id: 'reg_test', currency_code: 'zar' }] }))
    return
  }
  if (url.pathname === '/store/products') {
    response.end(JSON.stringify({ products: [product], count: 1 }))
    return
  }
  response.statusCode = 404
  response.end(JSON.stringify({ message: 'not found' }))
}).listen(port, '127.0.0.1', () => console.log(`analytics Medusa fixture on 127.0.0.1:${port}`))
