import { describe, expect, it } from "vitest";

import {
  isAdminPath,
  isBooksPath,
  isCatalogueMenuPath,
  isNavLinkActive,
  isSalesPath,
  isStockPath,
  isWarehousePath,
  labelForNavPath,
} from "./nav";

describe("nav path helpers", () => {
  it("treats catalogue detail URLs as catalogue menu + active catalogue link", () => {
    expect(isCatalogueMenuPath("/catalogue")).toBe(true);
    expect(isCatalogueMenuPath("/catalogue/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")).toBe(true);
    expect(isNavLinkActive("/catalogue/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "/catalogue")).toBe(
      true,
    );
  });

  it("does not treat /stock as a stock-menu path after inventory list removal", () => {
    expect(isStockPath("/stock")).toBe(false);
    expect(isStockPath("/stocktakes")).toBe(true);
    expect(isStockPath("/adjustments")).toBe(true);
  });

  it("groups warehouse and sales paths", () => {
    expect(isWarehousePath("/purchase-orders")).toBe(true);
    expect(isWarehousePath("/purchase-orders/abc")).toBe(true);
    expect(isWarehousePath("/wms")).toBe(true);
    expect(isSalesPath("/quotes")).toBe(true);
    expect(isSalesPath("/orders")).toBe(true);
    expect(isSalesPath("/laybys")).toBe(true);
    expect(isSalesPath("/deliveries")).toBe(true);
    expect(isSalesPath("/customers/abc")).toBe(true);
  });

  it("groups admin and books paths", () => {
    expect(isAdminPath("/settings")).toBe(true);
    expect(isAdminPath("/users")).toBe(true);
    expect(isAdminPath("/audit")).toBe(true);
    expect(isBooksPath("/invoices/abc")).toBe(true);
    expect(isBooksPath("/ledger")).toBe(true);
    expect(isBooksPath("/books-periods")).toBe(true);
  });

  it("labels audit and books periods nav paths", () => {
    expect(labelForNavPath("/audit")).toBe("Audit");
    expect(labelForNavPath("/books-periods")).toBe("Books periods");
  });

  it("labels nested paths for Nia cards", () => {
    expect(labelForNavPath("/catalogue")).toBe("Catalogue");
    expect(labelForNavPath("/catalogue/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")).toBe("Catalogue");
    expect(labelForNavPath("/invoices/abc")).toBe("Invoices");
  });

  it("includes price lists in catalogue menu", () => {
    expect(isCatalogueMenuPath("/price-lists")).toBe(true);
    expect(labelForNavPath("/price-lists")).toBe("Price lists");
  });
});
