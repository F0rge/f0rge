const required = [
  "FIRSTOUT_OPS_URL",
  "FIRSTOUT_OPS_TOKEN",
  "FIRSTOUT_OPS_COMPANY_ID",
  "MEDUSA_BACKEND_URL",
  "NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY",
  "STOREFRONT_TEST_SKU_ID",
]

for (const name of required) {
  if (!process.env[name]) throw new Error(`Set ${name} before running integration`)
}

const sourceBase = process.env.FIRSTOUT_OPS_URL.replace(/\/$/, "")
const commerceBase = process.env.MEDUSA_BACKEND_URL.replace(/\/$/, "")
const companyId = process.env.FIRSTOUT_OPS_COMPANY_ID
const skuId = process.env.STOREFRONT_TEST_SKU_ID

const headers = {
  Authorization: `Bearer ${process.env.FIRSTOUT_OPS_TOKEN}`,
  "X-Ops-Company-ID": companyId,
}
const sourceResponse = await fetch(`${sourceBase}/products`, { headers })
if (!sourceResponse.ok) throw new Error(`Ops API returned ${sourceResponse.status}`)
const source = await sourceResponse.json()
if (source.company_id !== companyId) throw new Error("Ops API company mismatch")
const snapshot = source.products.find((item) => item.source_sku_id === skuId)
if (!snapshot) throw new Error(`SKU ${skuId} is not published in the Ops API`)
const allowedFields = [
  "source_sku_id", "sku", "name", "price_minor_zar", "available_quantity", "revision", "observed_at",
]
if (Object.keys(snapshot).sort().join() !== allowedFields.sort().join()) {
  throw new Error("Ops API exposed an unexpected field")
}

const denied = await fetch(`${sourceBase}/products`, {
  headers: { ...headers, Authorization: "Bearer invalid-integration-token" },
})
if (denied.status !== 401) throw new Error(`Invalid machine token returned ${denied.status}`)

const storeHeaders = { "x-publishable-api-key": process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY }
const regionsResponse = await fetch(`${commerceBase}/store/regions`, { headers: storeHeaders })
if (!regionsResponse.ok) throw new Error(`Medusa regions returned ${regionsResponse.status}`)
const { regions } = await regionsResponse.json()
const region = regions.find((item) => item.currency_code === "zar")
if (!region) throw new Error("Medusa has no ZAR region")
const query = new URLSearchParams({
  handle: `firstout-${skuId}`,
  region_id: region.id,
  fields: "id,handle,title,*variants,+variants.inventory_quantity,*variants.calculated_price",
})
const productResponse = await fetch(`${commerceBase}/store/products?${query}`, { headers: storeHeaders })
if (!productResponse.ok) throw new Error(`Medusa product returned ${productResponse.status}`)
const { products } = await productResponse.json()
const product = products[0]
if (!product || product.handle !== `firstout-${skuId}`) throw new Error("Stable source identity was lost")
const variant = product.variants?.[0]
if (!variant || variant.inventory_quantity !== snapshot.available_quantity) {
  throw new Error("Medusa availability differs from Firstout")
}
if (Math.round(variant.calculated_price?.calculated_amount * 100) !== snapshot.price_minor_zar) {
  throw new Error("Medusa ZAR price differs from Firstout")
}

console.log(`Ops → Medusa parity OK for ${snapshot.sku}: ZAR ${snapshot.price_minor_zar / 100}, ${snapshot.available_quantity} available`)
