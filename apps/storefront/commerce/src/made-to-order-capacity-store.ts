import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import { updateProductVariantsWorkflow } from "@medusajs/medusa/core-flows";
import {
  CAPACITY_STATE_METADATA_KEY,
  consumeCapacity,
  offerPresentation,
  readCapacityState,
} from "./made-to-order-capacity";

type PromiseSnapshot = { kind?: unknown; offer_id?: unknown } | null;

function linePromise(metadata: Record<string, unknown> | null): PromiseSnapshot {
  const value = metadata?.fulfillment_promise;
  return value && typeof value === "object" && !Array.isArray(value) ? value as PromiseSnapshot : null;
}

/**
 * Convert paid made-to-order holds into durable order commitments. Call while
 * holding the shared `storefront:inventory` lock and after the immutable
 * handoff outbox payload is persisted. The order/line key makes retries safe.
 */
export async function commitMadeToOrderCapacity(
  container: MedusaContainer,
  orderId: string,
  nowMs = Date.now(),
): Promise<void> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data: orders } = await query.graph({
    entity: "order",
    fields: ["id", "items.id", "items.quantity", "items.detail.quantity", "items.metadata", "items.variant.id", "items.variant.sku", "items.variant.metadata"],
    filters: { id: orderId },
  });
  const lines = (orders[0]?.items || []) as {
    id: string;
    quantity: number;
    metadata: Record<string, unknown> | null;
    variant?: { id?: string; sku?: string | null; metadata?: Record<string, unknown> | null } | null;
  }[];
  const mtoLines = lines.filter((line) => linePromise(line.metadata)?.kind === "made_to_order");
  if (!mtoLines.length) return;
  const orderCartQuery = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data: cartLinks } = await orderCartQuery.graph({
    entity: "order_cart", fields: ["cart_id"], filters: { order_id: orderId },
  });
  const cartId = cartLinks[0]?.cart_id;
  if (typeof cartId !== "string") throw new Error("made_to_order_order_cart_missing");

  const metadataByVariant = new Map<string, Record<string, unknown>>();
  for (const line of mtoLines) {
    const promise = linePromise(line.metadata);
    const offerId = promise?.offer_id;
    const cartLineId = line.metadata?.storefront_capacity_hold_line_id;
    const variantId = line.variant?.id;
    const sku = line.variant?.sku;
    const sourceSkuId = line.variant?.metadata?.source_sku_id;
    if (typeof offerId !== "string" || typeof cartLineId !== "string" ||
      typeof sku !== "string" || typeof sourceSkuId !== "string" || typeof variantId !== "string" ||
      !Number.isSafeInteger(line.quantity) || line.quantity < 1) {
      throw new Error("made_to_order_paid_line_invalid");
    }
    const variant = line.variant;
    const currentMetadata = metadataByVariant.get(variantId) || variant?.metadata || {};
    const state = readCapacityState(currentMetadata);
    const commitmentId = `storefront:${orderId}:${line.id}`;
    const next = consumeCapacity(
      state, offerId, cartId, cartLineId, commitmentId, line.quantity, nowMs,
    );
    if (next === state) continue;
    const presentation = offerPresentation(next, nowMs);
    const updatedMetadata = {
      ...currentMetadata,
      [CAPACITY_STATE_METADATA_KEY]: next,
      storefront_made_to_order_offer: presentation ? {
        ...presentation,
        observed_at: typeof currentMetadata.source_observed_at === "string" ? currentMetadata.source_observed_at : null,
      } : null,
    };
    await updateProductVariantsWorkflow(container).run({
      input: { product_variants: [{
        id: variantId,
        metadata: updatedMetadata,
      }] },
    });
    metadataByVariant.set(variantId, updatedMetadata);
  }
}
