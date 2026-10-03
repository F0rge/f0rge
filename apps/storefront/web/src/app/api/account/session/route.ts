import { NextRequest, NextResponse } from "next/server";
import { currentCartId, medusaResponse, cartCookie, orderAccessCookie, signedCart } from "@/lib/bag-server";
import { CustomerAuthError, getCustomerContext } from "@/lib/customer-auth";
import { isSameOrigin } from "@/lib/same-origin";

export const dynamic = "force-dynamic";

function privateReply<T>(body: T, status = 200): NextResponse<T> {
  const response = NextResponse.json(body, { status });
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  response.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
  return response;
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (!isSameOrigin(request)) return privateReply({ message: "Invalid request origin" }, 403);
  try {
    const customer = await getCustomerContext();
    if (!customer) return privateReply({ message: "Sign in to access your customer account" }, 401);
    let cartAttached = false;
    const cartId = await currentCartId();
    if (cartId) {
      const attached = await medusaResponse<{ cart?: { id?: string } }>(`/store/carts/${cartId}/storefront-customer`, "POST", {});
      cartAttached = attached.status >= 200 && attached.status < 300;
      if (attached.status === 404) {
        const response = privateReply({
          customer: { id: customer.id, email: customer.email, first_name: customer.first_name, last_name: customer.last_name },
          cart_attached: false,
        });
        response.cookies.set(cartCookie, "", { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0 });
        response.cookies.set(orderAccessCookie, "", { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0 });
        return response;
      }
      if (!cartAttached) return privateReply({ message: "Your bag could not be linked to this account" }, 503);
    }
    const response = privateReply({
      customer: { id: customer.id, email: customer.email, first_name: customer.first_name, last_name: customer.last_name },
      cart_attached: cartAttached,
    });
    if (cartAttached && cartId) response.cookies.set(cartCookie, signedCart(cartId), {
      httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 30,
    });
    return response;
  } catch (error) {
    const status = error instanceof CustomerAuthError ? error.status : 503;
    return privateReply({ message: status === 401 ? "Sign in to access your customer account" : "Customer account is unavailable" }, status);
  }
}
