import { NextRequest, NextResponse } from "next/server";
import { BagError, cartCookie, createCart, currentCartId, getCart, medusaRequest, publicBag, signedCart } from "@/lib/bag-server";
import { isSameOrigin } from "@/lib/same-origin";

type CartResponse = { cart?: Parameters<typeof publicBag>[0]; parent?: Parameters<typeof publicBag>[0] };

function reply(error: unknown): NextResponse {
  const status = error instanceof BagError && error.status < 500 ? error.status : 503;
  return NextResponse.json({ message: error instanceof Error ? error.message : "Bag unavailable" }, { status });
}

function invalidOrigin(request: NextRequest): NextResponse | null {
  return isSameOrigin(request) ? null : NextResponse.json({ message: "Invalid request origin" }, { status: 403 });
}

function hasActiveHold(hold: { status: string; expires_at: string } | null | undefined): boolean {
  return hold?.status === "active" && Date.parse(hold.expires_at) > Date.now();
}

async function activeCart(id: string | null) {
  if (!id) return null;
  try { return await getCart(id); }
  catch (error) {
    // Completed carts and stale ownership/access cannot be used for a new bag.
    // Preserve payment capabilities: they are independent of this cart cookie.
    if (error instanceof BagError && (error.status === 404 || error.status === 410)) return null;
    throw error;
  }
}

export async function GET() {
  try {
    const id = await currentCartId();
    return NextResponse.json(await activeCart(id) || publicBag());
  } catch (error) { return reply(error); }
}

export async function POST(request: NextRequest) {
  const denied = invalidOrigin(request);
  if (denied) return denied;
  try {
    const body: unknown = await request.json();
    const variantId = typeof body === "object" && body !== null && "variant_id" in body ? body.variant_id : null;
    const quantity = typeof body === "object" && body !== null && "quantity" in body ? body.quantity : 1;
    if (typeof variantId !== "string" || !/^variant_[A-Za-z0-9_-]+$/.test(variantId) ||
      !Number.isSafeInteger(quantity) || typeof quantity !== "number" || quantity < 1 || quantity > 99) {
      return NextResponse.json({ message: "Choose a valid item and quantity" }, { status: 400 });
    }
    const existingId = await currentCartId();
    const cart = await activeCart(existingId) || await createCart();
    if (!cart.id) throw new BagError(503, "Bag unavailable");
    if (hasActiveHold(cart.hold)) return NextResponse.json({ message: "Change bag to edit this reservation" }, { status: 409 });
    const { cart: updated } = await medusaRequest<CartResponse>(`/store/carts/${cart.id}/line-items`, "POST", { variant_id: variantId, quantity });
    const response = NextResponse.json(publicBag(updated));
    if (cart.id !== existingId) response.cookies.set(cartCookie, signedCart(cart.id), {
      httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 30,
    });
    return response;
  } catch (error) { return reply(error); }
}

export async function PATCH(request: NextRequest) {
  const denied = invalidOrigin(request);
  if (denied) return denied;
  try {
    const id = await currentCartId();
    if (!id) return NextResponse.json({ message: "Bag not found" }, { status: 404 });
    const body: unknown = await request.json();
    const itemId = typeof body === "object" && body !== null && "item_id" in body ? body.item_id : null;
    const quantity = typeof body === "object" && body !== null && "quantity" in body ? body.quantity : null;
    if (typeof itemId !== "string" || !/^cali_[A-Za-z0-9_-]+$/.test(itemId) ||
      typeof quantity !== "number" || !Number.isSafeInteger(quantity) || quantity < 1 || quantity > 99) {
      return NextResponse.json({ message: "Choose a quantity from 1 to 99" }, { status: 400 });
    }
    const bag = await getCart(id);
    if (!bag.items.some((item) => item.id === itemId)) return NextResponse.json({ message: "Item not found" }, { status: 404 });
    if (hasActiveHold(bag.hold)) return NextResponse.json({ message: "Change bag to edit this reservation" }, { status: 409 });
    const { cart } = await medusaRequest<CartResponse>(`/store/carts/${id}/line-items/${itemId}`, "POST", { quantity });
    return NextResponse.json(publicBag(cart));
  } catch (error) { return reply(error); }
}

export async function DELETE(request: NextRequest) {
  const denied = invalidOrigin(request);
  if (denied) return denied;
  try {
    const id = await currentCartId();
    if (!id) return NextResponse.json({ message: "Bag not found" }, { status: 404 });
    const itemId = request.nextUrl.searchParams.get("item_id");
    if (!itemId || !/^cali_[A-Za-z0-9_-]+$/.test(itemId)) return NextResponse.json({ message: "Item not found" }, { status: 400 });
    const bag = await getCart(id);
    if (!bag.items.some((item) => item.id === itemId)) return NextResponse.json({ message: "Item not found" }, { status: 404 });
    if (hasActiveHold(bag.hold)) return NextResponse.json({ message: "Change bag to edit this reservation" }, { status: 409 });
    const { parent } = await medusaRequest<CartResponse>(`/store/carts/${id}/line-items/${itemId}`, "DELETE");
    return NextResponse.json(publicBag(parent));
  } catch (error) { return reply(error); }
}
