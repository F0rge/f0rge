import type { NextRequest } from "next/server";

export function isSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return true;
  try {
    const url = new URL(origin);
    const host = request.headers.get("host");
    const protocol = request.headers.get("x-forwarded-proto") || request.nextUrl.protocol.slice(0, -1);
    return url.host === host && url.protocol === `${protocol}:`;
  } catch {
    return false;
  }
}
