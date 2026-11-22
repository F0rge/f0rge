import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { analyticsEnvironment } from "./policy";

describe("server analytics environment", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_STOREFRONT_ANALYTICS_ENV", undefined);
    vi.stubEnv("STOREFRONT_RUNTIME_KIND", undefined);
    vi.stubEnv("RAILWAY_PROJECT_NAME", undefined);
    vi.stubEnv("RAILWAY_ENVIRONMENT_NAME", undefined);
    vi.stubEnv("RAILWAY_SERVICE_NAME", undefined);
  });

  afterEach(() => vi.unstubAllEnvs());

  it("defaults to test without deployment or configuration metadata", () => {
    expect(analyticsEnvironment()).toBe("test");
  });

  it.each(["NEXT_PUBLIC_STOREFRONT_ANALYTICS_ENV", "STOREFRONT_RUNTIME_KIND"])(
    "honors an explicit production value in %s",
    (name) => {
      vi.stubEnv(name, "production");
      expect(analyticsEnvironment()).toBe("production");
    },
  );

  describe("on Railway", () => {
    beforeEach(() => {
      vi.stubEnv("RAILWAY_PROJECT_NAME", "DasKasas");
      vi.stubEnv("RAILWAY_ENVIRONMENT_NAME", "production");
      vi.stubEnv("RAILWAY_SERVICE_NAME", "storefront");
    });

    it("marks the DasKasas production storefront as production", () => {
      expect(analyticsEnvironment()).toBe("production");
    });

    it.each([
      ["RAILWAY_PROJECT_NAME", "Preview"],
      ["RAILWAY_ENVIRONMENT_NAME", "staging"],
      ["RAILWAY_SERVICE_NAME", "storefront-commerce"],
    ])("keeps traffic classified as test when %s differs", (name, value) => {
      vi.stubEnv(name, value);
      expect(analyticsEnvironment()).toBe("test");
    });

    it("honors an explicit test label even in production", () => {
      vi.stubEnv("NEXT_PUBLIC_STOREFRONT_ANALYTICS_ENV", "test");
      vi.stubEnv("STOREFRONT_RUNTIME_KIND", "production");
      expect(analyticsEnvironment()).toBe("test");
    });
  });
});
