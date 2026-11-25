import type { IInventoryService, MedusaContainer, ReservationItemDTO } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, MedusaError, Modules, ProductStatus } from "@medusajs/framework/utils";
import { createHash } from "node:crypto";
import { reconcileStorefrontHandoffs } from "./storefront-order-handoff";
import { recordOpsCheckoutHealth, refreshOpsCheckoutHealth } from "./storefront-commerce-exceptions";
import { CAPACITY_STATE_METADATA_KEY, mergeCapacityState, offerPresentation, readCapacityState } from "./made-to-order-capacity";
import {
  batchLinkProductsToCategoryWorkflow, batchVariantImagesWorkflow, createCollectionsWorkflow, createInventoryLevelsWorkflow, createProductsWorkflow,
  createProductVariantsWorkflow, deleteFilesWorkflow, deleteProductVariantsWorkflow, linkProductsToSalesChannelWorkflow, updateCollectionsWorkflow,
  updateInventoryLevelsWorkflow, updateProductVariantsWorkflow, updateProductsWorkflow, uploadFilesWorkflow,
} from "@medusajs/medusa/core-flows";

import {
  CATALOGUE_COLLECTION_HANDLE, CATALOGUE_COLLECTION_TITLE, LEGACY_CATALOGUE_COLLECTION_HANDLE, STOREFRONT_CATEGORIES,
  collectionEnsurePlan, type CollectionRecord,
} from "./catalogue-collections";
import { medusaPrice, parseOpsProducts, pendingCommitments, projectAvailableQuantity, shouldApplyRevision, type OpsProduct, type OpsProductsResponse } from "./ops-contract";
import { CURATED_PRODUCT_METADATA_KEY } from "./publication";

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

function syncedCapacityMetadata(row: OpsProduct, metadata: Record<string, unknown> | null) {
  const state = mergeCapacityState(metadata, row.made_to_order_offer, row.revision);
  const presentation = offerPresentation(state, Date.now());
  return {
    [CAPACITY_STATE_METADATA_KEY]: state,
    storefront_made_to_order_offer: presentation ? { ...presentation, observed_at: row.observed_at } : null,
  };
}

function syncedCatalogueMetadata(row: OpsProduct) {
  return {
    ...(row.dimensions_cm === undefined ? {} : { dimensions_cm: row.dimensions_cm }),
    ...(row.piece_count === undefined ? {} : { piece_count: row.piece_count }),
    // Variant metadata key the storefront card reads; null once Firstout clears the colour.
    ...(row.swatch_hex === undefined ? {} : { swatch_hex: row.swatch_hex }),
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

export function catalogueExternalIds(source: OpsProduct[], curated = false): string[] {
  return groupOpsProducts(source)
    .filter((group) => curated ? group.rows.some(isCatalogueRow) : group.rows.every(isCatalogueRow))
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

async function opsGet(path: string): Promise<{ response: Response; companyId: string }> {
  const url = process.env.FIRSTOUT_OPS_URL;
  const token = process.env.FIRSTOUT_OPS_TOKEN;
  const companyId = process.env.FIRSTOUT_OPS_COMPANY_ID;
  if (!url || !token || !companyId) {
    throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Firstout Ops Commerce connection is not configured");
  }
  const response = await fetch(`${url.replace(/\/$/, "")}${path}`, {
    headers: { Authorization: `Bearer ${token}`, "X-Ops-Company-ID": companyId },
    signal: AbortSignal.timeout(10_000),
    redirect: "error",
  });
  if (!response.ok) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Firstout Ops Commerce returned ${response.status}`);
  return { response, companyId };
}

async function fetchOpsProducts(): Promise<OpsProductsResponse> {
  const { response, companyId } = await opsGet(
    "/products?catalogue_version=2&include_setting_photo=true&include_detail_photo=true&include_swatch=true",
  );
  return parseOpsProducts(await response.json(), companyId);
}

type PaidReservationOrder = {
  metadata?: Record<string, unknown> | null;
  items?: { id: string }[];
  payment_collections?: { payments?: { captured_at?: string | Date | null }[] }[];
};

async function paidStorefrontOrdersForLineItems(container: MedusaContainer, lineIds: string[]): Promise<PaidReservationOrder[]> {
  if (!lineIds.length) return [];
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const relevantOrderIds = new Set<string>();
  const pageSize = 500;
  for (let skip = 0; ; skip += pageSize) {
    const { data: orderItems } = await query.graph({
      entity: "order_item", fields: ["item_id", "order_id"],
      filters: { item_id: lineIds },
      pagination: { skip, take: pageSize },
    });
    for (const item of orderItems) {
      // Medusa returns the selected native FK although its generated OrderItem
      // type omits it. Validate the wire field rather than guessing ownership.
      const orderId: unknown = Reflect.get(item, "order_id");
      if (typeof orderId !== "string" || !orderId) {
        throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Native order item mapping is missing");
      }
      relevantOrderIds.add(orderId);
    }
    if (orderItems.length < pageSize) break;
  }
  const orderIds = [...relevantOrderIds];
  if (!orderIds.length) return [];
  const { data: orders } = await query.graph({
    entity: "order", fields: ["id", "metadata", "items.id", "payment_collections.payments.captured_at"],
    filters: { id: orderIds }, pagination: { take: orderIds.length },
  });
  return (orders as PaidReservationOrder[]).filter((order) => order.metadata?.storefront_confirmation_sha256 &&
    order.payment_collections?.some((collection) => collection.payments?.some((payment) => payment.captured_at)));
}

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
  const paidOrders = await paidStorefrontOrdersForLineItems(container, orderReservations.map((row) => row.line_item_id!));
  const paidLines = new Set(paidOrders.flatMap((order) => (order.items || []).map((item) => item.id)));
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
  // cart holds and reservations outside captured DasKasas orders still reduce
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
  sales_channels?: { id: string }[];
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

async function listedCollections(container: MedusaContainer): Promise<CollectionRecord[]> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({ entity: "product_collection", fields: ["id", "handle", "title"] });
  return (data as { id?: string; handle?: string; title?: string }[]).flatMap((row) =>
    row.id && row.handle && typeof row.title === "string" ? [{ id: row.id, handle: row.handle, title: row.title }] : [],
  );
}

async function ensureCollection(
  container: MedusaContainer, rows: CollectionRecord[], handle: string, title: string, legacyHandle?: string,
): Promise<string> {
  const plan = collectionEnsurePlan(rows, handle, title, legacyHandle);
  if (plan.action === "keep") return plan.id;
  if (plan.action === "retitle" || plan.action === "rename") {
    await updateCollectionsWorkflow(container).run({
      input: { selector: { id: plan.id }, update: plan.action === "rename" ? { title, handle } : { title } },
    });
    return plan.id;
  }
  const { result } = await createCollectionsWorkflow(container).run({
    input: { collections: [{ title, handle }] },
  });
  const created = (Array.isArray(result) ? result : []) as { id?: string }[];
  const id = created[0]?.id;
  if (!id) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Medusa did not create the ${title} collection`);
  rows.push({ id, handle, title });
  return id;
}

async function ensureStorefrontCollections(container: MedusaContainer): Promise<string> {
  const rows = await listedCollections(container);
  const saleId = await ensureCollection(
    container, rows, CATALOGUE_COLLECTION_HANDLE, CATALOGUE_COLLECTION_TITLE, LEGACY_CATALOGUE_COLLECTION_HANDLE,
  );
  return saleId;
}

async function setCatalogueMembership(
  container: MedusaContainer, ids: string[], update: { status: ProductStatus; collection_id?: string | null },
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

async function publishCatalogue(container: MedusaContainer, readyIds: Set<string>, curatedChannel?: string, withdrawOnly = false) {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({
    entity: "product", fields: ["id", "external_id", "status", "collection_id", "sales_channels.id"],
  });
  const products = (data as CatalogueProduct[]).filter((product) => curatedChannel || product.external_id?.startsWith(SOURCE_PREFIX));
  const wanted = products.filter((product) => readyIds.has(product.external_id || ""));
  const withdraw = products
    .filter((product) => product.external_id?.startsWith(SOURCE_PREFIX))
    .filter((product) => !readyIds.has(product.external_id || "") &&
      (product.status !== ProductStatus.DRAFT || !!product.collection_id))
    .map((product) => product.id);
  if (withdraw.length) {
    await setCatalogueMembership(container, withdraw, { status: ProductStatus.DRAFT, collection_id: null });
  }
  if (curatedChannel) {
    const manualIds = products.filter((product) => !product.external_id?.startsWith(SOURCE_PREFIX) &&
      product.sales_channels?.some(({ id }) => id === curatedChannel)).map((product) => product.id);
    if (manualIds.length) await linkProductsToSalesChannelWorkflow(container).run({
      input: { id: curatedChannel, remove: manualIds },
    });
  }
  if (withdrawOnly) return;
  if (curatedChannel) {
    const missing = wanted.filter((product) => !product.sales_channels?.some(({ id }) => id === curatedChannel));
    if (missing.length) await linkProductsToSalesChannelWorkflow(container).run({
      input: { id: curatedChannel, add: missing.map((product) => product.id) },
    });
  }
  const collectionId = await ensureStorefrontCollections(container);
  const publish = wanted
    .filter((product) => product.status !== ProductStatus.PUBLISHED || product.collection_id !== collectionId)
    .map((product) => product.id);
  if (publish.length) await publishCatalogueProducts(container, publish, collectionId);
}

async function storefrontChannel(container: MedusaContainer, curated: boolean): Promise<string | undefined> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data: channels } = await query.graph({
    entity: "sales_channel", fields: ["id", "name"], ...(curated ? { filters: { name: "DasKasas" } } : {}),
  });
  if (curated && channels.length !== 1) {
    throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "The curated catalogue needs one DasKasas sales channel");
  }
  return channels[0]?.id;
}

/** Variant metadata: the Firstout photo token last synced, whether or not staff kept the image. */
const PHOTO_TOKEN_METADATA_KEY = "firstout_photo_token";
/** Product image metadata marking an image the sync created; any other image belongs to staff. */
const PHOTO_SOURCE_METADATA_KEY = "firstout_source_sku_id";
const PHOTO_SLOT_METADATA_KEY = "firstout_gallery_slot";
const GALLERY_TOKENS_METADATA_KEY = "firstout_gallery_photo_tokens";
const SETTING_PHOTO_SLOT = 4;
const DETAIL_PHOTO_SLOT = 5;

type PhotoImage = { id: string; url: string; metadata?: Record<string, unknown> | null };
type PhotoVariant = {
  id: string; thumbnail?: string | null; metadata: Record<string, unknown> | null; images?: { id: string }[];
};
type PhotoProduct = {
  id: string; external_id: string | null; thumbnail?: string | null; images?: PhotoImage[]; variants?: PhotoVariant[];
};

const MAX_PHOTO_BYTES = 5 * 1024 * 1024;

/** Reads a JPEG of at most 5 MB; anything else (an HTML error page, an oversized body) is refused. */
async function readJpeg(response: Response): Promise<Buffer> {
  const type = response.headers.get("content-type")?.split(";")[0].trim().toLowerCase();
  if (type !== "image/jpeg") throw new MedusaError(MedusaError.Types.INVALID_DATA, `photo is ${type || "untyped"}, not image/jpeg`);
  if (Number(response.headers.get("content-length")) > MAX_PHOTO_BYTES) {
    throw new MedusaError(MedusaError.Types.INVALID_DATA, "photo is larger than 5 MB");
  }
  const chunks: Uint8Array[] = [];
  let size = 0;
  const reader = response.body?.getReader();
  for (let read = await reader?.read(); read && !read.done; read = await reader!.read()) {
    size += read.value.length;
    if (size > MAX_PHOTO_BYTES) {
      await reader!.cancel();
      throw new MedusaError(MedusaError.Types.INVALID_DATA, "photo is larger than 5 MB");
    }
    chunks.push(read.value);
  }
  const bytes = Buffer.concat(chunks);
  if (bytes[0] !== 0xff || bytes[1] !== 0xd8 || bytes[2] !== 0xff) {
    throw new MedusaError(MedusaError.Types.INVALID_DATA, "photo is not a JPEG");
  }
  return bytes;
}

/** Uploads the photo and adds it to the gallery, replacing only the sync's own image for this SKU. */
async function addPhotoToGallery(
  container: MedusaContainer, product: PhotoProduct, sourceSkuId: string, token: string,
): Promise<PhotoImage> {
  const { response } = await opsGet(`/products/${sourceSkuId}/photo`);
  const content = (await readJpeg(response)).toString("base64");
  const { result: [file] } = await uploadFilesWorkflow(container).run({ input: { files: [{
    filename: `firstout-${sourceSkuId}.jpg`, mimeType: "image/jpeg", content, access: "public",
  }] } });
  const images = product.images || [];
  const previous = images.filter((image) => image.metadata?.[PHOTO_SOURCE_METADATA_KEY] === sourceSkuId);
  const replaceable = !product.thumbnail || previous.some((image) => image.url === product.thumbnail);
  const kept = images.filter((image) => !previous.includes(image));
  const metadata = { [PHOTO_SOURCE_METADATA_KEY]: sourceSkuId, [PHOTO_TOKEN_METADATA_KEY]: token };
  // Medusa replaces the image list, so every staff image is passed back unchanged.
  try {
    await updateProductsWorkflow(container).run({ input: { selector: { id: product.id }, update: {
      images: [...kept.map(({ id, url }) => ({ id, url })), { url: file.url, metadata }],
      ...(replaceable ? { thumbnail: file.url } : {}),
    } } });
  } catch (error) {
    // A rejected update (e.g. the publication hook) would otherwise leave one file per retry on the volume.
    await deleteFilesWorkflow(container).run({ input: { ids: [file.id] } });
    throw error;
  }
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({ entity: "product", fields: ["images.id", "images.url"], filters: { id: product.id } });
  let image = ((data[0] as PhotoProduct | undefined)?.images || []).find((candidate) => candidate.url === file.url);
  if (!image) {
    await deleteFilesWorkflow(container).run({ input: { ids: [file.id] } });
    throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Medusa did not keep the photo for ${sourceSkuId}`);
  }
  image = { ...image, metadata };
  product.images = [...kept, image];
  if (replaceable) product.thumbnail = file.url;
  return image;
}

/**
 * The gallery image carries its token, so a run that failed after the upload
 * reuses that image and retries only the variant link, never the upload.
 */
async function syncVariantPhoto(
  container: MedusaContainer, product: PhotoProduct, variant: PhotoVariant, sourceSkuId: string, token: string,
) {
  const owned = (product.images || []).filter((image) => image.metadata?.[PHOTO_SOURCE_METADATA_KEY] === sourceSkuId);
  const image = owned.find((candidate) => candidate.metadata?.[PHOTO_TOKEN_METADATA_KEY] === token) ||
    await addPhotoToGallery(container, product, sourceSkuId, token);
  if (!variant.images?.some((linked) => linked.id === image.id)) {
    await batchVariantImagesWorkflow(container).run({ input: { variant_id: variant.id, add: [image.id] } });
  }
  const replaceable = !variant.thumbnail || owned.some((candidate) => candidate.url === variant.thumbnail);
  // Metadata merges in Medusa, so only the token key is written.
  await updateProductVariantsWorkflow(container).run({ input: { product_variants: [{
    id: variant.id, ...(replaceable ? { thumbnail: image.url } : {}),
    metadata: { [PHOTO_TOKEN_METADATA_KEY]: token },
  }] } });
}

/** Stage every changed image before linking the reviewed gallery to its variant. */
async function syncReviewedGallery(
  container: MedusaContainer, product: PhotoProduct, variant: PhotoVariant, row: OpsProduct, useAsProductHero: boolean,
): Promise<void> {
  const studioTokens = row.gallery_photo_tokens || [];
  const images = product.images || [];
  const owned = images.filter((image) => image.metadata?.[PHOTO_SOURCE_METADATA_KEY] === row.source_sku_id);
  const findImage = (slot: number, token: string) => owned.find((image) =>
    image.metadata?.[PHOTO_SLOT_METADATA_KEY] === slot && image.metadata?.[PHOTO_TOKEN_METADATA_KEY] === token);
  const previousTokens = variant.metadata?.[GALLERY_TOKENS_METADATA_KEY];
  // An older Firstout may omit a supplemental slot. Reuse its previous
  // verified image when still attached to the product.
  const retainedToken = (slot: number): string | null => {
    const token = Array.isArray(previousTokens) ? previousTokens[slot - 1] : undefined;
    return typeof token === "string" && findImage(slot, token) ? token : null;
  };
  const settingCandidate = row.setting_photo_token === undefined ? retainedToken(SETTING_PHOTO_SLOT) : row.setting_photo_token;
  const detailCandidate = row.detail_photo_token === undefined ? retainedToken(DETAIL_PHOTO_SLOT) : row.detail_photo_token;
  // The source's explicitly supplied tokens take precedence over retained
  // assets if the same image is now used in a different slot.
  const setting = settingCandidate && !studioTokens.includes(settingCandidate) && settingCandidate !== row.detail_photo_token
    ? settingCandidate : null;
  const detail = detailCandidate && !studioTokens.includes(detailCandidate) && detailCandidate !== setting
    ? detailCandidate : null;
  const tokens: (string | null)[] = [...studioTokens];
  if (setting || detail) tokens.push(setting);
  if (detail) tokens.push(detail);
  const slots = tokens.flatMap((token, index) => token ? [{ token, slot: index + 1 }] : []);
  const missing = slots.filter(({ token, slot }) => !findImage(slot, token));
  const toUpload = await Promise.all(missing.map(async ({ token, slot }) => {
    const { response } = await opsGet(`/products/${row.source_sku_id}/photo?slot=${slot}`);
    const bytes = await readJpeg(response);
    if (createHash("sha256").update(bytes).digest("hex") !== token) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, "Firstout gallery changed during download");
    }
    return { slot, token, file: {
      filename: `firstout-${row.source_sku_id}-${slot}.jpg`, mimeType: "image/jpeg", content: bytes.toString("base64"),
      access: "public" as const,
    } };
  }));
  if (toUpload.length) {
    const { result: files } = await uploadFilesWorkflow(container).run({ input: { files: toUpload.map((entry) => entry.file) } });
    const added = toUpload.map(({ slot, token }, index) => ({ url: files[index].url, metadata: {
      [PHOTO_SOURCE_METADATA_KEY]: row.source_sku_id, [PHOTO_SLOT_METADATA_KEY]: slot, [PHOTO_TOKEN_METADATA_KEY]: token,
    } }));
    try {
      await updateProductsWorkflow(container).run({ input: { selector: { id: product.id }, update: {
        images: [...images.map(({ id, url }) => ({ id, url })), ...added],
      } } });
    } catch (error) {
      await deleteFilesWorkflow(container).run({ input: { ids: files.map((file) => file.id) } });
      throw error;
    }
    const query = container.resolve(ContainerRegistrationKeys.QUERY);
    const { data } = await query.graph({ entity: "product", fields: ["images.id", "images.url"], filters: { id: product.id } });
    const attached = (data[0] as PhotoProduct | undefined)?.images || [];
    for (const entry of added) {
      const image = attached.find((candidate) => candidate.url === entry.url);
      if (!image) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Medusa did not attach the reviewed gallery");
      owned.push({ ...image, metadata: entry.metadata });
    }
    product.images = [...images, ...owned.filter((image) => !images.some(({ id }) => id === image.id))];
  }

  const ordered = slots.map(({ slot, token }) => findImage(slot, token)!);
  const urls = ordered.map((image) => image.url);
  const newIds = new Set(ordered.map((image) => image.id));
  const linkedIds = new Set((variant.images || []).map((image) => image.id));
  const add = [...newIds].filter((id) => !linkedIds.has(id));
  const remove = owned.map((image) => image.id).filter((id) => linkedIds.has(id) && !newIds.has(id));
  if (add.length || remove.length) {
    await batchVariantImagesWorkflow(container).run({ input: { variant_id: variant.id, add, remove } });
  }
  if (variant.thumbnail !== urls[0] || JSON.stringify(variant.metadata?.[GALLERY_TOKENS_METADATA_KEY]) !== JSON.stringify(tokens) ||
      JSON.stringify(variant.metadata?.suitable_image_urls) !== JSON.stringify(urls)) {
    await updateProductVariantsWorkflow(container).run({ input: { product_variants: [{
      id: variant.id, thumbnail: urls[0],
      metadata: { [GALLERY_TOKENS_METADATA_KEY]: tokens, suitable_image_urls: urls },
    }] } });
  }
  if (useAsProductHero && product.thumbnail !== urls[0]) {
    await updateProductsWorkflow(container).run({ input: { selector: { id: product.id }, update: { thumbnail: urls[0] } } });
    product.thumbnail = urls[0];
  }
  const usedByOtherVariants = new Set((product.variants || []).filter(({ id }) => id !== variant.id)
    .flatMap((candidate) => [...(candidate.images || []).map((image) => image.id), candidate.thumbnail]));
  const obsolete = new Set(owned.filter((image) => !newIds.has(image.id) && !usedByOtherVariants.has(image.id) &&
    !usedByOtherVariants.has(image.url) && image.url !== product.thumbnail).map((image) => image.id));
  if (obsolete.size) {
    const retained = (product.images || []).filter((image) => !obsolete.has(image.id));
    await updateProductsWorkflow(container).run({ input: { selector: { id: product.id }, update: {
      images: retained.map(({ id, url }) => ({ id, url })),
    } } });
    product.images = retained;
  }
}

function hasVerifiedStudioGallery(product: PhotoProduct, variant: PhotoVariant, row: OpsProduct): boolean {
  const studioTokens = row.gallery_photo_tokens;
  const urls = variant.metadata?.suitable_image_urls;
  if (!studioTokens?.length || !Array.isArray(urls)) return false;
  const linkedIds = new Set((variant.images || []).map(({ id }) => id));
  return studioTokens.every((token, index) => product.images?.some((image) =>
    image.url === urls[index] && linkedIds.has(image.id) &&
    image.metadata?.[PHOTO_SOURCE_METADATA_KEY] === row.source_sku_id &&
    image.metadata?.[PHOTO_SLOT_METADATA_KEY] === index + 1 &&
    image.metadata?.[PHOTO_TOKEN_METADATA_KEY] === token));
}

/**
 * Only missing photo revisions are uploaded. A curated SKU is ready for
 * publication when all its reviewed images are attached in the approved order.
 */
export async function syncFirstoutPhotos(container: MedusaContainer, source: OpsProduct[]): Promise<Set<string>> {
  const ready = new Set<string>();
  const withPhotos = new Map(source.flatMap((row) =>
    row.gallery_photo_tokens?.length || row.photo_token ? [[row.source_sku_id, row] as const] : []));
  if (!withPhotos.size) return ready;
  const primarySources = new Set(groupOpsProducts(source).map((group) => group.rows[0].source_sku_id));
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const logger = container.resolve(ContainerRegistrationKeys.LOGGER);
  const { data } = await query.graph({
    entity: "product",
    fields: ["id", "external_id", "thumbnail", "images.id", "images.url", "images.metadata", "variants.id", "variants.thumbnail", "variants.metadata", "variants.images.id"],
  });
  for (const product of (data as PhotoProduct[]).filter((row) => row.external_id?.startsWith(SOURCE_PREFIX))) {
    for (const variant of product.variants || []) {
      const sourceSkuId = variant.metadata?.source_sku_id;
      const row = typeof sourceSkuId === "string" ? withPhotos.get(sourceSkuId) : undefined;
      if (!row) continue;
      try {
        if (row.gallery_photo_tokens?.length) {
          await syncReviewedGallery(container, product, variant, row, primarySources.has(row.source_sku_id));
          ready.add(row.source_sku_id);
        } else if (row.photo_token && variant.metadata?.[PHOTO_TOKEN_METADATA_KEY] !== row.photo_token &&
            !Array.isArray(variant.metadata?.[GALLERY_TOKENS_METADATA_KEY])) {
          await syncVariantPhoto(container, product, variant, row.source_sku_id, row.photo_token);
        }
      } catch (error) {
        // An optional photo can retry while the verified studio gallery stays visible.
        if (hasVerifiedStudioGallery(product, variant, row)) ready.add(row.source_sku_id);
        logger.warn(`Firstout photo for SKU ${sourceSkuId} was not synced and will be retried: ${error instanceof Error ? error.message : String(error)}`);
      }
    }
  }
  return ready;
}

/** Product metadata: the Firstout name the sync last set as the title. */
const FIRSTOUT_TITLE_METADATA_KEY = "firstout_title";

type MerchandisedProduct = {
  id: string; external_id: string | null; title?: string | null; metadata: Record<string, unknown> | null;
  categories?: { id: string }[] | null;
};

/**
 * Puts each product in its Firstout shop category, moving it out of the other three and
 * never touching any other category. Renames a product only while its title is still the
 * Firstout name the sync last set, so a staff edit in Medusa Admin always wins. Only rows
 * carrying shop_category (Firstout auto-publish on) are touched; otherwise nothing is written.
 */
export async function syncFirstoutMerchandising(container: MedusaContainer, source: OpsProduct[], curated = false): Promise<void> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const logger = container.resolve(ContainerRegistrationKeys.LOGGER);
  const groups = groupOpsProducts(source).filter((group) => group.rows[0].shop_category);
  if (!groups.length) return;
  const { data } = await query.graph({ entity: "product", fields: ["id", "external_id", "title", "metadata", "categories.id"] });
  const products = new Map((data as MerchandisedProduct[])
    .filter((product) => product.external_id?.startsWith(SOURCE_PREFIX))
    .map((product) => [product.external_id!, product]));

  const placed = groups.filter((group) => products.has(group.externalId));
  if (placed.length) {
    const { data: categories } = await query.graph({
      entity: "product_category", fields: ["id", "handle"],
      filters: { handle: STOREFRONT_CATEGORIES.map((category) => category.handle) },
    });
    const ids = new Map((categories as { id: string; handle: string }[]).map((category) => [category.handle, category.id]));
    const changes = new Map([...ids.values()].map((id) => [id, { add: [] as string[], remove: [] as string[] }]));
    for (const group of placed) {
      const product = products.get(group.externalId)!;
      const target = ids.get(group.rows[0].shop_category!);
      if (!target) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Run the DasKasas bootstrap: a shop category is missing");
      const linked = new Set((product.categories || []).map((category) => category.id));
      for (const [id, change] of changes) {
        if (id === target && !linked.has(id)) change.add.push(product.id);
        if (id !== target && linked.has(id)) change.remove.push(product.id);
      }
    }
    for (const [id, { add, remove }] of changes) {
      if (add.length || remove.length) await batchLinkProductsToCategoryWorkflow(container).run({ input: { id, add, remove } });
    }
  }

  for (const group of groups) {
    const product = products.get(group.externalId);
    if (!product) continue;
    const recorded = product.metadata?.[FIRSTOUT_TITLE_METADATA_KEY];
    // A product synced before names were recorded counts as unedited only while it still has the Firstout name.
    const unedited = product.title === (typeof recorded === "string" ? recorded : group.title);
    const reviewed = curated && group.rows.some((row) => row.gallery_photo_tokens?.length);
    if ((!reviewed && !unedited) || (recorded === group.title && product.title === group.title)) continue;
    try {
      // Metadata merges in Medusa, so only the recorded name is written.
      await updateProductsWorkflow(container).run({ input: { selector: { id: product.id }, update: {
        title: group.title, metadata: { [FIRSTOUT_TITLE_METADATA_KEY]: group.title },
      } } });
    } catch (error) {
      if (reviewed) throw error;
      logger.warn(`Firstout name for ${group.externalId} was not synced and will be retried: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
}

export async function syncFirstout(container: MedusaContainer): Promise<void> {
  const locking = container.resolve(Modules.LOCKING);
  // Keep all phases on one source snapshot without holding the checkout lock
  // across remote image downloads. A later sync cannot publish an older gallery.
  await locking.execute("storefront:catalogue-sync", async () => {
    const { snapshot, channelId } = await locking.execute("storefront:inventory", async () => syncFirstoutLocked(container));
    const { products: source, curated_catalogue: curated } = snapshot;
    const logger = container.resolve(ContainerRegistrationKeys.LOGGER);
    try {
      await syncFirstoutMerchandising(container, source, curated);
    } catch (error) {
      if (curated) throw error;
      logger.warn(`Firstout names and categories skipped this run: ${error instanceof Error ? error.message : String(error)}`);
    }
    try {
      const galleries = await syncFirstoutPhotos(container, source);
      if (curated) {
        const eligible = new Set(catalogueExternalIds(source, true));
        const ready = groupOpsProducts(source).filter((group) => eligible.has(group.externalId) &&
          group.rows.every((row) => !row.gallery_photo_tokens?.length || galleries.has(row.source_sku_id)));
        await locking.execute("storefront:inventory", async () => publishCatalogue(container, new Set(ready.map((group) => group.externalId)), channelId));
      }
    } catch (error) {
      if (curated) throw error;
      logger.warn(`Firstout photo sync skipped this run: ${error instanceof Error ? error.message : String(error)}`);
    }
  });
}

// Medusa recreates variants when their product group changes. Its delete
// workflow also removes the variant's inventory links, so check all moves
// before touching any catalogue rows.
async function assertPaidRecoveryHasSnapshot(
  container: MedusaContainer, variant: CommerceVariant, source: unknown,
): Promise<void> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const lineIds = new Set<string>();
  const pageSize = 500;
  for (let skip = 0; ; skip += pageSize) {
    const { data } = await query.graph({
      entity: "order_line_item", fields: ["id"], filters: { variant_id: variant.id }, pagination: { skip, take: pageSize },
    });
    for (const line of data) lineIds.add(line.id);
    if (data.length < pageSize) break;
  }
  for (const order of await paidStorefrontOrdersForLineItems(container, [...lineIds])) {
    const affected = (order.items || []).filter(({ id }) => lineIds.has(id));
    if (!affected.length) continue;
    const outbox = order.metadata?.storefront_handoff_outbox as { status?: unknown; payload?: { lines?: unknown[] } } | null | undefined;
    const lines = Array.isArray(outbox?.payload?.lines) ? outbox.payload.lines : [];
    const captured = new Set(lines.flatMap((line) => {
      if (!line || typeof line !== "object" || !("external_line_id" in line) || !("source_sku_id" in line) || !("sku" in line) ||
          typeof line.external_line_id !== "string" || line.source_sku_id !== source || line.sku !== variant.sku) return [];
      return [line.external_line_id];
    }));
    if (affected.some(({ id }) => !captured.has(id))) {
      throw new MedusaError(MedusaError.Types.NOT_ALLOWED, `Catalogue regrouping waits for the paid-order handoff snapshot on SKU ${variant.sku}`);
    }
    const fulfillment = order.metadata?.storefront_fulfillment_status as { status?: unknown } | null | undefined;
    if (outbox?.status !== "imported" || !["delivered", "collected", "cancelled"].some((status) => status === fulfillment?.status)) {
      throw new MedusaError(MedusaError.Types.NOT_ALLOWED, `Catalogue regrouping waits for a paid order to finish on SKU ${variant.sku}`);
    }
  }
}

async function assertRegroupingSafe(
  container: MedusaContainer, existing: CommerceProduct[], desiredOwner: Map<string, string>,
): Promise<void> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const inventory = container.resolve<IInventoryService>(Modules.INVENTORY);
  const retainedGroups = new Set(desiredOwner.values());
  const now = Date.now();
  for (const product of existing) {
    const oldSource = product.external_id?.startsWith(`${SOURCE_PREFIX}group-`) ? undefined : product.external_id?.slice(SOURCE_PREFIX.length);
    for (const variant of product.variants || []) {
      const source = variant.metadata?.source_sku_id ?? oldSource;
      const owner = typeof source === "string" ? desiredOwner.get(source) : undefined;
      const replacing = owner !== product.external_id && (!!owner || retainedGroups.has(product.external_id || ""));
      if (!replacing) continue;
      const capacity = Object.values(readCapacityState(variant.metadata).allocations);
      const mustRetain = pendingCommitments(variant.metadata).length > 0 ||
        capacity.some((offer) => Object.values(offer.holds).some((hold) => Date.parse(hold.expires_at) > now) ||
          (Date.parse(offer.expires_at) > now && Object.keys(offer.committed).length > 0));
      const { data } = await query.graph({
        entity: "product_variant", fields: ["inventory_items.inventory_item_id"], filters: { id: variant.id },
      });
      const itemIds = ((data[0] as VariantInventory | undefined)?.inventory_items || []).map((item) => item.inventory_item_id);
      if (mustRetain || (itemIds.length && (await inventory.listReservationItems({ inventory_item_id: itemIds }, { take: 1 })).length)) {
        throw new MedusaError(MedusaError.Types.NOT_ALLOWED, `Catalogue regrouping waits for active reservations or paid commitments on SKU ${variant.sku}`);
      }
      await assertPaidRecoveryHasSnapshot(container, variant, source);
    }
  }
}

async function syncFirstoutLocked(container: MedusaContainer): Promise<{ snapshot: OpsProductsResponse; channelId: string }> {
  let snapshot;
  try {
    snapshot = await fetchOpsProducts();
    await refreshOpsCheckoutHealth();
  } catch (error) {
    recordOpsCheckoutHealth({ opsReachable: false, checkoutAllowed: false });
    throw error;
  }
  const { products: sourceProducts, curated_catalogue: curated } = snapshot;
  const eligible = new Set(catalogueExternalIds(sourceProducts, curated));
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
  const channelId = await storefrontChannel(container, Boolean(curated));
  const { data: locations } = await query.graph({ entity: "stock_location", fields: ["id"] });
  const { data: profiles } = await query.graph({ entity: "shipping_profile", fields: ["id"] });
  if (!channelId || !locations[0] || !profiles[0]) {
    throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Run the DasKasas bootstrap before syncing");
  }

  // A SKU may move from its legacy one-SKU product into a group. Release the
  // old variant's unique SKU before creating the grouped variant.
  const desiredOwner = new Map(groups.flatMap((group) =>
    group.rows.map((row) => [row.source_sku_id, group.externalId] as const),
  ));
  if (curated) {
    await assertRegroupingSafe(container, existing, desiredOwner);
    await publishCatalogue(container, eligible, channelId, true);
  }
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
        sales_channels: [{ id: channelId }], options,
        variants: group.rows.map((row) => ({
          title: variantTitle(row), sku: row.sku, manage_inventory: true, allow_backorder: allowsFiniteBackorder(row),
          options: variantOptions(row), prices: [{ amount: medusaPrice(row.price_minor_zar), currency_code: "zar" }],
          metadata: { source_sku_id: row.source_sku_id, source_revision: row.revision, source_observed_at: row.observed_at, source_available_quantity: row.available_quantity, source_projected_quantity: row.available_quantity, source_price_includes_tax: true, ...syncedCapacityMetadata(row, null), ...syncedCatalogueMetadata(row) },
        })),
        metadata: {
          ...(group.grouped ? { source_product_group_id: group.rows[0].product_group_id } : {}),
          ...(group.rows[0].shop_category ? { [FIRSTOUT_TITLE_METADATA_KEY]: group.title } : {}),
          ...(curated ? { [CURATED_PRODUCT_METADATA_KEY]: true } : {}),
        },
      }] } });
      const createdId = result[0]?.id;
      if (!createdId) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Medusa did not create product ${group.externalId}`);
      const createdVariants = result[0]?.variants || [];
      for (const row of group.rows) {
        const variant = createdVariants.find((item) => item.sku === row.sku);
        if (!variant) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, `Medusa did not create variant ${row.sku}`);
        await writeStock(container, variant.id, locations[0].id, projectAvailableQuantity(row, []));
      }
      logger.info(`Projected Firstout product ${group.externalId}`);
      continue;
    }

    if (Boolean(product.metadata?.[CURATED_PRODUCT_METADATA_KEY]) !== Boolean(curated)) {
      await updateProductsWorkflow(container).run({ input: { selector: { id: product.id }, update: {
        status: ProductStatus.DRAFT, metadata: { [CURATED_PRODUCT_METADATA_KEY]: Boolean(curated) },
      } } });
      product.status = ProductStatus.DRAFT;
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
        metadata: { source_sku_id: row.source_sku_id, source_revision: row.revision, source_observed_at: row.observed_at, source_available_quantity: row.available_quantity, source_projected_quantity: row.available_quantity, source_price_includes_tax: true, ...syncedCapacityMetadata(row, null), ...syncedCatalogueMetadata(row) },
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
      const catalogue = syncedCatalogueMetadata(row);
      const catalogueChanged = Object.entries(catalogue).some(([key, value]) => JSON.stringify(value) !== JSON.stringify(variant.metadata?.[key]));
      // Reservation consumption/cancellation can change independently of the
      // source revision. Rebase stock on every accepted projection.
      await writeStock(container, variant.id, locations[0].id, projected);
      if (!optionsChanged && !revisionChanged && !observationChanged && !projectionChanged && !capacityChanged && !backorderChanged && !catalogueChanged) continue;
      await updateProductVariantsWorkflow(container).run({ input: { product_variants: [{
        id: variant.id, allow_backorder: allowBackorder, ...(revisionChanged ? { sku: row.sku, prices: [{ amount: medusaPrice(row.price_minor_zar), currency_code: "zar" }] } : {}),
        ...(optionsChanged ? { options: nextOptions, title: variantTitle(row) } : {}),
        metadata: { ...variant.metadata, source_sku_id: row.source_sku_id, source_revision: row.revision, source_observed_at: row.observed_at, source_available_quantity: row.available_quantity, source_projected_quantity: projected, pending_paid_commitments: remainingPending, source_price_includes_tax: true, ...nextCapacityMetadata, ...catalogue },
      }] } });
    }
  }

  if (!curated) await publishCatalogue(container, eligible);
  return { snapshot, channelId };
}
