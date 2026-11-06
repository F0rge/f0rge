import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextRequest, NextResponse, type NextFetchEvent } from "next/server";
import { frontendHeaders } from "./lib/frontend-headers";

function forward(request: NextRequest) {
  const headers = frontendHeaders(
    request.headers,
    process.env.NODE_ENV !== "production" ||
      process.env.FIRSTOUT_ALLOW_LOCAL_HOSTS === "true",
    process.env.FRONTEND_PROXY_SECRET,
  );
  if (!headers) return new NextResponse("Unknown host", { status: 404 });
  return NextResponse.next({ request: { headers } });
}
// No protect(): legacy staff and trade cookies remain valid during dual-auth.
const withClerk = clerkMiddleware((_auth, request) => forward(request));
export default function proxy(request: NextRequest, event: NextFetchEvent) {
  if (
    !frontendHeaders(
      request.headers,
      process.env.NODE_ENV !== "production" ||
        process.env.FIRSTOUT_ALLOW_LOCAL_HOSTS === "true",
    )
  ) {
    return new NextResponse("Unknown host", { status: 404 });
  }
  if (
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY &&
    !request.nextUrl.pathname.startsWith("/trade") &&
    !request.nextUrl.pathname.startsWith("/api/v1/portal")
  ) {
    return withClerk(request, event);
  }
  return forward(request);
}
export const config = {
  matcher: [
    "/((?!_next|.*\\.(?:png|jpg|jpeg|gif|svg|ico|css|js|woff2?)$).*)",
    "/api/:path*",
  ],
};
