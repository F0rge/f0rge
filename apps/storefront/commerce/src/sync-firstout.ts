import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, MedusaError, Modules, ProductStatus } from "@medusajs/framework/utils";
import {
  createInventoryLevelsWorkflow,
  createProductsWorkflow,
  updateInventoryLevelsWorkflow,
  updateProductVariantsWorkflow,
  updateProductsWorkflow,
} from "@medusajs/medusa/core-flows";

import { medusaPrice, parseOpsProducts, shouldApplyRevision, type OpsProduct } from "./ops-contract";

type CommerceProduct = {
  id: string;
  external_id: string | null;
  status: string;
  metadata: Record<string, unknown> | null;
  variants?: { id: string; sku: string | null }[];
};

type VariantInventory = {
  id: string;
  inventory_items?: { inventory_item_id: string }[];
};

const SOURCE_PREFIX = "firstout-";

async function fetchOpsProducts(): Promise<OpsProduct[]> {
  const url = process.env.FIRSTOUT_OPS_URL;
  const token = process.env.FIRSTOUT_OPS_TOKEN;
  const companyId = process.env.FIRSTOUT_OPS_COMPANY_ID;
  if (!url || !token || !companyId) {
    throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Firstout Ops Commerce connection is not configured");
  }
  const response = await fetch(`${url.replace(/\/$/, "")}/products`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Ops-Company-ID": companyId,
    },
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Firstout Ops Commerce returned ${response.status}`);
  return parseOpsProducts(await response.json(), companyId).products;
}

async function writeStock(
  container: MedusaContainer,
  variantId: string,
  locationId: string,
  quantity: number,
) {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data: variants } = await query.graph({
    entity: "product_variant",
    fields: ["id", "inventory_items.inventory_item_id"],
    filters: { id: variantId },
  });
  const variant = variants[0] as VariantInventory | undefined;
  const itemId = variant?.inventory_items?.[0]?.inventory_item_id;
  if (!itemId) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Medusa variant ${variantId} has no inventory item`);
  const { data: levels } = await query.graph({
    entity: "inventory_level",
    fields: ["id", "inventory_item_id", "location_id", "stocked_quantity"],
    filters: { inventory_item_id: itemId, location_id: locationId },
  });
  if (levels.length) {
    await updateInventoryLevelsWorkflow(container).run({
      input: { updates: [{
        id: levels[0].id,
        inventory_item_id: itemId,
        location_id: locationId,
        stocked_quantity: quantity,
      }] },
    });
  } else {
    await createInventoryLevelsWorkflow(container).run({
      input: { inventory_levels: [{
        inventory_item_id: itemId,
        location_id: locationId,
        stocked_quantity: quantity,
      }] },
    });
  }
}

export async function syncFirstout(container: MedusaContainer): Promise<void> {
  const locking = container.resolve(Modules.LOCKING);
  await locking.execute("storefront:firstout:catalogue-sync", async () => {
    await syncFirstoutLocked(container);
  });
}

async function syncFirstoutLocked(container: MedusaContainer): Promise<void> {
  const source = await fetchOpsProducts();
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const logger = container.resolve(ContainerRegistrationKeys.LOGGER);
  const { data: existingData } = await query.graph({
    entity: "product",
    fields: ["id", "external_id", "status", "metadata", "variants.id", "variants.sku"],
  });
  const existing = (existingData as CommerceProduct[]).filter((product) =>
    product.external_id?.startsWith(SOURCE_PREFIX),
  );
  const bySourceId = new Map(existing.map((product) => [product.external_id, product]));
  const { data: channels } = await query.graph({
    entity: "sales_channel", fields: ["id"],
  });
  const { data: locations } = await query.graph({
    entity: "stock_location", fields: ["id"],
  });
  const { data: profiles } = await query.graph({
    entity: "shipping_profile", fields: ["id"],
  });
  if (!channels[0] || !locations[0] || !profiles[0]) {
    throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Run the Medusa Storefront bootstrap before syncing");
  }

  for (const snapshot of source) {
    const externalId = `${SOURCE_PREFIX}${snapshot.source_sku_id}`;
    const product = bySourceId.get(externalId);
    if (product && !shouldApplyRevision(snapshot.revision, product.metadata?.source_revision)) {
      continue;
    }
    const majorPrice = medusaPrice(snapshot.price_minor_zar);
    if (!product) {
      const { result } = await createProductsWorkflow(container).run({
        input: { products: [{
          title: snapshot.name,
          handle: externalId,
          external_id: externalId,
          status: ProductStatus.PUBLISHED,
          shipping_profile_id: profiles[0].id,
          sales_channels: [{ id: channels[0].id }],
          options: [{ title: "Item", values: ["Standard"] }],
          variants: [{
            title: "Standard",
            sku: snapshot.sku,
            manage_inventory: true,
            options: { Item: "Standard" },
            prices: [{ amount: majorPrice, currency_code: "zar" }],
          }],
          metadata: { source_revision: snapshot.revision },
        }] },
      });
      const variantId = result[0]?.variants?.[0]?.id;
      if (!variantId) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Medusa did not create a variant for ${externalId}`);
      await writeStock(container, variantId, locations[0].id, snapshot.available_quantity);
      logger.info(`Projected Firstout SKU ${snapshot.sku}`);
      continue;
    }

    const variantId = product.variants?.[0]?.id;
    if (!variantId) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Medusa product ${product.id} has no variant`);
    await updateProductVariantsWorkflow(container).run({
      input: { product_variants: [{
        id: variantId,
        sku: snapshot.sku,
        prices: [{ amount: majorPrice, currency_code: "zar" }],
      }] },
    });
    await writeStock(container, variantId, locations[0].id, snapshot.available_quantity);
    await updateProductsWorkflow(container).run({
      input: { selector: { id: product.id }, update: {
        status: ProductStatus.PUBLISHED,
        metadata: { ...product.metadata, source_revision: snapshot.revision },
      } },
    });
  }

  const liveIds = new Set(source.map((sku) => `${SOURCE_PREFIX}${sku.source_sku_id}`));
  for (const product of existing) {
    if (!liveIds.has(product.external_id!) && product.status !== ProductStatus.DRAFT) {
      await updateProductsWorkflow(container).run({
        input: { selector: { id: product.id }, update: { status: ProductStatus.DRAFT } },
      });
    }
  }
}
