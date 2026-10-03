import { createHash, timingSafeEqual } from "node:crypto";
import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { ContainerRegistrationKeys, MedusaError } from "@medusajs/framework/utils";
import { storefrontAnalyticsOrderId, storefrontCustomerRefund } from "../../../../../storefront-analytics-ids";
import { storefrontOrderHistory } from "../../../../../storefront-order-history";

function matchesDigest(token: string, digest: unknown): boolean {
  if (typeof digest !== "string" || !/^[a-f0-9]{64}$/.test(digest)) return false;
  const actual = Buffer.from(createHash("sha256").update(token).digest("hex"));
  const expected = Buffer.from(digest);
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}

export async function GET(req: MedusaRequest, res: MedusaResponse): Promise<void> {
  res.setHeader("Cache-Control", "private, no-store, max-age=0");
  res.setHeader("Vary", "Cookie, x-storefront-confirmation-token");
  try {
    const token = req.headers["x-storefront-confirmation-token"];
    if (typeof token !== "string" || !/^[A-Za-z0-9_-]{40,100}$/.test(token)) {
      throw new MedusaError(MedusaError.Types.NOT_FOUND, "Order confirmation not found");
    }
    const query = req.scope.resolve(ContainerRegistrationKeys.QUERY);
    const { data: carts } = await query.graph({
      entity: "cart", fields: ["id", "metadata", "email"], filters: { id: req.params.id },
    });
    const cart = carts[0] as { id: string; email?: string; metadata?: Record<string, unknown> | null } | undefined;
    if (!cart || !matchesDigest(token, cart.metadata?.storefront_confirmation_sha256)) {
      throw new MedusaError(MedusaError.Types.NOT_FOUND, "Order confirmation not found");
    }

    const { data: links } = await query.graph({
      entity: "order_cart", fields: ["order_id"], filters: { cart_id: cart.id },
    });
    const orderId = links[0]?.order_id;
    if (typeof orderId === "string") {
      const { data: orders } = await query.graph({
        entity: "order",
        fields: [
          "id", "display_id", "email", "currency_code", "subtotal", "shipping_total", "tax_total", "total",
          "items.id", "items.title", "items.quantity", "items.unit_price", "items.total",
          "items.metadata",
          "shipping_methods.name", "shipping_methods.amount",
          "shipping_address.first_name", "shipping_address.last_name", "shipping_address.address_1",
          "shipping_address.address_2", "shipping_address.city", "shipping_address.province",
          "shipping_address.postal_code", "metadata",
        ],
        filters: { id: orderId },
      });
      const order = orders[0] as Record<string, any> | undefined;
      if (!order || !matchesDigest(token, order.metadata?.storefront_confirmation_sha256)) {
        throw new MedusaError(MedusaError.Types.NOT_FOUND, "Order confirmation not found");
      }
      const checkout = order.metadata?.storefront_checkout;
      const history = storefrontOrderHistory(order);
      const refundRows = Array.isArray(order.metadata?.storefront_refunds) ? order.metadata.storefront_refunds : [];
      const refunds = refundRows.filter((item: unknown) => item && typeof item === "object" &&
        ["pending", "succeeded", "failed"].includes((item as Record<string, unknown>).status as string))
        .map((item: Record<string, unknown>) => storefrontCustomerRefund(item));
      const fulfillmentStatus = order.metadata?.storefront_fulfillment_status || {
        fulfillment_type: checkout?.fulfillment_type || "delivery",
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
          fulfillment_type: checkout?.fulfillment_type,
          fulfillment_status: fulfillmentStatus.status,
          fulfillment_revision: fulfillmentStatus.revision,
          fulfillment_promise: order.metadata?.storefront_fulfillment_promise || null,
          refund_status: refunds.length ? {
            refunded_amount_minor: refunds.filter((item: { status: string }) => item.status === "succeeded")
              .reduce((sum: number, item: { amount_minor: number }) => sum + item.amount_minor, 0),
            items: refunds,
          } : null,
          items: (order.items || []).map((item: Record<string, unknown>) => ({
            title: item.title, quantity: item.quantity,
            unit_price: history.itemTotals.has(String(item.id)) && Number(item.quantity) > 0
              ? Number((history.itemTotals.get(String(item.id))! / Number(item.quantity)).toFixed(2)) : item.unit_price,
            total: history.itemTotals.get(String(item.id)) ?? item.total,
            fulfillment_promise: (item.metadata as Record<string, unknown> | undefined)?.fulfillment_promise || null,
          })),
          shipping: (order.shipping_methods || []).map((method: Record<string, unknown>) => ({
            name: method.name, total: method.amount,
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
      return;
    }

    const exception = cart.metadata?.storefront_payment_exception as { status?: string } | undefined;
    const { data: cartPaymentLinks } = await query.graph({
      entity: "cart_payment_collection", fields: ["payment_collection_id"], filters: { cart_id: cart.id },
    });
    const collectionId = cartPaymentLinks[0]?.payment_collection_id;
    const { data: sessions } = collectionId ? await query.graph({
      entity: "payment_session", fields: ["status", "metadata"], filters: { payment_collection_id: collectionId },
    }) : { data: [] };
    const session = sessions[0] as { status?: string; metadata?: Record<string, unknown> | null } | undefined;
    const paymentStatus = session?.status;
    const events = session?.metadata?.storefront_test_events;
    const lastEvent = Array.isArray(events)
      ? events[events.length - 1] as { status?: string } | undefined
      : undefined;
    const status = exception?.status === "paid_exception" ? "paid_exception"
      : lastEvent?.status === "unknown" ? "unknown"
      : paymentStatus === "captured" || paymentStatus === "authorized" ? "processing"
      : paymentStatus === "error" ? "declined"
      : paymentStatus === "canceled" ? "cancelled"
      : "pending";
    res.status(200).json({ status });
  } catch (error) {
    const status = error instanceof MedusaError && error.type === MedusaError.Types.NOT_FOUND ? 404 : 503;
    res.status(status).json({ message: status === 404 ? "Order confirmation not found" : "Order confirmation is temporarily unavailable" });
  }
}
