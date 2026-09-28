import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse, type NextRequest } from "next/server";

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

export function proxy(request: NextRequest): NextResponse {
  const response = () => withRobotsHeader(NextResponse.next());

  // Railway's liveness probe receives no account or dependency information.
  if (request.nextUrl.pathname === "/api/health") return response();

  // Preserve the existing local development workflow while hosted runtimes
  // fail closed even if NODE_ENV was accidentally set to development.
  if (process.env.NODE_ENV === "development" && !isHostedRuntime()) {
    return response();
  }

  const username = process.env.STOREFRONT_PREVIEW_USERNAME;
  const password = process.env.STOREFRONT_PREVIEW_PASSWORD;
  if (!isConfiguredCredential(username) || !isConfiguredCredential(password) ||
      password.length < 32 || username.includes(":")) {
    return unavailable();
  }

  if (!isAuthorized(request, username, password)) return unauthorized();
  return response();
}

export const config = {
  matcher: ["/:path*"],
};
