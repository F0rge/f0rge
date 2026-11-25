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

function paymentReply(body: unknown, status: number, cartId: string, token?: string): NextResponse {
  const response = reply(body, status);
  if (token) response.cookies.set(orderAccessCookie, signedOrderAccess(cartId, token), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 60 * 60 * 24 * 60,
  });
  return response;
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (!isSameOrigin(request)) return reply({ message: "Invalid request origin" }, 403);
  const cartId = await currentCartId();
  if (!cartId) return reply({ message: "Bag not found" }, 404);
  let body: unknown;
  try { body = await request.json(); }
  catch { return reply({ message: "Enter your checkout details" }, 400); }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return reply({ message: "Enter your checkout details" }, 400);
  }
  const input = body as Record<string, unknown>;
  if (input.step !== undefined && input.step !== "review" && input.step !== "payment") {
    return reply({ message: "Review your order before continuing to payment" }, 400);
  }
  const existingToken = await currentOrderAccessToken(cartId);
  // Old clients may still resume a session. Commerce requires a review for any new attempt.
  const paymentToken = input.step === "review" ? undefined : existingToken || newOrderAccessToken();
  try {
    const { status, payload } = await medusaResponse<{ quote?: unknown; checkout?: unknown; message?: string; code?: string; changes?: string[] }>(
      "/store/carts/" + encodeURIComponent(cartId) + "/storefront-checkout", "POST", {
        ...input,
        confirmation_token: paymentToken ?? existingToken ?? undefined,
      },
    );
    if (status >= 200 && status < 300) {
      return paymentReply(input.step === "review" ? { quote: payload.quote } : { checkout: payload.checkout }, status, cartId, paymentToken);
    }
    return paymentReply({ message: payload.message || "Checkout could not be prepared", code: payload.code, changes: payload.changes }, status, cartId, paymentToken);
  } catch (error) {
    const status = error instanceof BagError && error.status < 500 ? error.status : 503;
    return paymentReply({ message: error instanceof Error ? error.message : "Checkout could not be prepared" }, status, cartId, paymentToken);
  }
}
