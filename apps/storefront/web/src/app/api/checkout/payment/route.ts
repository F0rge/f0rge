import { randomUUID } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { publishPaymentFailure } from "@/lib/analytics/posthog-server";
import { currentCartId, medusaResponse } from "@/lib/bag-server";
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
  const body = await request.json().catch(() => null) as Record<string, unknown> | null;
  const sessionId = body?.session_id;
  const outcome = body?.outcome;
  const eventId = typeof body?.event_id === "string" ? body.event_id : randomUUID();
  if (typeof sessionId !== "string" || !/^payses_[A-Za-z0-9_-]+$/.test(sessionId) ||
    !["success", "pending", "declined", "cancelled", "unknown"].includes(String(outcome)) ||
    !/^[A-Za-z0-9_-]{8,128}$/.test(eventId)) {
    return reply({ message: "The test payment action is invalid" }, 400);
  }
  try {
    const { status, payload } = await medusaResponse<{ payment?: { status?: string; duplicate?: boolean }; message?: string }>(
      "/store/carts/" + encodeURIComponent(cartId) + "/storefront-test-payment", "POST", {
        session_id: sessionId,
        outcome,
        event_id: eventId,
      },
    );
    if (status < 200 || status >= 300) return reply({ message: payload.message || "Payment status could not be updated" }, status);
    void publishPaymentFailure({ headers: request.headers, cartId, outcome }).catch(() => undefined);
    return reply({ payment: { status: payload.payment?.status, duplicate: payload.payment?.duplicate === true } }, status);
  } catch (error) {
    return reply({ message: error instanceof Error ? error.message : "Payment status is unknown" }, 503);
  }
}
