import { afterEach, describe, expect, it, vi } from "vitest";

import {
  changeSupplierCodeSku,
  displayFabric,
  editSupplierCode,
  lookupManufacturerCode,
  prefillSupplierCode,
  type SupplierCodeLine,
  manufacturerCode,
} from "./po-supplier-code";

describe("PO supplier code prefill", () => {
  it("prefers the per-supplier factory code over the SKU supplier ref", () => {
    expect(manufacturerCode("DC-23-11G", "GENERIC-REF")).toBe("DC-23-11G");
  });

  it("falls back to the SKU supplier ref when that supplier has no code", () => {
    expect(manufacturerCode(null, "DC-23-11G")).toBe("DC-23-11G");
    expect(manufacturerCode("   ", "TOP-OAK")).toBe("TOP-OAK");
    expect(manufacturerCode(null, null)).toBe("");
  });


});

describe("PO fabric column", () => {
  it("shows the SKU fabric or finish", () => {
    expect(displayFabric("Belgian linen")).toBe("Belgian linen");
    expect(displayFabric("  Oak veneer  ")).toBe("Oak veneer");
  });

  it("hides the placeholder dash and blank fabric", () => {
    expect(displayFabric("-")).toBeNull();
    expect(displayFabric(" - ")).toBeNull();
    expect(displayFabric("")).toBeNull();
    expect(displayFabric(null)).toBeNull();
    expect(displayFabric(undefined)).toBeNull();
  });
});

const skuA = { id: "sku-a", supplier_ref: "GENERIC-A" };
const skuB = { id: "sku-b", supplier_ref: "GENERIC-B" };
const row = (key: string): SupplierCodeLine => ({ key, sku_id: skuA.id, supplier_code: "", supplierCodeTouched: false });

/** HTTP is the boundary; selections and completion updates use the actual form operations. */
function form(initial = [row("line-a")]) {
  let lines = initial;
  const requests: Array<{ url: URL; respond(code: string | null, status?: number): void }> = [];
  vi.stubGlobal("fetch", vi.fn((path: string) => new Promise<Response>((resolve) => {
    const url = new URL(path, "http://localhost:3003");
    requests.push({ url, respond(code, status = 200) {
      resolve(new Response(JSON.stringify(status === 200 ? {
        items: code === null ? [] : [{ supplier_id: url.searchParams.get("supplier_id"), sku_id: url.searchParams.get("sku_id"), supplier_sku: code }],
        total: code === null ? 0 : 1,
      } : { detail: "Supplier lookup unavailable" }), { status }));
    } });
  })));
  const update = (change: (current: SupplierCodeLine[]) => SupplierCodeLine[]) => { lines = change(lines); };
  return {
    get lines() { return lines; }, requests, update,
    select(key: string, sku = skuA) {
      update((current) => current.map((line) => line.key === key ? changeSupplierCodeSku(line, sku.id) : line));
    },
    lookup(key: string, supplier = "supplier-a", sku = skuA) { return prefillSupplierCode(update, key, supplier, sku); },
  };
}

afterEach(() => { vi.unstubAllGlobals(); });

describe("PO supplier-code request lifecycle", () => {
  it("keeps supplier B's code when supplier A completes last", async () => {
    const draft = form();
    const a = draft.lookup("line-a");
    const b = draft.lookup("line-a", "supplier-b");
    draft.requests[1].respond("FACTORY-B"); await b;
    draft.requests[0].respond("FACTORY-A"); await a;
    expect(draft.lines[0].supplier_code).toBe("FACTORY-B");
    expect(draft.lines[0].supplierCodeLookup).toBeUndefined();
  });

  it("does not revive the first request after supplier A → B → A", async () => {
    const draft = form();
    const firstA = draft.lookup("line-a");
    const b = draft.lookup("line-a", "supplier-b");
    const latestA = draft.lookup("line-a");
    draft.requests[2].respond("LATEST-A"); await latestA;
    draft.requests[1].respond("FACTORY-B"); await b;
    draft.requests[0].respond("OUTDATED-A"); await firstA;
    expect(draft.lines[0].supplier_code).toBe("LATEST-A");
  });

  it("rejects an old SKU request even when that SKU is selected again", async () => {
    const draft = form();
    const firstA = draft.lookup("line-a");
    draft.select("line-a", skuB);
    const b = draft.lookup("line-a", "supplier-a", skuB);
    draft.select("line-a");
    const latestA = draft.lookup("line-a");
    draft.requests[2].respond("LATEST-A"); await latestA;
    draft.requests[0].respond("OUTDATED-A"); await firstA;
    draft.requests[1].respond("FACTORY-B"); await b;
    expect(draft.lines[0].supplier_code).toBe("LATEST-A");
  });

  it("does not apply initial pending-order prefill after its SKU was replaced", async () => {
    const draft = form();
    const initial = draft.lookup("line-a");
    draft.select("line-a", skuB);
    const replacement = draft.lookup("line-a", "supplier-a", skuB);
    draft.requests[0].respond("FACTORY-A"); await initial;
    expect(draft.lines[0].supplier_code).toBe("");
    expect(draft.lines[0].supplierCodeLookup?.status).toBe("loading");
    draft.requests[1].respond("FACTORY-B"); await replacement;
    expect(draft.lines[0].supplier_code).toBe("FACTORY-B");
  });

  it("keeps duplicate SKU rows independent after deleting and reindexing a row", async () => {
    const draft = form([row("removed"), row("retained"), row("other")]);
    const removed = draft.lookup("removed");
    const retained = draft.lookup("retained");
    const other = draft.lookup("other", "supplier-a", skuB);
    draft.update((lines) => lines.filter((line) => line.key !== "removed").map((line) =>
      line.key === "other" ? changeSupplierCodeSku(line, skuB.id) : line));
    // Start a lookup matching the now-selected SKU; the first one had no matching row.
    const selectedOther = draft.lookup("other", "supplier-a", skuB);
    draft.requests[0].respond("REMOVED"); await removed;
    draft.requests[3].respond("OTHER"); await selectedOther;
    draft.requests[1].respond("RETAINED"); await retained;
    draft.requests[2].respond("OUTDATED-OTHER"); await other;
    expect(draft.lines.map((line) => [line.key, line.supplier_code])).toEqual([["retained", "RETAINED"], ["other", "OTHER"]]);
  });

  it.each(["MANUAL", ""])("retains a deliberate edit %j while a request is in flight", async (value) => {
    const draft = form();
    const pending = draft.lookup("line-a");
    draft.update((lines) => lines.map((line) => editSupplierCode(line, value)));
    draft.requests[0].respond("AUTOMATIC"); await pending;
    expect(draft.lines[0].supplier_code).toBe(value);
    expect(draft.lines[0].supplierCodeLookup).toBeUndefined();
  });

  it("preserves a persisted/manual code when its SKU changes", async () => {
    const draft = form([{ ...row("line-a"), supplier_code: "SAVED", supplierCodeTouched: true }]);
    draft.select("line-a", skuB);
    const pending = draft.lookup("line-a", "supplier-a", skuB);
    draft.requests[0].respond("AUTOMATIC"); await pending;
    expect(draft.lines[0].supplier_code).toBe("SAVED");
  });

  it("reports failed lookup without substituting the generic reference, then allows retry", async () => {
    const draft = form();
    const failed = draft.lookup("line-a");
    draft.requests[0].respond(null, 503); await failed;
    expect(draft.lines[0].supplier_code).toBe("");
    expect(draft.lines[0].supplierCodeLookup?.status).toBe("error");
    expect(draft.lines[0].supplierCodeLookup?.error).toContain("Retry");
    const retry = draft.lookup("line-a");
    draft.requests[1].respond("RECOVERED"); await retry;
    expect(draft.lines[0].supplier_code).toBe("RECOVERED");
    expect(draft.lines[0].supplierCodeLookup).toBeUndefined();
  });

  it("ignores an obsolete supplier failure after the current lookup succeeds", async () => {
    const draft = form();
    const a = draft.lookup("line-a");
    const b = draft.lookup("line-a", "supplier-b");
    draft.requests[1].respond("FACTORY-B"); await b;
    draft.requests[0].respond(null, 503); await a;
    expect(draft.lines[0].supplier_code).toBe("FACTORY-B");
    expect(draft.lines[0].supplierCodeLookup).toBeUndefined();
  });

  it("uses the generic reference after a successful lookup with no supplier entry", async () => {
    const draft = form();
    const pending = draft.lookup("line-a");
    expect(draft.lines[0].supplierCodeLookup?.status).toBe("loading");
    draft.requests[0].respond(null); await pending;
    expect(draft.lines[0].supplier_code).toBe("GENERIC-A");
    expect(draft.lines[0].supplierCodeLookup).toBeUndefined();
    expect(draft.requests[0].url.searchParams.get("supplier_id")).toBe("supplier-a");
    expect(draft.requests[0].url.searchParams.get("sku_id")).toBe("sku-a");
  });

  it("shows an actionable error for a failed network request", async () => {
    const draft = form();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Network unavailable")));
    await draft.lookup("line-a");
    expect(draft.lines[0].supplier_code).toBe("");
    expect(draft.lines[0].supplierCodeLookup?.status).toBe("error");
    expect(draft.lines[0].supplierCodeLookup?.error).toContain("Retry");
  });

  it("does not turn an HTTP failure into missing supplier data", async () => {
    const draft = form();
    const pending = lookupManufacturerCode("supplier-a", skuA);
    draft.requests[0].respond(null, 503);
    await expect(pending).rejects.toMatchObject({ status: 503 });
  });
});
