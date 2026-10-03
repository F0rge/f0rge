import { NextRequest, NextResponse } from "next/server";

/** Peach posts shopper return data here; server notifications alone update payment state. */
export function GET(request: NextRequest): NextResponse {
  return NextResponse.redirect(new URL("/order/confirmation", request.url), 303);
}

export function POST(request: NextRequest): NextResponse {
  return NextResponse.redirect(new URL("/order/confirmation", request.url), 303);
}
