import { afterEach, expect, it, vi } from "vitest";

import { listSkus, listSkusPage, listSkuUnitCosts } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("keeps supplier, search and category scope aligned for pages, costs and export", async () => {
  const fetch = vi.fn<typeof globalThis.fetch>(
    async () =>
      new Response(JSON.stringify({ items: [], total: 0, categories: [] })),
  );
  vi.stubGlobal("fetch", fetch);
  const filters = {
    preferred_supplier_id: "c18472f1-36db-48fa-99ca-c0c540df31bd",
    q: "quilt & linen",
    category: "Rugs, Cushions & Linen",
  };
  await listSkusPage({ ...filters, limit: 100, offset: 100 });
  await listSkuUnitCosts({ ...filters, limit: 100, offset: 100 });
  await listSkus(filters);

  const urls = fetch.mock.calls.map(
    (call) => new URL(String(call[0]), "https://fixture.invalid"),
  );
  expect(urls.map((url) => url.pathname)).toEqual([
    "/api/v1/skus",
    "/api/v1/skus/unit-costs",
    "/api/v1/skus",
  ]);
  for (const url of urls) {
    expect(url.searchParams.get("preferred_supplier_id")).toBe(
      filters.preferred_supplier_id,
    );
    expect(url.searchParams.get("q")).toBe(filters.q);
    expect(url.searchParams.get("category")).toBe(filters.category);
  }
  expect(urls[0].searchParams.get("limit")).toBe("100");
  expect(urls[1].searchParams.get("offset")).toBe("100");
  expect(urls[2].searchParams.has("limit")).toBe(false);
  expect(urls[2].searchParams.has("offset")).toBe(false);
});
