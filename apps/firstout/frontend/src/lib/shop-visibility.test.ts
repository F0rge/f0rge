import { afterEach, describe, expect, it, vi } from "vitest";

import { setSkuShopHidden } from "./shop-visibility";

afterEach(() => vi.unstubAllGlobals());

describe("Hide from shop switch", () => {
  it("PATCHes only storefront_hidden on the SKU, in either direction", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(
      async () => new Response(JSON.stringify({ id: "sku-1", storefront_hidden: true })),
    );
    vi.stubGlobal("fetch", fetch);

    await setSkuShopHidden("sku-1", true);
    await setSkuShopHidden("sku-1", false);

    expect(fetch).toHaveBeenCalledTimes(2);
    for (const [index, hidden] of [true, false].entries()) {
      const [url, init] = fetch.mock.calls[index];
      expect(new URL(String(url), "https://fixture.invalid").pathname).toBe("/api/v1/skus/sku-1");
      expect(init?.method).toBe("PATCH");
      expect(JSON.parse(String(init?.body))).toEqual({ storefront_hidden: hidden });
    }
  });
});
