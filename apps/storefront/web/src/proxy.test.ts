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
    "STOREFRONT_RUNTIME_KIND", "STOREFRONT_PREVIEW_USERNAME", "STOREFRONT_PREVIEW_PASSWORD",
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "CLERK_SECRET_KEY", "STOREFRONT_CLERK_JWT_TEMPLATE",
  ] as const;
  let saved: Record<string, string | undefined>;

  beforeEach(() => {
    saved = Object.fromEntries(envNames.map((name) => [name, process.env[name]]));
    process.env.STOREFRONT_RUNTIME_KIND = "hosted";
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
