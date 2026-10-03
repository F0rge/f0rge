import { NextResponse } from "next/server";
import { CustomerAuthError, customerMedusaFetch, getCustomerContext } from "@/lib/customer-auth";
import { paidOrderHistory } from "@/lib/order-history";

export const dynamic = "force-dynamic";

function privateReply<T>(body: T, status = 200): NextResponse<T> {
  const response = NextResponse.json(body, { status });
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  response.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
  return response;
}

function summary(value: unknown) {
  if (!value || typeof value !== "object") return null;
  const order = value as Record<string, unknown>;
  if (typeof order.id !== "string" || !/^order_[A-Za-z0-9_-]+$/.test(order.id)) return null;
  return {
    id: order.id,
    reference: typeof order.display_id === "number" ? order.display_id : null,
    created_at: typeof order.created_at === "string" ? order.created_at : null,
    currency_code: typeof order.currency_code === "string" ? order.currency_code : "ZAR",
    status: typeof order.status === "string" ? order.status : "pending",
    total: paidOrderHistory(order)?.total ?? (typeof order.total === "number" || typeof order.total === "string" ? order.total : null),
  };
}

export async function GET(request: Request): Promise<NextResponse> {
  const offsetValue = Number(new URL(request.url).searchParams.get("offset") || "0");
  const offset = Number.isInteger(offsetValue) && offsetValue >= 0 && offsetValue <= 1_000_000 ? offsetValue : 0;
  try {
    const customer = await getCustomerContext();
    if (!customer) return privateReply({ message: "Sign in to view your orders" }, 401);
    const [history, claimable] = await Promise.all([
      customerMedusaFetch(customer, `/store/orders?limit=50&offset=${offset}&fields=id,display_id,created_at,currency_code,status,total,metadata`),
      offset === 0 ? customerMedusaFetch(customer, "/store/orders/storefront-account/claimable") : Promise.resolve(null),
    ]);
    if (history.status < 200 || history.status >= 300 || (claimable && (claimable.status < 200 || claimable.status >= 300))) {
      return privateReply({ message: "Your orders are temporarily unavailable" }, history.status === 401 || claimable?.status === 401 ? 401 : 503);
    }
    const ownedRows = Array.isArray(history.payload.orders) ? history.payload.orders : [];
    const claimableRows = claimable && Array.isArray(claimable.payload.orders) ? claimable.payload.orders : [];
    const count = typeof history.payload.count === "number" ? history.payload.count : offset + ownedRows.length;
    return privateReply({
      orders: ownedRows.map(summary).filter((row): row is NonNullable<typeof row> => row !== null),
      claimable: claimableRows.map(summary).filter((row): row is NonNullable<typeof row> => row !== null),
      count,
      offset,
      hasMore: offset + ownedRows.length < count,
    });
  } catch (error) {
    const status = error instanceof CustomerAuthError ? error.status : 503;
    return privateReply({ message: "Your orders are temporarily unavailable" }, status);
  }
}
