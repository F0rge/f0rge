import type { IInventoryService, MedusaContainer, ReservationItemDTO } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, MedusaError, Modules, ProductStatus } from "@medusajs/framework/utils";
import { reconcileStorefrontHandoffs } from "./storefront-order-handoff";
import { recordOpsCheckoutHealth, refreshOpsCheckoutHealth } from "./storefront-commerce-exceptions";
import { CAPACITY_STATE_METADATA_KEY, mergeCapacityState, offerPresentation } from "./made-to-order-capacity";
import {
  createCollectionsWorkflow, createInventoryLevelsWorkflow, createProductsWorkflow, createProductVariantsWorkflow,
  deleteProductVariantsWorkflow, updateInventoryLevelsWorkflow, updateProductVariantsWorkflow,
  updateProductsWorkflow,
} from "@medusajs/medusa/core-flows";

import { medusaPrice, parseOpsProducts, pendingCommitments, projectAvailableQuantity, shouldApplyRevision, type OpsProduct } from "./ops-contract";

type CommerceVariant = {
  id: string; sku: string | null; allow_backorder?: boolean; metadata: Record<string, unknown> | null;
  options?: { value: string; option?: { title: string } }[];
};
type CommerceProduct = {
  id: string; external_id: string | null; status: string; metadata: Record<string, unknown> | null;
  options?: { title: string }[]; variants?: CommerceVariant[];
};
type VariantInventory = { inventory_items?: { inventory_item_id: string }[] };
type SourceGroup = { externalId: string; title: string; rows: OpsProduct[]; grouped: boolean };
const SOURCE_PREFIX = "firstout-";
export const CATALOGUE_COLLECTION_HANDLE = "in-stock";
export const CATALOGUE_COLLECTION_TITLE = "In stock";

function syncedCapacityMetadata(row: OpsProduct, metadata: Record<string, unknown> | null) {
  const state = mergeCapacityState(metadata, row.made_to_order_offer, row.revision);
  const presentation = offerPresentation(state, Date.now());
  return {
    [CAPACITY_STATE_METADATA_KEY]: state,
    storefront_made_to_order_offer: presentation ? { ...presentation, observed_at: row.observed_at } : null,
  };
}

// Medusa must be able to complete a zero-on-hand order after our finite
// capacity hold has passed. All public cart writes remain behind the BFF and
// payment still validates the exact hold under the shared inventory lock.
export function allowsFiniteBackorder(row: OpsProduct): boolean {
  return !!row.made_to_order_offer && Date.parse(row.made_to_order_offer.expires_at) > Date.now();
}

export function isCatalogueRow(row: OpsProduct): boolean {
  return row.available_quantity > 0 || allowsFiniteBackorder(row);
}

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

export function catalogueExternalIds(source: OpsProduct[]): string[] {
  return groupOpsProducts(source)
    .filter((group) => group.rows.length > 0 && group.rows.every(isCatalogueRow))
    .map((group) => group.externalId);
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

type PaidReservationOrder = {
  metadata?: Record<string, unknown> | null;
  items?: { id: string }[];
  payment_collections?: { payments?: { captured_at?: string | Date | null }[] }[];
};

async function paidOrderReservedQuantity(container: MedusaContainer, inventoryItemId: string, locationId: string): Promise<number> {
  const inventory = container.resolve<IInventoryService>(Modules.INVENTORY);
  const reservations: ReservationItemDTO[] = [];
  const pageSize = 500;
  for (let skip = 0; ; skip += pageSize) {
    const page = await inventory.listReservationItems({ inventory_item_id: inventoryItemId, location_id: locationId }, { skip, take: pageSize });
    reservations.push(...page);
    if (page.length < pageSize) break;
  }
  const orderReservations = reservations.filter((row) => row.line_item_id && !row.created_by?.startsWith("storefront_hold:"));
  if (!orderReservations.length) return 0;
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const relevantOrderIds = new Set<string>();
  for (let skip = 0; ; skip += pageSize) {
    const { data: orderItems } = await query.graph({
      entity: "order_item", fields: ["item_id", "order_id"],
      filters: { item_id: orderReservations.map((row) => row.line_item_id!) },
      pagination: { skip, take: pageSize },
    });
    for (const item of orderItems) {
      // Medusa returns the selected native FK although its generated OrderItem
      // type omits it. Validate the wire field rather than guessing ownership.
      const orderId: unknown = Reflect.get(item, "order_id");
      if (typeof orderId !== "string" || !orderId) {
        throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Native reservation order mapping is missing");
      }
      relevantOrderIds.add(orderId);
    }
    if (orderItems.length < pageSize) break;
  }
  const orderIds = [...relevantOrderIds];
  if (!orderIds.length) return 0;
  const { data: orders } = await query.graph({
    entity: "order", fields: ["id", "metadata", "items.id", "payment_collections.payments.captured_at"],
    filters: { id: orderIds }, pagination: { take: orderIds.length },
  });
  const paidLines = new Set((orders as PaidReservationOrder[])
    .filter((order) => order.metadata?.storefront_confirmation_sha256 &&
      order.payment_collections?.some((collection) => collection.payments?.some((payment) => payment.captured_at)))
    .flatMap((order) => (order.items || []).map((item) => item.id)));
  return orderReservations.filter((row) => paidLines.has(row.line_item_id!))
    .reduce((quantity, row) => quantity + Number(row.quantity), 0);
}

export async function writeStock(container: MedusaContainer, variantId: string, locationId: string, quantity: number) {
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
  // Ops availability (less unacknowledged paid commitments) already excludes
  // these sold units. Native reservations must remain for fulfillment, so add
  // them to stocked quantity and let Medusa subtract them exactly once. Active
  // cart holds and reservations outside captured Storefront orders still reduce
  // sellable stock normally.
  const stockedQuantity = quantity + await paidOrderReservedQuantity(container, itemId, locationId);
  if (levels.length) {
    await updateInventoryLevelsWorkflow(container).run({ input: { updates: [{
      id: levels[0].id, inventory_item_id: itemId, location_id: locationId, stocked_quantity: stockedQuantity,
    }] } });
  } else {
    await createInventoryLevelsWorkflow(container).run({ input: { inventory_levels: [{
      inventory_item_id: itemId, location_id: locationId, stocked_quantity: stockedQuantity,
    }] } });
  }
}

type CatalogueProduct = {
  id: string; external_id: string | null; status: string; collection_id?: string | null;
};

// The publication hook rejects a product with no tax-inclusive ZAR price. That
// string is the only signal we continue past: the product stays a draft, and
// the priced products in the same run still publish. No price is invented.
export function missingTaxInclusiveZarPrice(error: unknown): boolean {
  const parts: string[] = [];
  const seen = new Set<unknown>();
  let current = error;
  for (let depth = 0; current && depth < 5; depth += 1) {
    if (seen.has(current)) break;
    seen.add(current);
    if (current instanceof Error) {
      parts.push(current.message);
      current = Reflect.get(current, "cause");
      continue;
    }
    if (typeof current === "object" && current && "message" in current) {
      parts.push(String((current as { message: unknown }).message));
    }
    break;
  }
  return parts.join("\n").includes("tax-inclusive ZAR price is missing");
}

async function catalogueCollectionId(container: MedusaContainer): Promise<string> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({ entity: "product_collection", fields: ["id", "handle"] });
  const existing = (data as { id?: string; handle?: string }[]).find((item) => item.handle === CATALOGUE_COLLECTION_HANDLE)?.id;
  if (existing) return existing;
  const { result } = await createCollectionsWorkflow(container).run({
    input: { collections: [{ title: CATALOGUE_COLLECTION_TITLE, handle: CATALOGUE_COLLECTION_HANDLE }] },
  });
  const created = (Array.isArray(result) ? result : []) as { id?: string }[];
  const id = created[0]?.id;
  if (!id) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Medusa did not create the In stock collection");
  return id;
}

async function setCatalogueMembership(
  container: MedusaContainer, ids: string[], update: { status: ProductStatus; collection_id: string | null },
) {
  for (let index = 0; index < ids.length; index += 20) {
    await updateProductsWorkflow(container).run({
      input: { selector: { id: ids.slice(index, index + 20) }, update },
    });
  }
}

async function publishCatalogueProducts(container: MedusaContainer, ids: string[], collectionId: string) {
  const logger = container.resolve(ContainerRegistrationKeys.LOGGER);
  for (const id of ids) {
    try {
      await updateProductsWorkflow(container).run({
        input: { selector: { id: [id] }, update: { status: ProductStatus.PUBLISHED, collection_id: collectionId } },
      });
    } catch (error) {
      if (!missingTaxInclusiveZarPrice(error)) throw error;
      logger.warn(`Left Firstout product ${id} unpublished because a tax-inclusive ZAR price is missing`);
    }
  }
}

async function publishCatalogue(container: MedusaContainer, readyIds: Set<string>) {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({
    entity: "product", fields: ["id", "external_id", "status", "collection_id"],
  });
  const products = (data as CatalogueProduct[]).filter((product) => product.external_id?.startsWith(SOURCE_PREFIX));
  const wanted = products.filter((product) => readyIds.has(product.external_id || ""));
  const collectionId = wanted.length ? await catalogueCollectionId(container) : null;
  const publish = wanted
    .filter((product) => product.status !== ProductStatus.PUBLISHED || product.collection_id !== collectionId)
    .map((product) => product.id);
  const withdraw = products
    .filter((product) => !readyIds.has(product.external_id || "") &&
      (product.status !== ProductStatus.DRAFT || !!product.collection_id))
    .map((product) => product.id);
  if (publish.length && collectionId) await publishCatalogueProducts(container, publish, collectionId);
  if (withdraw.length) {
    await setCatalogueMembership(container, withdraw, { status: ProductStatus.DRAFT, collection_id: null });
  }
}

export async function syncFirstout(container: MedusaContainer): Promise<void> {
  const locking = container.resolve(Modules.LOCKING);
  await locking.execute("storefront:inventory", async () => syncFirstoutLocked(container));
}

async function syncFirstoutLocked(container: MedusaContainer): Promise<void> {
  let sourceProducts;
  try {
    sourceProducts = await fetchOpsProducts();
    await refreshOpsCheckoutHealth();
  } catch (error) {
    recordOpsCheckoutHealth({ opsReachable: false, checkoutAllowed: false });
    throw error;
  }
  await reconcileStorefrontHandoffs(
    container,
    sourceProducts.flatMap((product) => product.acknowledged_commitment_ids),
  );
  const groups = groupOpsProducts(sourceProducts);
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const logger = container.resolve(ContainerRegistrationKeys.LOGGER);
  const { data: existingData } = await query.graph({
    entity: "product",
    fields: ["id", "external_id", "status", "metadata", "options.title", "variants.id", "variants.sku", "variants.allow_backorder", "variants.metadata", "variants.options.value", "variants.options.option.title"],
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
          title: variantTitle(row), sku: row.sku, manage_inventory: true, allow_backorder: allowsFiniteBackorder(row),
          options: variantOptions(row), prices: [{ amount: medusaPrice(row.price_minor_zar), currency_code: "zar" }],
          metadata: { source_sku_id: row.source_sku_id, source_revision: row.revision, source_observed_at: row.observed_at, source_available_quantity: row.available_quantity, source_projected_quantity: row.available_quantity, source_price_includes_tax: true, ...syncedCapacityMetadata(row, null) },
        })),
        metadata: group.grouped ? { source_product_group_id: group.rows[0].product_group_id } : {},
      }] } });
      const createdVariants = result[0]?.variants || [];
      for (const row of group.rows) {
        const variant = createdVariants.find((item) => item.sku === row.sku);
        if (!variant) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Medusa did not create variant ${row.sku}`);
        await writeStock(container, variant.id, locations[0].id, projectAvailableQuantity(row, []));
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
        product_id: product.id, title: variantTitle(row), sku: row.sku, manage_inventory: true, allow_backorder: allowsFiniteBackorder(row),
        options: variantOptions(row), prices: [{ amount: medusaPrice(row.price_minor_zar), currency_code: "zar" }],
        metadata: { source_sku_id: row.source_sku_id, source_revision: row.revision, source_observed_at: row.observed_at, source_available_quantity: row.available_quantity, source_projected_quantity: row.available_quantity, source_price_includes_tax: true, ...syncedCapacityMetadata(row, null) },
      })) } });
      for (const row of added) {
        const variant = result.find((item) => item.sku === row.sku);
        if (!variant) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Medusa did not create variant ${row.sku}`);
        await writeStock(container, variant.id, locations[0].id, projectAvailableQuantity(row, []));
      }
    }
    for (const row of group.rows) {
      const variant = bySkuId.get(row.source_sku_id);
      if (!variant) continue;
      const currentOptions = Object.fromEntries((variant.options || []).map((item) => [item.option?.title, item.value]));
      const nextOptions = variantOptions(row);
      const optionsChanged = JSON.stringify(Object.entries(currentOptions).sort()) !== JSON.stringify(Object.entries(nextOptions).sort());
      const revisionChanged = shouldApplyRevision(row.revision, variant.metadata?.source_revision);
      if (typeof variant.metadata?.source_revision === "string" && row.revision < variant.metadata.source_revision) continue;
      const observationChanged = typeof variant.metadata?.source_observed_at !== "string" || row.observed_at > variant.metadata.source_observed_at;
      const pending = pendingCommitments(variant.metadata);
      const projected = projectAvailableQuantity(row, pending);
      const nextCapacityMetadata = syncedCapacityMetadata(row, variant.metadata);
      const allowBackorder = allowsFiniteBackorder(row);
      const backorderChanged = variant.allow_backorder !== allowBackorder;
      const capacityChanged = JSON.stringify(variant.metadata?.[CAPACITY_STATE_METADATA_KEY]) !==
        JSON.stringify(nextCapacityMetadata[CAPACITY_STATE_METADATA_KEY]) ||
        JSON.stringify(variant.metadata?.storefront_made_to_order_offer) !==
        JSON.stringify(nextCapacityMetadata.storefront_made_to_order_offer);
      const acknowledged = new Set(row.acknowledged_commitment_ids);
      const remainingPending = pending.filter((item) => !acknowledged.has(item.commitment_id));
      const commitmentsChanged = remainingPending.length !== pending.length;
      const projectionChanged = variant.metadata?.source_projected_quantity !== projected || commitmentsChanged;
      // Reservation consumption/cancellation can change independently of the
      // source revision. Rebase stock on every accepted projection.
      await writeStock(container, variant.id, locations[0].id, projected);
      if (!optionsChanged && !revisionChanged && !observationChanged && !projectionChanged && !capacityChanged && !backorderChanged) continue;
      await updateProductVariantsWorkflow(container).run({ input: { product_variants: [{
        id: variant.id, allow_backorder: allowBackorder, ...(revisionChanged ? { sku: row.sku, prices: [{ amount: medusaPrice(row.price_minor_zar), currency_code: "zar" }] } : {}),
        ...(optionsChanged ? { options: nextOptions, title: variantTitle(row) } : {}),
        metadata: { ...variant.metadata, source_sku_id: row.source_sku_id, source_revision: row.revision, source_observed_at: row.observed_at, source_available_quantity: row.available_quantity, source_projected_quantity: projected, pending_paid_commitments: remainingPending, source_price_includes_tax: true, ...nextCapacityMetadata },
      }] } });
    }
  }

  await publishCatalogue(container, new Set(catalogueExternalIds(sourceProducts)));
}
