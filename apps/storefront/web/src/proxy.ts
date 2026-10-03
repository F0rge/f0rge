import { createHash, timingSafeEqual } from "node:crypto";
import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse, type NextFetchEvent, type NextRequest } from "next/server";

const ROBOTS_HEADER = "noindex, nofollow, noarchive";

function withRobotsHeader(response: NextResponse): NextResponse {
  response.headers.set("X-Robots-Tag", ROBOTS_HEADER);
  return response;
}

function unavailable(): NextResponse {
  const response = new NextResponse("Private preview access is unavailable.", { status: 503 });
  response.headers.set("Cache-Control", "no-store");
  return withRobotsHeader(response);
}

function unauthorized(): NextResponse {
  const response = new NextResponse("Authentication required.", { status: 401 });
  response.headers.set("WWW-Authenticate", 'Basic realm="Storefront private preview", charset="UTF-8"');
  response.headers.set("Cache-Control", "no-store");
  return withRobotsHeader(response);
}

function digest(value: string): Buffer {
  return createHash("sha256").update(value, "utf8").digest();
}

function isConfiguredCredential(value: string | undefined): value is string {
  return typeof value === "string" && value.length > 0;
}

function isHostedRuntime(): boolean {
  return process.env.STOREFRONT_RUNTIME_KIND === "hosted" ||
    ["RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID"]
      .some((name) => Boolean(process.env[name]));
}

function isAuthorized(request: NextRequest, username: string, password: string): boolean {
  const authorization = request.headers.get("authorization") ?? "";
  const match = /^Basic\s+([A-Za-z0-9+/]+={0,2})$/i.exec(authorization);
  if (!match) return false;

  const encoded = match[1];
  const decoded = Buffer.from(encoded, "base64");
  if (decoded.toString("base64").replace(/=+$/, "") !== encoded.replace(/=+$/, "")) return false;

  const separator = decoded.indexOf(":");
  if (separator < 0) return false;

  const suppliedUsername = decoded.subarray(0, separator).toString("utf8");
  const suppliedPassword = decoded.subarray(separator + 1).toString("utf8");
  return timingSafeEqual(digest(suppliedUsername), digest(username)) &&
    timingSafeEqual(digest(suppliedPassword), digest(password));
}

function privatePreviewGate(request: NextRequest): NextResponse | null {
  // Railway's liveness probe receives no account or dependency information.
  if (request.nextUrl.pathname === "/api/health") return withRobotsHeader(NextResponse.next());

  // Preserve the existing local development workflow while hosted runtimes
  // fail closed even if NODE_ENV was accidentally set to development.
  if (process.env.NODE_ENV === "development" && !isHostedRuntime()) {
    return null;
  }

  const username = process.env.STOREFRONT_PREVIEW_USERNAME;
  const password = process.env.STOREFRONT_PREVIEW_PASSWORD;
  if (!isConfiguredCredential(username) || !isConfiguredCredential(password) ||
      password.length < 32 || username.includes(":")) {
    return unavailable();
  }

  if (!isAuthorized(request, username, password)) return unauthorized();
  return null;
}

function withNoIndex(result: Response | null | undefined | void, pathname = ""): NextResponse {
  const response = result || NextResponse.next();
  const headers = new Headers(response.headers);
  headers.set("X-Robots-Tag", ROBOTS_HEADER);
  if (/^\/(?:account(?:\/|$)|api\/account(?:\/|$)|order\/confirmation(?:\/|$))/.test(pathname)) {
    headers.set("Cache-Control", "private, no-store, max-age=0");
  } else if (response.status >= 300 || headers.has("Location")) headers.set("Cache-Control", "no-store");
  return new NextResponse(response.body, { status: response.status, statusText: response.statusText, headers });
}

const clerkConfigured = Boolean(
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY &&
  process.env.CLERK_SECRET_KEY &&
  process.env.STOREFRONT_CLERK_JWT_TEMPLATE,
);
const clerkProxy = clerkMiddleware(() => withRobotsHeader(NextResponse.next()), {
  publishableKey: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || "",
  secretKey: process.env.CLERK_SECRET_KEY || "",
});

export function proxy(request: NextRequest, event: NextFetchEvent) {
  // Check Basic Auth before Clerk. Clerk can answer redirect or handshake
  // requests before invoking its callback, which must never bypass this gate.
  const denied = privatePreviewGate(request);
  if (denied) return denied;
  if (!clerkConfigured) return withNoIndex(NextResponse.next(), request.nextUrl.pathname);
  return Promise.resolve(clerkProxy(request, event)).then((result) => withNoIndex(result, request.nextUrl.pathname));
}

export const config = {
  matcher: ["/:path*"],
};
