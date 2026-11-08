import { NextRequest } from "next/server";
import { NextFetchEvent } from "next/dist/server/web/spec-extension/fetch-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { clerkDispatch } = vi.hoisted(() => ({
  clerkDispatch: vi.fn(() => new Response(null, { status: 204 })),
}));

vi.mock("@clerk/nextjs/server", () => ({ clerkMiddleware: () => clerkDispatch }));

import proxy from "./proxy";

async function request(path: string, host: string, method = "GET") {
  const incoming = new NextRequest(`http://${host}${path}`, { method, headers: { host } });
  const event = new NextFetchEvent({ request: incoming, page: "/", context: undefined });
  const response = await proxy(incoming, event);
  if (!response) throw new Error("Expected the proxy to return a response");
  return response;
}

beforeEach(() => {
  vi.stubEnv("NODE_ENV", "production");
  vi.stubEnv("FIRSTOUT_ALLOW_LOCAL_HOSTS", "false");
  vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "pk_test_liveness_probe");
  clerkDispatch.mockClear();
});
afterEach(() => vi.unstubAllEnvs());

describe("frontend deployment liveness", () => {
  it("answers the Railway probe without invoking Clerk or returning tenant data", async () => {
    const response = await request("/healthz", "healthcheck.railway.app");
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "ok" });
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(response.headers.get("Set-Cookie")).toBeNull();
    expect(clerkDispatch).not.toHaveBeenCalled();
  });

  it.each(["/", "/catalogue", "/api/v1/auth/me", "/healthz/details", "/healthz-extra"])(
    "continues rejecting unknown hosts at %s", async (path) => {
      const response = await request(path, "unknown.example");
      expect(response.status).toBe(404);
      expect(await response.text()).toBe("Unknown host");
      expect(clerkDispatch).not.toHaveBeenCalled();
    },
  );

  it("does not bypass the host guard for non-GET probes", async () => {
    expect((await request("/healthz", "healthcheck.railway.app", "POST")).status).toBe(404);
    expect(clerkDispatch).not.toHaveBeenCalled();
  });

  it("preserves the authenticated application path for known hosts", async () => {
    const response = await request("/", "app.firstout.co.za");
    expect(response.status).toBe(204);
    expect(clerkDispatch).toHaveBeenCalledOnce();
  });
});
