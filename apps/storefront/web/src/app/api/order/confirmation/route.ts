import { NextResponse } from "next/server";
import { currentCartId, currentOrderAccessToken, orderConfirmationResponse } from "@/lib/bag-server";

export async function GET(): Promise<NextResponse> {
  const headers = { "Cache-Control": "private, no-store, max-age=0", Vary: "Cookie" };
  try {
    const cartId = await currentCartId();
    const token = cartId ? await currentOrderAccessToken(cartId) : null;
    if (!cartId || !token) return NextResponse.json({ message: "Order confirmation not found" }, { status: 404, headers });
    const { status, payload } = await orderConfirmationResponse(cartId, token);
    return NextResponse.json(payload, { status, headers });
  } catch {
    return NextResponse.json({ message: "Order confirmation is temporarily unavailable" }, { status: 503, headers });
  }
}
