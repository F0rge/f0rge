import { NextRequest, NextResponse } from "next/server";
import {
  currentCartId,
  currentEmailOrderAccess,
  currentOrderAccessToken,
  emailOrderAccessCookie,
  orderConfirmationResponse,
  signedEmailOrderAccess,
  storefrontOrderStatusResponse,
} from "@/lib/bag-server";
import { publishConfirmationOutcomes } from "@/lib/analytics/posthog-server";
import { isSameOrigin } from "@/lib/same-origin";

function reply(payload: unknown, status: number): NextResponse {
  const response = NextResponse.json(payload, { status });
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  response.headers.set("Vary", "Cookie");
  response.headers.set("Referrer-Policy", "no-referrer");
  return response;
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  try {
    const emailAccess = await currentEmailOrderAccess();
    if (emailAccess) {
      const { status, payload } = await storefrontOrderStatusResponse(emailAccess.orderId, emailAccess.token);
      if (status >= 200 && status < 300) {
        void publishConfirmationOutcomes({ headers: request.headers, orderId: emailAccess.orderId, payload }).catch(() => undefined);
      }
      return reply(payload, status);
    }
    const cartId = await currentCartId();
    const token = cartId ? await currentOrderAccessToken(cartId) : null;
    if (!cartId || !token) return reply({ message: "Order confirmation not found" }, 404);
    const { status, payload } = await orderConfirmationResponse(cartId, token);
    if (status >= 200 && status < 300) {
      void publishConfirmationOutcomes({ headers: request.headers, cartId, payload }).catch(() => undefined);
    }
    return reply(payload, status);
  } catch {
    return reply({ message: "Order confirmation is temporarily unavailable" }, 503);
  }
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (!isSameOrigin(request)) return reply({ message: "Invalid request origin" }, 403);
  let body: unknown;
  try { body = await request.json(); }
  catch { return reply({ message: "Order status not found" }, 404); }
  const values = body && typeof body === "object" ? body as Record<string, unknown> : {};
  const orderId = values.order_id;
  const token = values.access_token;
  if (typeof orderId !== "string" || !/^order_[A-Za-z0-9_-]+$/.test(orderId) ||
      typeof token !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(token)) {
    return reply({ message: "Order status not found" }, 404);
  }
  try {
    const { status, payload } = await storefrontOrderStatusResponse(orderId, token);
    if (status >= 200 && status < 300) {
      void publishConfirmationOutcomes({ headers: request.headers, orderId, payload }).catch(() => undefined);
    }
    const response = reply(payload, status);
    if (status >= 200 && status < 300) {
      response.cookies.set(emailOrderAccessCookie, signedEmailOrderAccess(orderId, token), {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "strict",
        path: "/api/order/confirmation",
        maxAge: 60 * 60 * 24 * 60,
      });
    }
    return response;
  } catch {
    return reply({ message: "Order confirmation is temporarily unavailable" }, 503);
  }
}
