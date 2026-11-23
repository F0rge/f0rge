import { afterEach, expect, it, vi } from "vitest";

import { listSkus, listSkusPage, listSkuUnitCosts, previewSkuPrice } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("keeps supplier, search and category scope aligned for pages, costs and export", async () => {
  const fetch = vi.fn<typeof globalThis.fetch>(
    async () =>
      new Response(JSON.stringify({ items: [], total: 0, categories: [] })),
  );
  vi.stubGlobal("fetch", fetch);
  const filters = {
    lifecycle: "archived" as const,
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
    expect(url.searchParams.get("lifecycle")).toBe("archived");
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

it("sends an explicit cleared tier to the SKU invoice preview", async () => {
  const result = {
    source: "retail_fallback",
    vat_rate: "0.1500",
    unit_ex_vat: "2000.00",
    subtotal_ex_vat: "4000.00",
    vat_amount: "600.00",
    total_inc_vat: "4600.00",
  };
  const fetch = vi.fn<typeof globalThis.fetch>(async () => new Response(JSON.stringify(result)));
  vi.stubGlobal("fetch", fetch);
  const signal = new AbortController().signal;

  await expect(previewSkuPrice("sku-1", {
    classification: "Stockist",
    quantity: 2,
    price_changes: { stockist_ex_vat: null },
  }, signal)).resolves.toEqual(result);

  expect(fetch).toHaveBeenCalledExactlyOnceWith("/api/v1/skus/sku-1/price-preview", expect.objectContaining({
    method: "POST",
    body: '{"classification":"Stockist","quantity":2,"price_changes":{"stockist_ex_vat":null}}',
    signal,
  }));
});
