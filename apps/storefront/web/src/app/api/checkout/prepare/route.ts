import { NextRequest, NextResponse } from "next/server";
import {
  BagError,
  currentCartId,
  currentOrderAccessToken,
  medusaResponse,
  newOrderAccessToken,
  orderAccessCookie,
  signedOrderAccess,
} from "@/lib/bag-server";
import { isSameOrigin } from "@/lib/same-origin";

function reply(body: unknown, status: number): NextResponse {
  const response = NextResponse.json(body, { status });
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  return response;
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (!isSameOrigin(request)) return reply({ message: "Invalid request origin" }, 403);
  const cartId = await currentCartId();
  if (!cartId) return reply({ message: "Bag not found" }, 404);
  let body: unknown;
  try { body = await request.json(); }
  catch { return reply({ message: "Enter your checkout details" }, 400); }
  const token = await currentOrderAccessToken(cartId) || newOrderAccessToken();
  try {
    const { status, payload } = await medusaResponse<{ checkout?: Record<string, unknown>; message?: string; changes?: string[] }>(
      "/store/carts/" + encodeURIComponent(cartId) + "/storefront-checkout", "POST", {
        ...(body && typeof body === "object" ? body as Record<string, unknown> : {}),
        confirmation_token: token,
      },
    );
    const result = reply(status >= 200 && status < 300 ? { checkout: payload.checkout } : { message: payload.message || "Checkout could not be prepared", changes: payload.changes }, status);
    result.cookies.set(orderAccessCookie, signedOrderAccess(cartId, token), {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      path: "/",
      maxAge: 60 * 60 * 24 * 60,
    });
    return result;
  } catch (error) {
    const status = error instanceof BagError && error.status < 500 ? error.status : 503;
    const result = reply({ message: error instanceof Error ? error.message : "Checkout could not be prepared" }, status);
    result.cookies.set(orderAccessCookie, signedOrderAccess(cartId, token), {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      path: "/",
      maxAge: 60 * 60 * 24 * 60,
    });
    return result;
  }
}
