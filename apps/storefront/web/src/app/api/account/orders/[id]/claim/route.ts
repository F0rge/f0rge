import { NextRequest, NextResponse } from "next/server";
import { CustomerAuthError, customerMedusaFetch, getCustomerContext } from "@/lib/customer-auth";
import { isSameOrigin } from "@/lib/same-origin";

export const dynamic = "force-dynamic";

type Context = { params: Promise<{ id: string }> };
const validId = (id: string) => /^order_[A-Za-z0-9_-]+$/.test(id);

function privateReply<T>(body: T, status = 200): NextResponse<T> {
  const response = NextResponse.json(body, { status });
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  response.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
  return response;
}

export async function POST(request: NextRequest, { params }: Context): Promise<NextResponse> {
  if (!isSameOrigin(request)) return privateReply({ message: "Invalid request origin" }, 403);
  const { id } = await params;
  if (!validId(id)) return privateReply({ message: "Order not found" }, 404);
  try {
    const customer = await getCustomerContext();
    if (!customer) return privateReply({ message: "Sign in to link this order" }, 401);
    const { status, payload } = await customerMedusaFetch(customer, `/store/orders/storefront-account/${encodeURIComponent(id)}/claim`, "POST", {});
    if (status < 200 || status >= 300) return privateReply({ message: status === 401 ? "Sign in to link this order" : "This order is not available to link" }, status === 401 ? 401 : status === 503 ? 503 : 404);
    return privateReply({ claimed: payload.claimed === true, already_owned: payload.already_owned === true });
  } catch (error) {
    const status = error instanceof CustomerAuthError ? error.status : 503;
    return privateReply({ message: "This order could not be linked right now" }, status);
  }
}
