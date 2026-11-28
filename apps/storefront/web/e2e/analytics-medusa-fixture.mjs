import { createServer } from 'node:http'

const port = Number(process.env.STOREFRONT_ANALYTICS_MEDUSA_PORT || 9011)
const includeAvanzi = process.env.STOREFRONT_TEST_AVANZI_GUIDANCE === 'true'
const category = (handle, name) => [{ id: `cat_${handle}`, name, handle }]
// `was` puts the variant on a sale price list, as Medusa reports it.
const variant = (id, sku, amount, inventory, metadata = null, was = null) => ({
  id, sku, title: 'Default', inventory_quantity: inventory, options: [], metadata,
  calculated_price: {
    calculated_amount: amount, original_amount: was ?? amount, currency_code: 'zar',
    calculated_price: { price_list_type: was ? 'sale' : null },
  },
})
const piece = ({ uuid, id, title, image, extraImages = [], categories = [], tags = [], variants, ...details }) => ({
  ...details, id, tags: tags.map((value) => ({ id: `tag_${value}`, value })), handle: `firstout-${uuid}`, title, description: `${title}, local browser fixture.`, status: 'published',
  thumbnail: image ?? null, images: [image, ...extraImages].filter(Boolean).map((url, index) => ({ id: `img_${id}_${index}`, url })),
  categories, collection: { id: 'col_on_sale', title: 'On Sale', handle: 'on-sale' }, variants,
})

const options = [
  { id: 'opt_umbra_colour', title: 'Colour', values: ['Silver', 'Gold', 'Bronze'].map((value) => ({ id: value, value })) },
  { id: 'opt_umbra_size', title: 'Size', values: ['160 cm', '200 cm'].map((value) => ({ id: value, value })) },
]
const swatches = { Silver: '#c0c0c0', Gold: '#b8902e', Bronze: '#8c5a2b' }
function umbraVariant(id, sku, colour, size, amount, inventory, urls) {
  return {
    ...variant(id, sku, amount, inventory, { suitable_image_urls: urls, swatch_hex: swatches[colour] }),
    title: `${colour} / ${size}`,
    options: [colour, size].map((value, index) => ({ id: `${id}_${index}`, option_id: options[index].id, value })),
    images: urls.map((url) => ({ id: url, url })).reverse(),
  }
}

// Titles sort after "Test chair" so the analytics spec still opens it first on /shop.
function products() {
  const now = Date.now()
  const madeToOrder = {
    storefront_made_to_order_offer: {
      id: 'mto_fixture', capacity: 4, remaining_capacity: 3, min_lead_time_days: 42, max_lead_time_days: 56,
      expires_at: new Date(now + 30 * 86_400_000).toISOString(), observed_at: new Date(now).toISOString(),
    },
  }
  const catalogue = [
    piece({ uuid: '11111111-1111-4111-8111-111111111111', id: 'prod_test_chair', title: 'Test chair', image: '/demo/arc-front.jpg', extraImages: ['/demo/arc-angle.jpg'], tags: ['just-arrived'], categories: category('sofas-armchairs', 'Sofas & Armchairs'), variants: [variant('variant_test_chair', 'TEST-CHAIR', 2400, 1)] }),
    piece({ uuid: '22222222-2222-4222-8222-222222222222', id: 'prod_tilda_sofa', title: 'Tilda Sofa', image: '/hero-sofas.jpg', material: 'Bouclé', length: 220, width: 95, height: 80, metadata: { dimension_unit: 'cm' }, categories: category('sofas-armchairs', 'Sofas & Armchairs'), variants: [variant('variant_tilda_sofa', 'TILDA-SOFA', 18999, 2, { piece_count: 2 }, 22999)] }),
    piece({ uuid: 'group-33333333-3333-4333-8333-333333333333', id: 'prod_umbra_table', title: 'Umbra Dining Table', image: '/demo/arc-angle.jpg', categories: category('dining-room', 'Dining Room'), options, variants: [
      umbraVariant('variant_umbra_table', 'UMBRA-TABLE', 'Silver', '200 cm', 37773.92, 1, [
        '/demo/arc-angle.jpg',
        '/demo/arc-front.jpg',
        '/hero-sofas.jpg',
        '/merchandising/category-dining-room.webp',
        '/demo/arc-detail.jpg',
        '/merchandising/category-coffee-console-tables.webp',
      ]),
      umbraVariant('variant_umbra_gold_large', 'UMBRA-GOLD-200', 'Gold', '200 cm', 36500, 0, ['/hero-sofas.jpg']),
      umbraVariant('variant_umbra_gold_small', 'UMBRA-GOLD-160', 'Gold', '160 cm', 37000, 2, ['/demo/arc-front.jpg']),
    ] }),
    piece({ uuid: '44444444-4444-4444-8444-444444444444', id: 'prod_vale_bedside', title: 'Vale Bedside Table', categories: [...category('custom-label', 'Custom label'), ...category('bedroom', 'Bedroom')], variants: [variant('variant_vale_bedside', 'VALE-BEDSIDE', 6877.39, 1)] }),
    piece({ uuid: '55555555-5555-4555-8555-555555555555', id: 'prod_wren_coffee', title: 'Wren Coffee Table', image: '/demo/arc-detail.jpg', categories: category('coffee-console-tables', 'Coffee & Console Tables'), variants: [variant('variant_wren_coffee', 'WREN-COFFEE', 7817.39, 0, madeToOrder)] }),
    piece({ uuid: '66666666-6666-4666-8666-666666666666', id: 'prod_yara_lamp', title: 'Yara Floor Lamp', image: '/demo/arc-front.jpg', variants: [variant('variant_yara_lamp', 'YARA-LAMP', 1999, 3)] }),
  ]
  if (includeAvanzi) {
    catalogue.push(piece({ uuid: '7d36b7b6-9871-44c5-b330-b808221f8005', id: 'prod_avanzi', title: 'Avanzi L-Shaped Sofa', image: '/hero-sofas.jpg', categories: category('sofas-armchairs', 'Sofas & Armchairs'), variants: [variant('variant_avanzi', 'FIXTURE-AVANZI', 12000, 1)] }))
  }
  return catalogue
}
// Sold in pairs with five in stock, so the most a shopper can take is four.
// Unlisted: served only by handle or id, so the listing and analytics counts stay as they are.
const pairSold = () => piece({ uuid: '77777777-7777-4777-8777-777777777777', id: 'prod_pella_chair', title: 'Pella Dining Chair', image: '/demo/arc-front.jpg', categories: category('dining-room', 'Dining Room'), variants: [variant('variant_pella_chair', 'PELLA-CHAIR', 2450, 5, { sell_multiple: 2, min_quantity: 2 })] })
// Sold in pairs with a single unit left: no valid quantity can be offered.
const lastOddUnit = () => piece({ uuid: '88888888-8888-4888-8888-888888888888', id: 'prod_pella_stool', title: 'Pella Counter Stool', categories: category('dining-room', 'Dining Room'), variants: [variant('variant_pella_stool', 'PELLA-STOOL', 1850, 1, { sell_multiple: 2, min_quantity: 2 })] })
// Sold in pairs, minimum four, nine in stock: four, six or eight.
const pairsFromFour = () => piece({ uuid: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', id: 'prod_pella_side', title: 'Pella Side Chair', categories: category('dining-room', 'Dining Room'), variants: [variant('variant_pella_side', 'PELLA-SIDE', 1990, 9, { sell_multiple: 2, min_quantity: 4 })] })
const allProducts = () => [...products(), pairSold(), lastOddUnit(), pairsFromFour()]

// In-memory carts so the bag route works against the fixture.
// ponytail: no stock check here; the web caps quantity and real Medusa enforces inventory.
const carts = new Map()
function addLine(cart, { variant_id, quantity }) {
  const product = allProducts().find((candidate) => candidate.variants.some((item) => item.id === variant_id))
  const unit = product?.variants.find((item) => item.id === variant_id)
  if (!unit) return false
  const line = cart.items.find((item) => item.variant_id === variant_id)
  if (line) line.quantity += quantity
  else cart.items.push({ id: `cali_${variant_id}`, variant_id, product_id: product.id, title: product.title, thumbnail: product.thumbnail, quantity, unit_price: unit.calculated_price.calculated_amount })
  totals(cart)
  return true
}
function totals(cart) {
  for (const item of cart.items) item.total = item.unit_price * item.quantity
  cart.subtotal = cart.total = cart.items.reduce((sum, item) => sum + item.total, 0)
}
const readJson = async (request) => {
  let body = ''
  for await (const chunk of request) body += chunk
  return body ? JSON.parse(body) : {}
}

createServer(async (request, response) => {
  const url = new URL(request.url || '/', `http://127.0.0.1:${port}`)
  response.setHeader('content-type', 'application/json')
  if (url.pathname === '/store/carts' && request.method === 'POST') {
    const cart = { id: `cart_fixture_${carts.size + 1}`, items: [], subtotal: 0, total: 0, currency_code: 'zar' }
    carts.set(cart.id, cart)
    response.end(JSON.stringify({ cart }))
    return
  }
  const cartPath = /^\/store\/carts\/([^/]+)(?:\/(line-items|checkout-hold|storefront-checkout)(?:\/([^/]+))?)?$/.exec(url.pathname)
  const cart = cartPath && carts.get(cartPath[1])
  const [, , action, itemId] = cartPath || []
  if (cart && !action && request.method === 'GET') {
    response.end(JSON.stringify({ cart }))
    return
  }
  if (cart && action === 'line-items' && !itemId && request.method === 'POST') {
    if (addLine(cart, await readJson(request))) {
      response.end(JSON.stringify({ cart }))
      return
    }
  }
  const line = cart && itemId && cart.items.find((item) => item.id === itemId)
  if (line && request.method === 'POST') {
    line.quantity = (await readJson(request)).quantity
    totals(cart)
    response.end(JSON.stringify({ cart }))
    return
  }
  if (line && request.method === 'DELETE') {
    cart.items = cart.items.filter((item) => item !== line)
    totals(cart)
    response.end(JSON.stringify({ parent: cart }))
    return
  }
  // A hold is just a flag here; real Medusa reserves stock for 20 minutes.
  if (cart && action === 'checkout-hold') {
    const hold = request.method === 'POST'
      ? { status: 'active', expires_at: new Date(Date.now() + 20 * 60_000).toISOString() }
      : { status: 'cancelled' }
    cart.metadata = { storefront_hold: hold }
    response.end(JSON.stringify({ hold }))
    return
  }
  // No card provider is configured in the fixture: commerce answers before it creates any order.
  if (cart && action === 'storefront-checkout') {
    response.statusCode = 404
    response.end(JSON.stringify({ code: 'payment_unavailable', message: 'Checkout is not available here' }))
    return
  }
  if (url.pathname === '/store/regions') {
    response.end(JSON.stringify({ regions: [{ id: 'reg_test', currency_code: 'zar' }] }))
    return
  }
  if (url.pathname === '/store/products') {
    const handles = url.searchParams.getAll('handle')
    const ids = url.searchParams.getAll('id')
    const matching = (handles.length || ids.length ? allProducts() : products()).filter((product) => (!handles.length || handles.includes(product.handle)) && (!ids.length || ids.includes(product.id)))
    response.end(JSON.stringify({ products: matching, count: matching.length }))
    return
  }
  response.statusCode = 404
  response.end(JSON.stringify({ message: 'not found' }))
}).listen(port, '127.0.0.1', () => console.log(`analytics Medusa fixture on 127.0.0.1:${port}`))
