import { NextResponse } from "next/server";
import { CustomerAuthError, customerMedusaFetch, getCustomerContext } from "@/lib/customer-auth";
import { orderRefundStatus, paidOrderHistory } from "@/lib/order-history";

export const dynamic = "force-dynamic";

type Context = { params: Promise<{ id: string }> };
const validId = (id: string) => /^order_[A-Za-z0-9_-]+$/.test(id);

function privateReply<T>(body: T, status = 200): NextResponse<T> {
  const response = NextResponse.json(body, { status });
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  response.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
  response.headers.set("Referrer-Policy", "no-referrer");
  return response;
}

export async function GET(_request: Request, { params }: Context): Promise<NextResponse> {
  const { id } = await params;
  if (!validId(id)) return privateReply({ message: "Order not found" }, 404);
  try {
    const customer = await getCustomerContext();
    if (!customer) return privateReply({ message: "Sign in to view this order" }, 401);
    const fields = [
      "id", "display_id", "created_at", "currency_code", "status", "total", "subtotal", "shipping_total", "tax_total", "metadata",
      "items.id", "items.title", "items.quantity", "items.unit_price", "items.total", "shipping_methods.name", "shipping_methods.total",
    ].join(",");
    const { status, payload } = await customerMedusaFetch(customer, `/store/orders/${encodeURIComponent(id)}?fields=${fields}`);
    if (status < 200 || status >= 300 || !payload.order) {
      return privateReply({ message: "Order not found" }, status === 401 ? 401 : status === 503 ? 503 : 404);
    }
    const order = payload.order as Record<string, unknown>;
    const paidHistory = paidOrderHistory(order);
    const items = Array.isArray(order.items) ? order.items.map((value) => {
      if (!value || typeof value !== "object") return null;
      const item = value as Record<string, unknown>;
      return {
        title: typeof item.title === "string" ? item.title : "Item",
        quantity: typeof item.quantity === "number" ? item.quantity : 0,
        unit_price: typeof item.unit_price === "number" || typeof item.unit_price === "string" ? item.unit_price : 0,
        total: typeof item.id === "string" && paidHistory?.items.has(item.id)
          ? paidHistory.items.get(item.id)!
          : typeof item.total === "number" || typeof item.total === "string" ? item.total : 0,
      };
    }).filter((item) => item !== null) : [];
    const shipping = Array.isArray(order.shipping_methods) ? order.shipping_methods.map((value) => {
      if (!value || typeof value !== "object") return null;
      const method = value as Record<string, unknown>;
      return { name: typeof method.name === "string" ? method.name : "Delivery", total: typeof method.total === "number" || typeof method.total === "string" ? method.total : 0 };
    }).filter((method) => method !== null) : [];
    const amount = (key: string) => typeof order[key] === "number" || typeof order[key] === "string" ? order[key] : null;
    return privateReply({ order: {
      id,
      reference: typeof order.display_id === "number" ? order.display_id : null,
      created_at: typeof order.created_at === "string" ? order.created_at : null,
      currency_code: typeof order.currency_code === "string" ? order.currency_code : "ZAR",
      status: typeof order.status === "string" ? order.status : "pending",
      total: paidHistory?.total ?? amount("total"),
      subtotal: amount("subtotal"),
      shipping_total: amount("shipping_total"),
      tax_total: amount("tax_total"),
      refund_status: orderRefundStatus(order),
      items,
      shipping,
    } });
  } catch (error) {
    const status = error instanceof CustomerAuthError ? error.status : 503;
    return privateReply({ message: "Order details are temporarily unavailable" }, status);
  }
}
