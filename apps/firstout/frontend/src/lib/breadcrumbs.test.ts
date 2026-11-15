import { describe, expect, it } from "vitest";
import { breadcrumbsForPath } from "./breadcrumbs";
import {
  ADMIN_NAV_ITEMS,
  BOOKS_NAV_ITEMS,
  CATALOGUE_NAV_ITEMS,
  SALES_NAV_ITEMS,
  STOCK_NAV_ITEMS,
  WAREHOUSE_NAV_ITEMS,
} from "./nav";

describe("application breadcrumbs", () => {
  it("omits top-level and public screens", () => {
    for (const path of [
      "/",
      "/till",
      "/till/",
      "/clerk-login",
      "/trade/catalogue",
      "/onboarding",
    ]) {
      expect(breadcrumbsForPath(path)).toEqual([]);
    }
  });
  it("covers every grouped staff screen without fake category links", () => {
    for (const item of [
      ...ADMIN_NAV_ITEMS,
      ...BOOKS_NAV_ITEMS,
      ...CATALOGUE_NAV_ITEMS,
      ...SALES_NAV_ITEMS,
      ...STOCK_NAV_ITEMS,
      ...WAREHOUSE_NAV_ITEMS,
    ]) {
      const crumbs = breadcrumbsForPath(item.href);
      expect(crumbs).toHaveLength(2);
      expect(crumbs.every((crumb) => crumb.href === undefined)).toBe(true);
    }
  });
  it("links actual detail ancestors and keeps opaque identifiers out of labels", () => {
    expect(breadcrumbsForPath("/purchase-orders/opaque-id")).toEqual([
      { label: "Warehouse" },
      { label: "Purchase orders", href: "/purchase-orders" },
      { label: "Purchase order" },
    ]);
    expect(breadcrumbsForPath("/catalogue/new").at(-1)?.label).toBe(
      "Create product",
    );
    expect(breadcrumbsForPath("/bills/read").at(-1)?.label).toBe(
      "Read document",
    );
    expect(breadcrumbsForPath("/catalogue-wrong")).toEqual([]);
  });
});
