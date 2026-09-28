import { NextRequest, NextResponse } from "next/server";
import { BagError, currentCartId, getCart, medusaResponse, type Bag } from "@/lib/bag-server";
import { isSameOrigin } from "@/lib/same-origin";

type Hold = NonNullable<Bag["hold"]>;

function rejectedOrigin(request: NextRequest): NextResponse | null {
  return isSameOrigin(request) ? null : NextResponse.json({ message: "Invalid request origin" }, { status: 403 });
}

async function changeHold(request: NextRequest, method: "POST" | "DELETE"): Promise<NextResponse> {
  const denied = rejectedOrigin(request);
  if (denied) return denied;
  const cartId = await currentCartId();
  if (!cartId) return NextResponse.json({ message: "Bag not found" }, { status: 404 });
  try {
    const { status, payload } = await medusaResponse<{ hold?: Hold }>(`/store/carts/${cartId}/checkout-hold`, method);
    if ((status < 200 || status >= 300) && !(status === 409 && payload.hold?.status === "review")) {
      throw new BagError(status, payload.message || "Checkout is temporarily unavailable");
    }
    return NextResponse.json({ ...await getCart(cartId), hold: payload.hold || null });
  } catch (error) {
    const status = error instanceof BagError && error.status < 500 ? error.status : 503;
    return NextResponse.json({ message: error instanceof Error ? error.message : "Checkout is temporarily unavailable" }, { status });
  }
}

export async function POST(request: NextRequest): Promise<NextResponse> { return changeHold(request, "POST"); }
export async function DELETE(request: NextRequest): Promise<NextResponse> { return changeHold(request, "DELETE"); }
