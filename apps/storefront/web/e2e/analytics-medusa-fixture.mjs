import { createServer } from 'node:http'

const port = Number(process.env.STOREFRONT_ANALYTICS_MEDUSA_PORT || 9011)
const category = (handle, name) => [{ id: `cat_${handle}`, name, handle }]
const variant = (id, sku, amount, inventory, metadata = null) => ({
  id, sku, title: 'Default', inventory_quantity: inventory, options: [], metadata,
  calculated_price: { calculated_amount: amount, currency_code: 'zar' },
})
const piece = ({ uuid, id, title, image, extraImages = [], categories = [], variants }) => ({
  id, handle: `firstout-${uuid}`, title, description: `${title}, local browser fixture.`, status: 'published',
  thumbnail: image ?? null, images: [image, ...extraImages].filter(Boolean).map((url, index) => ({ id: `img_${id}_${index}`, url })),
  categories, collection: { id: 'col_on_sale', title: 'On Sale', handle: 'on-sale' }, variants,
})

// Titles sort after "Test chair" so the analytics spec still opens it first on /shop.
function products() {
  const now = Date.now()
  const madeToOrder = {
    storefront_made_to_order_offer: {
      id: 'mto_fixture', capacity: 4, remaining_capacity: 3, min_lead_time_days: 42, max_lead_time_days: 56,
      expires_at: new Date(now + 30 * 86_400_000).toISOString(), observed_at: new Date(now).toISOString(),
    },
  }
  return [
    piece({ uuid: '11111111-1111-4111-8111-111111111111', id: 'prod_test_chair', title: 'Test chair', image: '/demo/arc-front.jpg', extraImages: ['/demo/arc-angle.jpg'], categories: category('sofas-armchairs', 'Sofas & Armchairs'), variants: [variant('var_test_chair', 'TEST-CHAIR', 2400, 1)] }),
    piece({ uuid: '22222222-2222-4222-8222-222222222222', id: 'prod_tilda_sofa', title: 'Tilda Sofa', image: '/hero-sofas.jpg', categories: category('sofas-armchairs', 'Sofas & Armchairs'), variants: [variant('var_tilda_sofa', 'TILDA-SOFA', 18999, 2)] }),
    piece({ uuid: '33333333-3333-4333-8333-333333333333', id: 'prod_umbra_table', title: 'Umbra Dining Table', image: '/demo/arc-angle.jpg', categories: category('dining-room', 'Dining Room'), variants: [variant('var_umbra_table', 'UMBRA-TABLE', 34773.92, 1)] }),
    piece({ uuid: '44444444-4444-4444-8444-444444444444', id: 'prod_vale_bedside', title: 'Vale Bedside Table', categories: category('bedroom', 'Bedroom'), variants: [variant('var_vale_bedside', 'VALE-BEDSIDE', 6877.39, 1)] }),
    piece({ uuid: '55555555-5555-4555-8555-555555555555', id: 'prod_wren_coffee', title: 'Wren Coffee Table', image: '/demo/arc-detail.jpg', categories: category('coffee-console-tables', 'Coffee & Console Tables'), variants: [variant('var_wren_coffee', 'WREN-COFFEE', 7817.39, 0, madeToOrder)] }),
    piece({ uuid: '66666666-6666-4666-8666-666666666666', id: 'prod_yara_lamp', title: 'Yara Floor Lamp', image: '/demo/arc-front.jpg', variants: [variant('var_yara_lamp', 'YARA-LAMP', 1999, 3)] }),
  ]
}

createServer((request, response) => {
  const url = new URL(request.url || '/', `http://127.0.0.1:${port}`)
  response.setHeader('content-type', 'application/json')
  if (url.pathname === '/store/regions') {
    response.end(JSON.stringify({ regions: [{ id: 'reg_test', currency_code: 'zar' }] }))
    return
  }
  if (url.pathname === '/store/products') {
    const handles = url.searchParams.getAll('handle')
    const matching = products().filter((product) => !handles.length || handles.includes(product.handle))
    response.end(JSON.stringify({ products: matching, count: matching.length }))
    return
  }
  response.statusCode = 404
  response.end(JSON.stringify({ message: 'not found' }))
}).listen(port, '127.0.0.1', () => console.log(`analytics Medusa fixture on 127.0.0.1:${port}`))
