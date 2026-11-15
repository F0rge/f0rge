import { afterEach, expect, it, vi } from "vitest";
import { readWorkspaceQuery } from "./record-workspace";
import { loadCatalogueSelection } from "./catalogue-workspace";

afterEach(() => vi.unstubAllGlobals());

it("keeps archived lifecycle and advanced filters when exporting across pages", async () => {
  const query = { ...readWorkspaceQuery(new URLSearchParams("lifecycle=archived")), filters: [{ field: "category", operator: "eq" as const, value: "Lighting" }] };
  const first = Array.from({ length: 100 }, (_, id) => ({ id: String(id) }));
  const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValueOnce(new Response(JSON.stringify({ items: first, total: 102 }))).mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: "100" }, { id: "101" }], total: 102 })));
  vi.stubGlobal("fetch", fetch);
  const selected = await loadCatalogueSelection(query, ["3", "101"]);
  expect(selected.map((item) => item.id)).toEqual(["3", "101"]);
  const requests = fetch.mock.calls.map(([, init]) => JSON.parse(String(init?.body)));
  expect(requests.map((request) => request.offset)).toEqual([0, 100]);
  for (const request of requests) expect(request).toMatchObject({ lifecycle: "archived", filters: query.filters, limit: 100 });
  expect(fetch.mock.calls.every(([url]) => String(url).endsWith("/record-workspaces/skus/query"))).toBe(true);
});

it("does not turn a failed later page into a partial export or label batch", async () => {
  const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValueOnce(new Response(JSON.stringify({ items: Array.from({ length: 100 }, (_, id) => ({ id: String(id) })), total: 101 }))).mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Catalogue unavailable" }), { status: 503 }));
  vi.stubGlobal("fetch", fetch);
  await expect(loadCatalogueSelection(readWorkspaceQuery(new URLSearchParams()))).rejects.toThrow("Catalogue unavailable");
});
