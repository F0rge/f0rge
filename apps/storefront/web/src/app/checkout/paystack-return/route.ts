import { NextRequest, NextResponse } from "next/server";

/** Paystack returns the shopper here with ?reference=&trxref=; only the signed webhook and verify job update payment state. */
export function GET(request: NextRequest): NextResponse {
  return NextResponse.redirect(new URL("/order/confirmation", request.url), 303);
}
