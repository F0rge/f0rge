import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const clerkState = vi.hoisted(() => ({ configured: vi.fn(), invoked: vi.fn() }));
vi.mock("@clerk/nextjs/server", () => ({
  clerkMiddleware: () => {
    clerkState.configured();
    return () => {
      clerkState.invoked();
      return Response.redirect("https://clerk.example/redirect");
    };
  },
}));

describe("Clerk and private-preview proxy composition", () => {
  const envNames = [
    "STOREFRONT_RUNTIME_KIND", "STOREFRONT_PRIVATE_PREVIEW",
    "STOREFRONT_PREVIEW_USERNAME", "STOREFRONT_PREVIEW_PASSWORD",
    "STOREFRONT_INDEXING_ENABLED", "RAILWAY_ENVIRONMENT_NAME", "NEXT_PUBLIC_BASE_URL",
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "CLERK_SECRET_KEY", "STOREFRONT_CLERK_JWT_TEMPLATE",
  ] as const;
  let saved: Record<string, string | undefined>;

  beforeEach(() => {
    saved = Object.fromEntries(envNames.map((name) => [name, process.env[name]]));
    process.env.STOREFRONT_RUNTIME_KIND = "hosted";
    delete process.env.STOREFRONT_PRIVATE_PREVIEW;
    process.env.STOREFRONT_PREVIEW_USERNAME = "preview-user";
    process.env.STOREFRONT_PREVIEW_PASSWORD = "test-preview-password-that-is-long-enough";
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = "pk_test_fake";
    process.env.CLERK_SECRET_KEY = "sk_test_fake";
    process.env.STOREFRONT_CLERK_JWT_TEMPLATE = "storefront_medusa";
    clerkState.configured.mockClear();
    clerkState.invoked.mockClear();
    vi.resetModules();
  });

  afterEach(() => {
    for (const [name, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  });

  it("denies anonymous traffic before Clerk can redirect or start a request", async () => {
    const { proxy } = await import("./proxy");
    const response = await proxy(new NextRequest("https://storefront.example/shop"), {} as never);
    expect(response.status).toBe(401);
    expect(response.headers.get("x-robots-tag")).toContain("noindex");
    expect(clerkState.invoked).not.toHaveBeenCalled();
  });

  it("keeps Clerk redirects private after the Basic gate has passed", async () => {
    const { proxy } = await import("./proxy");
    const authorization = `Basic ${Buffer.from("preview-user:test-preview-password-that-is-long-enough").toString("base64")}`;
    const response = await proxy(new NextRequest("https://storefront.example/account", { headers: { authorization } }), {} as never);
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe("https://clerk.example/redirect");
    expect(response.headers.get("x-robots-tag")).toContain("noindex");
    expect(response.headers.get("cache-control")).toBe("private, no-store, max-age=0");
    expect(clerkState.invoked).toHaveBeenCalledTimes(1);
  });

  it("skips Basic Auth when the private preview is off", async () => {
    process.env.STOREFRONT_PRIVATE_PREVIEW = "off";
    delete process.env.STOREFRONT_PREVIEW_USERNAME;
    delete process.env.STOREFRONT_PREVIEW_PASSWORD;
    const { proxy } = await import("./proxy");
    const response = await proxy(new NextRequest("https://storefront.example/"), {} as never);
    expect(response.status).not.toBe(401);
    expect(response.status).not.toBe(503);
    expect(await response.text()).not.toContain("Private preview access is unavailable.");
    expect(response.headers.get("x-robots-tag")).toContain("noindex");
    expect(clerkState.invoked).toHaveBeenCalledTimes(1);
  });

  it("still fail-closes hosted traffic when the private preview flag is unset", async () => {
    delete process.env.STOREFRONT_PREVIEW_USERNAME;
    delete process.env.STOREFRONT_PREVIEW_PASSWORD;
    const { proxy } = await import("./proxy");
    const response = await proxy(new NextRequest("https://storefront.example/"), {} as never);
    expect(response.status).toBe(503);
    expect(await response.text()).toContain("Private preview access is unavailable.");
    expect(response.headers.get("x-robots-tag")).toContain("noindex");
    expect(clerkState.invoked).not.toHaveBeenCalled();
  });

  it("leaves the health check open and noindex when the private preview is off", async () => {
    process.env.STOREFRONT_PRIVATE_PREVIEW = "off";
    delete process.env.STOREFRONT_PREVIEW_USERNAME;
    delete process.env.STOREFRONT_PREVIEW_PASSWORD;
    const { proxy } = await import("./proxy");
    const response = await proxy(new NextRequest("https://storefront.example/api/health"), {} as never);
    expect(response.status).toBe(200);
    expect(response.headers.get("x-robots-tag")).toContain("noindex");
    expect(clerkState.invoked).not.toHaveBeenCalled();
  });

  it("matches the Clerk handshake path after the API matcher", async () => {
    const { config } = await import("./proxy");
    const api = config.matcher.indexOf("/(api|trpc)(.*)");
    const clerk = config.matcher.indexOf("/__clerk/:path*");
    expect(api).toBeGreaterThanOrEqual(0);
    expect(clerk).toBe(api + 1);
    expect(config.matcher.filter((pattern) => pattern === "/__clerk/:path*")).toHaveLength(1);
  });

  it("indexes catalogue routes only when production indexing is explicitly enabled", async () => {
    process.env.STOREFRONT_PRIVATE_PREVIEW = "off";
    process.env.STOREFRONT_INDEXING_ENABLED = "true";
    process.env.RAILWAY_ENVIRONMENT_NAME = "production";
    process.env.NEXT_PUBLIC_BASE_URL = "https://collector.example";
    delete process.env.STOREFRONT_PREVIEW_USERNAME;
    delete process.env.STOREFRONT_PREVIEW_PASSWORD;
    const { proxy } = await import("./proxy");
    const shop = await proxy(new NextRequest("https://collector.example/shop"), {} as never);
    const account = await proxy(new NextRequest("https://collector.example/account"), {} as never);
    const checkout = await proxy(new NextRequest("https://collector.example/checkout"), {} as never);
    expect(shop.headers.get("x-robots-tag")).toBeNull();
    expect(account.headers.get("x-robots-tag")).toContain("noindex");
    expect(checkout.headers.get("x-robots-tag")).toContain("noindex");
  });

  it("marks account and order-confirmation pages private and non-indexable", async () => {
    const { proxy } = await import("./proxy");
    const authorization = `Basic ${Buffer.from("preview-user:test-preview-password-that-is-long-enough").toString("base64")}`;
    for (const path of ["/account", "/account/orders/order_safe", "/order/confirmation"]) {
      const response = await proxy(new NextRequest(`https://storefront.example${path}`, { headers: { authorization } }), {} as never);
      expect(response.headers.get("cache-control")).toBe("private, no-store, max-age=0");
      expect(response.headers.get("x-robots-tag")).toContain("noindex");
    }
  });
});
