import { createHmac, timingSafeEqual } from "node:crypto";
import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { ContainerRegistrationKeys, MedusaError } from "@medusajs/framework/utils";
import { storefrontAnalyticsOrderId, storefrontCustomerRefund } from "../../../../../storefront-analytics-ids";
import { storefrontOrderHistory } from "../../../../../storefront-order-history";

function validAccess(orderId: string, supplied: unknown, digest: unknown): boolean {
  const secret = process.env.STOREFRONT_BFF_SECRET;
  if (!secret || secret.length < 32 || typeof supplied !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(supplied) ||
      typeof digest !== "string" || !/^[a-f0-9]{64}$/i.test(digest)) return false;
  const expected = Buffer.from(createHmac("sha256", secret)
    .update(`storefront-order-status:v1:${orderId}:${digest}`)
    .digest("base64url"));
  const received = Buffer.from(supplied);
  return received.length === expected.length && timingSafeEqual(received, expected);
}

export async function GET(req: MedusaRequest, res: MedusaResponse): Promise<void> {
  res.setHeader("Cache-Control", "private, no-store, max-age=0");
  res.setHeader("Referrer-Policy", "no-referrer");
  res.setHeader("Vary", "x-storefront-order-status-token");
  try {
    const query = req.scope.resolve(ContainerRegistrationKeys.QUERY);
    const { data } = await query.graph({
      entity: "order",
      fields: [
        "id", "display_id", "email", "currency_code", "subtotal", "shipping_total", "tax_total", "total",
        "items.id", "items.title", "items.quantity", "items.unit_price", "items.total", "items.metadata",
        "shipping_methods.name", "shipping_methods.amount", "shipping_address.first_name", "shipping_address.last_name",
        "shipping_address.address_1", "shipping_address.address_2", "shipping_address.city", "shipping_address.province",
        "shipping_address.postal_code", "metadata",
      ],
      filters: { id: req.params.id },
    });
    const order = data[0] as Record<string, any> | undefined;
    if (!order || !validAccess(order.id, req.headers["x-storefront-order-status-token"], order.metadata?.storefront_confirmation_sha256)) {
      throw new MedusaError(MedusaError.Types.NOT_FOUND, "Order status not found");
    }
    const checkout = order.metadata?.storefront_checkout || {};
    const history = storefrontOrderHistory(order);
    const refundRows = Array.isArray(order.metadata?.storefront_refunds) ? order.metadata.storefront_refunds : [];
    const refunds = refundRows.filter((item: unknown) => item && typeof item === "object" &&
      ["pending", "succeeded", "failed"].includes((item as Record<string, unknown>).status as string))
      .map((item: Record<string, unknown>) => storefrontCustomerRefund(item));
    const fulfillmentStatus = order.metadata?.storefront_fulfillment_status || {
      fulfillment_type: checkout.fulfillment_type || "delivery",
      status: "confirmed",
      revision: 0,
    };
    res.status(200).json({
      status: "captured",
      order: {
        reference: order.display_id,
        analytics_order_id: storefrontAnalyticsOrderId(order.id),
        email: order.email,
        currency_code: order.currency_code,
        subtotal: history.subtotal,
        shipping_total: history.shipping_total,
        tax_total: history.tax_total,
        total: history.total,
        captured_amount_minor: history.captured_amount_minor,
        captured_at: history.captured_at,
        fulfillment_type: fulfillmentStatus.fulfillment_type || checkout.fulfillment_type,
        fulfillment_status: fulfillmentStatus.status,
        fulfillment_revision: fulfillmentStatus.revision,
        fulfillment_promise: order.metadata?.storefront_fulfillment_promise || null,
        refund_status: refunds.length ? {
          refunded_amount_minor: refunds.filter((item: { status: string }) => item.status === "succeeded")
            .reduce((sum: number, item: { amount_minor: number }) => sum + item.amount_minor, 0),
          items: refunds,
        } : null,
        items: (order.items || []).map((item: Record<string, any>) => ({
          title: item.title,
          quantity: item.quantity,
          unit_price: history.itemTotals.has(String(item.id)) && Number(item.quantity) > 0
            ? Number((history.itemTotals.get(String(item.id))! / Number(item.quantity)).toFixed(2)) : item.unit_price,
          total: history.itemTotals.get(String(item.id)) ?? item.total,
          fulfillment_promise: item.metadata?.fulfillment_promise || null,
        })),
        shipping: (order.shipping_methods || []).map((method: Record<string, unknown>) => ({
          name: method.name,
          total: method.amount,
        })),
        address: order.shipping_address ? {
          first_name: order.shipping_address.first_name,
          last_name: order.shipping_address.last_name,
          address_1: order.shipping_address.address_1,
          address_2: order.shipping_address.address_2,
          city: order.shipping_address.city,
          province: order.shipping_address.province,
          postal_code: order.shipping_address.postal_code,
        } : null,
      },
    });
  } catch (error) {
    const status = error instanceof MedusaError && error.type === MedusaError.Types.NOT_FOUND ? 404 : 503;
    res.status(status).json({ message: status === 404 ? "Order status not found" : "Order status is temporarily unavailable" });
  }
}
