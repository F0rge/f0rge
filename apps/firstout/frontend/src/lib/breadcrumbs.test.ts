import { describe, expect, it } from "vitest";
import { ADMIN_DESTINATIONS, adminBreadcrumbs } from "./admin-navigation";
import { breadcrumbsForPath } from "./breadcrumbs";
import { NAV_GROUPS } from "./nav";

describe("application breadcrumbs", () => {
  it("omits top-level, public and Administration screens", () => {
    for (const path of ["/", "/till", "/till/", "/clerk-login", "/trade/catalogue", "/onboarding", "/reports", "/locations", "/import", "/history"]) {
      expect(breadcrumbsForPath(path)).toEqual([]);
    }
  });

  it("names the new group for every grouped screen, without fake group links", () => {
    for (const group of NAV_GROUPS.filter((item) => !item.link)) {
      for (const page of group.pages) {
        const [path, query] = page.href.split("?");
        const crumbs = breadcrumbsForPath(path, query);
        expect(crumbs).toHaveLength(2);
        expect(crumbs[0]).toEqual({ label: group.label });
        expect(crumbs.every((crumb) => crumb.href === undefined)).toBe(true);
      }
    }
  });

  it("follows the moved pages", () => {
    expect(breadcrumbsForPath("/catalogue")).toEqual([{ label: "Products" }, { label: "Catalogue" }]);
    expect(breadcrumbsForPath("/suppliers")).toEqual([{ label: "Buy" }, { label: "Suppliers" }]);
    expect(breadcrumbsForPath("/reorder")).toEqual([{ label: "Buy" }, { label: "Reorder" }]);
    expect(breadcrumbsForPath("/proformas")).toEqual([{ label: "Buy" }, { label: "Proformas" }]);
    expect(breadcrumbsForPath("/purchase-orders")).toEqual([{ label: "Buy" }, { label: "Purchase orders" }]);
    expect(breadcrumbsForPath("/deliveries")).toEqual([{ label: "Warehouse" }, { label: "Deliveries" }]);
    expect(breadcrumbsForPath("/stock")).toEqual([{ label: "Stock" }, { label: "Stock on hand" }]);
    expect(breadcrumbsForPath("/invoices")).toEqual([{ label: "Sell" }, { label: "Invoices" }]);
    expect(breadcrumbsForPath("/credit-notes")).toEqual([{ label: "Sell" }, { label: "Credit notes" }]);
    expect(breadcrumbsForPath("/commission")).toEqual([{ label: "Reports" }, { label: "Commission" }]);
  });

  it("follows the Reports section", () => {
    expect(breadcrumbsForPath("/reports", "section=sales")).toEqual([{ label: "Reports" }, { label: "Sales" }]);
    expect(breadcrumbsForPath("/reports", new URLSearchParams("section=books&tab=journals"))).toEqual([{ label: "Reports" }, { label: "Books" }]);
    expect(breadcrumbsForPath("/reports", "section=nope")).toEqual([]);
  });

  it("links actual detail ancestors and keeps opaque identifiers out of labels", () => {
    expect(breadcrumbsForPath("/purchase-orders/opaque-id")).toEqual([
      { label: "Buy" },
      { label: "Purchase orders", href: "/purchase-orders" },
      { label: "Purchase order" },
    ]);
    expect(breadcrumbsForPath("/catalogue/new").at(-1)?.label).toBe("Create product");
    expect(breadcrumbsForPath("/catalogue/curated")).toEqual([
      { label: "Products" },
      { label: "Catalogue", href: "/catalogue" },
      { label: "Product details" },
    ]);
    expect(breadcrumbsForPath("/quotes/new").at(-1)?.label).toBe("New quote");
    expect(breadcrumbsForPath("/quotes/opaque-id")).toEqual([
      { label: "Sell" },
      { label: "Quotes", href: "/quotes" },
      { label: "Quote" },
    ]);
    expect(breadcrumbsForPath("/proformas/read").at(-1)?.label).toBe("Read document");
    expect(breadcrumbsForPath("/bills/new").at(-1)?.label).toBe("Create bill");
    expect(breadcrumbsForPath("/invoices/new").at(-1)?.label).toBe("Create invoice");
    expect(breadcrumbsForPath("/catalogue-wrong")).toEqual([]);
    expect(breadcrumbsForPath("/stock-by-bin")).toEqual([{ label: "Stock" }, { label: "Stock by bin" }]);
  });
});

describe("Administration breadcrumbs", () => {
  it("covers every Administration page", () => {
    for (const { href, label } of Object.values(ADMIN_DESTINATIONS)) {
      expect(adminBreadcrumbs(href, null, "/organisation").at(-1)).toEqual({ label });
    }
  });

  it("puts the moved pages under Administration and the Settings tab under Settings", () => {
    expect(adminBreadcrumbs("/locations", null, "/organisation")).toEqual([
      { label: "Administration", href: "/organisation" },
      { label: "Locations" },
    ]);
    expect(adminBreadcrumbs("/history", null, "/organisation").at(-1)).toEqual({ label: "Archive" });
    expect(adminBreadcrumbs("/import", null, "/organisation").at(-1)).toEqual({ label: "Import" });
    expect(adminBreadcrumbs("/settings", "locations", "/organisation")).toEqual([
      { label: "Administration", href: "/organisation" },
      { label: "Settings", href: "/settings" },
      { label: "Location defaults" },
    ]);
    expect(adminBreadcrumbs("/settings/integrations/mcp-tokens", null, "/organisation").map(({ label }) => label))
      .toEqual(["Administration", "Settings", "Integrations", "MCP tokens"]);
    expect(adminBreadcrumbs("/locations", null, "/locations")[0]).toEqual({ label: "Administration", href: undefined });
    expect(adminBreadcrumbs("/catalogue", null, "/organisation")).toEqual([]);
  });
});
