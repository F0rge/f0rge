import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { GET } from "./route";

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_BASE_URL", "https://www.daskasas.co.za");
  vi.stubEnv("RAILWAY_ENVIRONMENT_NAME", "production");
  vi.stubEnv("STOREFRONT_INDEXING_ENABLED", "true");
  vi.stubEnv("STOREFRONT_PRIVATE_PREVIEW", "off");
});

afterEach(() => vi.unstubAllEnvs());

it("publishes a plain-text guide to the public shop and policies", async () => {
  const response = GET();
  expect(response.status).toBe(200);
  expect(response.headers.get("content-type")).toBe("text/plain; charset=utf-8");
  const text = await response.text();
  expect(text).toMatch(/^# DasKasas\n/);
  expect(text).toContain("Shop GL15, Bedford Square");
  expect(text).toContain("[Sofas & Armchairs](https://www.daskasas.co.za/shop/sofas-armchairs)");
  expect(text).toContain("[Return policy](https://www.daskasas.co.za/policies/returns)");
});

it("does not serve the guide with indexing disabled", async () => {
  vi.stubEnv("STOREFRONT_INDEXING_ENABLED", "false");
  const response = GET();
  expect(response.status).toBe(404);
  expect(response.headers.get("cache-control")).toBe("no-store");
  expect(await response.text()).toBe("");
});
