import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, MedusaError, Modules, ProductStatus } from "@medusajs/framework/utils";
import {
  createInventoryLevelsWorkflow, createProductsWorkflow, createProductVariantsWorkflow,
  deleteProductVariantsWorkflow, updateInventoryLevelsWorkflow, updateProductVariantsWorkflow,
  updateProductsWorkflow,
} from "@medusajs/medusa/core-flows";

import { medusaPrice, parseOpsProducts, shouldApplyRevision, type OpsProduct } from "./ops-contract";

type CommerceVariant = {
  id: string; sku: string | null; metadata: Record<string, unknown> | null;
  options?: { value: string; option?: { title: string } }[];
};
type CommerceProduct = {
  id: string; external_id: string | null; status: string; metadata: Record<string, unknown> | null;
  options?: { title: string }[]; variants?: CommerceVariant[];
};
type VariantInventory = { inventory_items?: { inventory_item_id: string }[] };
type SourceGroup = { externalId: string; title: string; rows: OpsProduct[]; grouped: boolean };
const SOURCE_PREFIX = "firstout-";

export function groupOpsProducts(source: OpsProduct[]): SourceGroup[] {
  const groups = new Map<string, SourceGroup>();
  for (const row of source) {
    const grouped = row.product_group_id !== null;
    const externalId = grouped ? `${SOURCE_PREFIX}group-${row.product_group_id}` : `${SOURCE_PREFIX}${row.source_sku_id}`;
    const group = groups.get(externalId);
    if (group) group.rows.push(row);
    else groups.set(externalId, { externalId, title: row.product_title || row.name, rows: [row], grouped });
  }
  return [...groups.values()];
}

function variantTitle(row: OpsProduct): string {
  return Object.values(row.options).join(" / ") || "Standard";
}
function variantOptions(row: OpsProduct): Record<string, string> {
  return row.product_group_id ? row.options : { Item: "Standard" };
}
function productOptions(group: SourceGroup): { title: string; values: string[] }[] {
  if (!group.grouped) return [{ title: "Item", values: ["Standard"] }];
  return Object.keys(group.rows[0].options).sort().map((title) => ({
    title, values: [...new Set(group.rows.map((row) => row.options[title]))].sort(),
  }));
}

async function fetchOpsProducts(): Promise<OpsProduct[]> {
  const url = process.env.FIRSTOUT_OPS_URL;
  const token = process.env.FIRSTOUT_OPS_TOKEN;
  const companyId = process.env.FIRSTOUT_OPS_COMPANY_ID;
  if (!url || !token || !companyId) {
    throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Firstout Ops Commerce connection is not configured");
  }
  const response = await fetch(`${url.replace(/\/$/, "")}/products`, {
    headers: { Authorization: `Bearer ${token}`, "X-Ops-Company-ID": companyId },
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Firstout Ops Commerce returned ${response.status}`);
  return parseOpsProducts(await response.json(), companyId).products;
}

async function writeStock(container: MedusaContainer, variantId: string, locationId: string, quantity: number) {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data: variants } = await query.graph({
    entity: "product_variant", fields: ["id", "inventory_items.inventory_item_id"], filters: { id: variantId },
  });
  const itemId = (variants[0] as VariantInventory | undefined)?.inventory_items?.[0]?.inventory_item_id;
  if (!itemId) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Medusa variant ${variantId} has no inventory item`);
  const { data: levels } = await query.graph({
    entity: "inventory_level", fields: ["id", "inventory_item_id", "location_id", "stocked_quantity"],
    filters: { inventory_item_id: itemId, location_id: locationId },
  });
  if (levels.length) {
    await updateInventoryLevelsWorkflow(container).run({ input: { updates: [{
      id: levels[0].id, inventory_item_id: itemId, location_id: locationId, stocked_quantity: quantity,
    }] } });
  } else {
    await createInventoryLevelsWorkflow(container).run({ input: { inventory_levels: [{
      inventory_item_id: itemId, location_id: locationId, stocked_quantity: quantity,
    }] } });
  }
}

export async function syncFirstout(container: MedusaContainer): Promise<void> {
  const locking = container.resolve(Modules.LOCKING);
  await locking.execute("storefront:firstout:catalogue-sync", async () => syncFirstoutLocked(container));
}

async function syncFirstoutLocked(container: MedusaContainer): Promise<void> {
  const groups = groupOpsProducts(await fetchOpsProducts());
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const logger = container.resolve(ContainerRegistrationKeys.LOGGER);
  const { data: existingData } = await query.graph({
    entity: "product",
    fields: ["id", "external_id", "status", "metadata", "options.title", "variants.id", "variants.sku", "variants.metadata", "variants.options.value", "variants.options.option.title"],
  });
  const existing = (existingData as CommerceProduct[]).filter((product) => product.external_id?.startsWith(SOURCE_PREFIX));
  const bySourceId = new Map<string, CommerceProduct>();
  for (const product of existing) {
    if (bySourceId.has(product.external_id!)) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, `Duplicate Medusa product mapping ${product.external_id}`);
    }
    bySourceId.set(product.external_id!, product);
  }
  const { data: channels } = await query.graph({ entity: "sales_channel", fields: ["id"] });
  const { data: locations } = await query.graph({ entity: "stock_location", fields: ["id"] });
  const { data: profiles } = await query.graph({ entity: "shipping_profile", fields: ["id"] });
  if (!channels[0] || !locations[0] || !profiles[0]) {
    throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Run the Medusa Storefront bootstrap before syncing");
  }

  // A SKU may move from its legacy one-SKU product into a group. Release the
  // old variant's unique SKU before creating the grouped variant.
  const desiredOwner = new Map(groups.flatMap((group) =>
    group.rows.map((row) => [row.source_sku_id, group.externalId] as const),
  ));
  for (const product of existing) {
    const oldSourceId = product.external_id?.startsWith(`${SOURCE_PREFIX}group-`)
      ? null : product.external_id?.slice(SOURCE_PREFIX.length);
    const moved = (product.variants || []).filter((variant) => {
      const sourceId = variant.metadata?.source_sku_id || oldSourceId;
      return typeof sourceId === "string" && desiredOwner.has(sourceId) &&
        desiredOwner.get(sourceId) !== product.external_id;
    });
    if (!moved.length) continue;
    if (product.status === ProductStatus.PUBLISHED) {
      await updateProductsWorkflow(container).run({ input: {
        selector: { id: product.id }, update: { status: ProductStatus.DRAFT },
      } });
      product.status = ProductStatus.DRAFT;
    }
    await deleteProductVariantsWorkflow(container).run({ input: { ids: moved.map((variant) => variant.id) } });
    product.variants = (product.variants || []).filter((variant) => !moved.includes(variant));
  }

  for (const group of groups) {
    const product = bySourceId.get(group.externalId);
    const options = productOptions(group);
    if (!product) {
      const { result } = await createProductsWorkflow(container).run({ input: { products: [{
        title: group.title, handle: group.externalId, external_id: group.externalId,
        status: ProductStatus.DRAFT, shipping_profile_id: profiles[0].id,
        sales_channels: [{ id: channels[0].id }], options,
        variants: group.rows.map((row) => ({
          title: variantTitle(row), sku: row.sku, manage_inventory: true,
          options: variantOptions(row), prices: [{ amount: medusaPrice(row.price_minor_zar), currency_code: "zar" }],
          metadata: { source_sku_id: row.source_sku_id, source_revision: row.revision, source_available_quantity: row.available_quantity, source_price_includes_tax: true },
        })),
        metadata: group.grouped ? { source_product_group_id: group.rows[0].product_group_id } : {},
      }] } });
      const createdVariants = result[0]?.variants || [];
      for (const row of group.rows) {
        const variant = createdVariants.find((item) => item.sku === row.sku);
        if (!variant) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Medusa did not create variant ${row.sku}`);
        await writeStock(container, variant.id, locations[0].id, row.available_quantity);
      }
      logger.info(`Projected Firstout product ${group.externalId}`);
      continue;
    }

    const currentKeys = (product.options || []).map((option) => option.title).sort();
    const nextKeys = options.map((option) => option.title).sort();
    if (JSON.stringify(currentKeys) !== JSON.stringify(nextKeys)) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, `Option names changed for ${group.externalId}; manual migration required`);
    }
    const bySkuId = new Map<string, CommerceVariant>();
    for (const variant of product.variants || []) {
      const sourceId = variant.metadata?.source_sku_id;
      const legacyId = !group.grouped && group.externalId.slice(SOURCE_PREFIX.length);
      const mappedId = typeof sourceId === "string" ? sourceId : legacyId;
      if (!mappedId || bySkuId.has(mappedId)) {
        throw new MedusaError(MedusaError.Types.INVALID_DATA, `Ambiguous Medusa variant mapping for ${group.externalId}`);
      }
      bySkuId.set(mappedId, variant);
    }
    const incomingIds = new Set(group.rows.map((row) => row.source_sku_id));
    const removed = [...bySkuId].filter(([id]) => !incomingIds.has(id)).map(([, variant]) => variant.id);
    const added = group.rows.filter((row) => !bySkuId.has(row.source_sku_id));
    if ((removed.length || added.length) && product.status === ProductStatus.PUBLISHED) {
      await updateProductsWorkflow(container).run({ input: {
        selector: { id: product.id }, update: { status: ProductStatus.DRAFT },
      } });
    }
    if (removed.length) await deleteProductVariantsWorkflow(container).run({ input: { ids: removed } });
    if (added.length) {
      const { result } = await createProductVariantsWorkflow(container).run({ input: { product_variants: added.map((row) => ({
        product_id: product.id, title: variantTitle(row), sku: row.sku, manage_inventory: true,
        options: variantOptions(row), prices: [{ amount: medusaPrice(row.price_minor_zar), currency_code: "zar" }],
        metadata: { source_sku_id: row.source_sku_id, source_revision: row.revision, source_available_quantity: row.available_quantity, source_price_includes_tax: true },
      })) } });
      for (const row of added) {
        const variant = result.find((item) => item.sku === row.sku);
        if (!variant) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Medusa did not create variant ${row.sku}`);
        await writeStock(container, variant.id, locations[0].id, row.available_quantity);
      }
    }
    for (const row of group.rows) {
      const variant = bySkuId.get(row.source_sku_id);
      if (!variant) continue;
      const currentOptions = Object.fromEntries((variant.options || []).map((item) => [item.option?.title, item.value]));
      const nextOptions = variantOptions(row);
      const optionsChanged = JSON.stringify(Object.entries(currentOptions).sort()) !== JSON.stringify(Object.entries(nextOptions).sort());
      if (!optionsChanged && !shouldApplyRevision(row.revision, variant.metadata?.source_revision)) continue;
      await updateProductVariantsWorkflow(container).run({ input: { product_variants: [{
        id: variant.id, sku: row.sku, ...(optionsChanged ? { options: nextOptions, title: variantTitle(row) } : {}),
        prices: [{ amount: medusaPrice(row.price_minor_zar), currency_code: "zar" }],
        metadata: { ...variant.metadata, source_sku_id: row.source_sku_id, source_revision: row.revision, source_available_quantity: row.available_quantity, source_price_includes_tax: true },
      }] } });
      await writeStock(container, variant.id, locations[0].id, row.available_quantity);
    }
  }

  const liveIds = new Set(groups.map((group) => group.externalId));
  for (const product of existing) {
    if (!liveIds.has(product.external_id!) && product.status !== ProductStatus.DRAFT) {
      await updateProductsWorkflow(container).run({ input: {
        selector: { id: product.id }, update: { status: ProductStatus.DRAFT },
      } });
    }
  }
}
