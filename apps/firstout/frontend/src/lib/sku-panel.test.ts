import { describe, expect, it } from "vitest";
import {
  contextFor,
  keysBelongToTarget,
  readSkuPanel,
  skuPanelBack,
  skuPanelPageLabel,
  skuPanelPosition,
  skuPanelSearch,
  stepSkuId,
  withSkuPanelParams,
} from "./sku-panel";

const A = "11111111-1111-4111-8111-111111111111";
const B = "22222222-2222-4222-8222-222222222222";
const C = "33333333-3333-4333-8333-333333333333";
const page = "q=oslo&sort=name&direction=asc&size=25&page=2";

describe("SKU panel URL state", () => {
  it("reads closed, docked and full", () => {
    expect(readSkuPanel(new URLSearchParams(page))).toBeNull();
    expect(readSkuPanel(new URLSearchParams(`sku=${A}`))).toEqual({ id: A, view: "docked" });
    expect(readSkuPanel(new URLSearchParams(`sku=${A}&skuView=full`))).toEqual({ id: A, view: "full" });
    expect(readSkuPanel(new URLSearchParams(`skuView=full`))).toBeNull();
  });
  it("ignores ids that are not ids", () => {
    expect(readSkuPanel(new URLSearchParams("sku=<script>"))).toBeNull();
    expect(readSkuPanel(new URLSearchParams("sku="))).toBeNull();
  });
  it("opens, expands, collapses and closes without touching the page's own params", () => {
    const docked = skuPanelSearch(page, { id: A, view: "docked" });
    expect(new URLSearchParams(docked).get("page")).toBe("2");
    expect(new URLSearchParams(docked).get("sku")).toBe(A);
    expect(new URLSearchParams(docked).has("skuView")).toBe(false);
    const full = skuPanelSearch(docked, { id: A, view: "full" });
    expect(new URLSearchParams(full).get("skuView")).toBe("full");
    const back = skuPanelSearch(full, skuPanelBack({ id: A, view: "full" }));
    expect(back).toBe(docked);
    const closed = skuPanelSearch(back, skuPanelBack({ id: A, view: "docked" }));
    expect(closed).toBe(page);
  });
  it("carries the panel onto a query string a page rebuilt for itself", () => {
    const current = new URLSearchParams(`q=old&sku=${B}&skuView=full`);
    const next = withSkuPanelParams("q=new&page=1", current);
    expect(new URLSearchParams(next).get("q")).toBe("new");
    expect(readSkuPanel(new URLSearchParams(next))).toEqual({ id: B, view: "full" });
    expect(withSkuPanelParams("q=new", new URLSearchParams("q=old"))).toBe("q=new");
  });
  it("goes back one level at a time", () => {
    expect(skuPanelBack({ id: A, view: "full" })).toEqual({ id: A, view: "docked" });
    expect(skuPanelBack({ id: A, view: "docked" })).toBeNull();
    expect(skuPanelBack(null)).toBeNull();
  });
});

describe("SKU panel stepping", () => {
  const ids = [A, B, C];
  it("steps without wrapping", () => {
    expect(stepSkuId(ids, A, 1)).toBe(B);
    expect(stepSkuId(ids, C, 1)).toBeNull();
    expect(stepSkuId(ids, A, -1)).toBeNull();
    expect(stepSkuId(ids, "x", 1)).toBeNull();
  });
  it("names the position", () => {
    expect(skuPanelPosition({ ids, label: "oslo" }, B)).toBe("oslo · 2 of 3");
    expect(skuPanelPosition({ ids, label: "Catalogue" }, "x")).toBe("Catalogue · not in this list");
    expect(skuPanelPosition({ ids: [A], label: "" }, A)).toBe("1 of 1");
    expect(skuPanelPosition({ ids, label: "Catalogue" }, B, "Catalogue")).toBe("2 of 3");
    expect(skuPanelPosition({ ids, label: "alba" }, B, "Purchase orders")).toBe("alba · 2 of 3");
  });

  it("names the page the panel sits on", () => {
    expect(skuPanelPageLabel([{ label: "Catalogue management" }, { label: "Products" }])).toBe("Catalogue");
    expect(skuPanelPageLabel([{ label: "Stock" }, { label: "Purchase orders" }])).toBe("Purchase orders");
    expect(skuPanelPageLabel([])).toBe("Home");
  });
  it("always gives a context that contains the SKU", () => {
    expect(contextFor(A, { ids, label: "oslo", key: "search" })).toEqual({ ids, label: "oslo", key: "search" });
    expect(contextFor(A, null)).toEqual({ ids: [A], label: "", key: undefined });
    expect(contextFor("x", { ids, label: "oslo" }).ids).toEqual(["x"]);
  });
});

describe("keyboard ownership", () => {
  const el = (tagName: string, extra: Record<string, unknown> = {}) => ({ tagName, closest: () => null, ...extra });
  it("leaves typing fields and Carbon widgets alone", () => {
    expect(keysBelongToTarget(el("INPUT"))).toBe(true);
    expect(keysBelongToTarget(el("INPUT", { type: "number" }))).toBe(true);
    expect(keysBelongToTarget(el("TEXTAREA"))).toBe(true);
    expect(keysBelongToTarget(el("SELECT"))).toBe(true);
    expect(keysBelongToTarget(el("DIV", { isContentEditable: true }))).toBe(true);
    expect(keysBelongToTarget(el("BUTTON", { closest: (s: string) => (s.includes("[role=menu]") ? {} : null) }))).toBe(true);
  });
  it("lets buttons, checkboxes and the page body through", () => {
    expect(keysBelongToTarget(el("INPUT", { type: "checkbox" }))).toBe(false);
    expect(keysBelongToTarget(el("BUTTON"))).toBe(false);
    expect(keysBelongToTarget(el("BODY"))).toBe(false);
    expect(keysBelongToTarget(null)).toBe(false);
  });
});
