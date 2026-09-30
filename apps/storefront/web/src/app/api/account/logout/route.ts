import { NextRequest, NextResponse } from "next/server";
import { cartCookie, emailOrderAccessCookie, orderAccessCookie } from "@/lib/bag-server";
import { isSameOrigin } from "@/lib/same-origin";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const sameOrigin = isSameOrigin(request);
  const response = NextResponse.json(sameOrigin ? { ok: true } : { message: "Invalid request origin" }, { status: sameOrigin ? 200 : 403 });
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  response.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
  if (!sameOrigin) return response;
  for (const name of [cartCookie, orderAccessCookie, emailOrderAccessCookie]) {
    response.cookies.set(name, "", {
      httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0,
    });
  }
  return response;
}
