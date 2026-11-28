import { describe, expect, it } from "vitest";
import { adminDestination, adminNavGroupsFor, administrationHome, isAdminPath, searchAdminDestinations } from "./admin-navigation";
import {
  NAV_GROUPS,
  isNavLinkActive,
  navAccess,
  navGroupForPath,
  navGroupsFor,
} from "./nav";
import { PERMISSION_CATALOG } from "./permissions";

// Built-in presets, as `app/permissions.py` ROLE_PRESETS grants them.
const PRESETS = {
  owner: [...PERMISSION_CATALOG],
  till: ["till.sell", "till.discount", "sales.returns", "sales.laybys", "sales.quotes", "sales.orders", "sales.deliveries", "sales.customers"],
  warehouse: ["stock.receive", "stock.transfer", "stock.adjust", "sales.returns", "sales.quotes", "sales.deliveries", "till.discount"],
  buyer: ["catalogue.mutate", "po.raise", "stock.cost.view"],
  books: ["books.mutate", "books.journals", "sales.customers", "stock.cost.view", "sales.refunds"],
} as const;

type Preset = keyof typeof PRESETS;
const userFor = (role: string, permissions: readonly string[]) => ({ role, permissions: [...permissions] });

/** Everything a person sees: the sidebar (without the phone-only console) then the Administration shell's navigation. */
function pagesFor(role: string, permissions: readonly string[]): string[] {
  const user = userFor(role, permissions);
  const side = navGroupsFor(user).flatMap((group) => group.pages
    .filter((page) => !page.mobileOnly)
    .map((page) => `${group.id === "reports" && page.href.startsWith("/reports") ? "Reports: " : ""}${page.label}${page.access === "view" ? " (view)" : ""}`));
  const admin = adminNavGroupsFor(user).flatMap((group) => group.items
    .map(({ id, access }) => `${adminDestination(id).label}${access === "view" ? " (view)" : ""}`));
  return [...side, ...admin];
}
const forPreset = (preset: Preset) => pagesFor(preset, PRESETS[preset]);

describe("role-aware sidebar", () => {
  it("shows the owner every page", () => {
    expect(forPreset("owner")).toEqual([
      "Home", "Till",
      "Quotes", "Orders", "Laybys", "Invoices", "Returns", "Credit notes", "Customers",
      "Catalogue", "Price lists",
      "Reorder", "Purchase orders", "Proformas", "Suppliers",
      "Receive", "Transit", "Transfers", "Picks", "Deliveries",
      "Stock on hand", "Stock by bin", "Stocktakes", "Adjustments",
      "Bills", "Payments", "Bank reconciliation", "Journals", "Repeating invoices", "Chart of accounts", "VAT201", "Books periods",
      "Reports: Sales", "Reports: Stock", "Reports: Books", "Commission",
      "Organisation", "Settings directory", "Team members", "Sales staff", "Roles & permissions",
      "Company", "Documents", "Locations", "Location defaults", "Operations", "Labels",
      "Categories", "Materials", "MCP tokens", "Audit log", "Import", "Archive", "My profile",
    ]);
    // The mockup's 53, plus Location defaults: the spec keeps the Settings tab beside the Locations page.
    expect(forPreset("owner")).toHaveLength(54);
  });

  it("shows till staff the shop floor", () => {
    expect(forPreset("till")).toEqual([
      "Home", "Till", "Quotes", "Orders", "Laybys", "Invoices (view)", "Returns", "Customers",
      "Catalogue (view)", "Price lists (view)", "Transfers", "Picks", "Deliveries",
      "Stock on hand", "Stock by bin", "My profile",
    ]);
  });

  it("shows warehouse staff the goods", () => {
    expect(forPreset("warehouse")).toEqual([
      "Home", "Quotes", "Orders", "Returns", "Catalogue (view)",
      "Receive", "Transit (view)", "Transfers", "Picks", "Deliveries",
      "Stock on hand", "Stock by bin", "Stocktakes", "Adjustments", "Locations", "My profile",
    ]);
  });

  it("shows the buyer buying and the catalogue", () => {
    expect(forPreset("buyer")).toEqual([
      "Home", "Customers", "Catalogue", "Price lists", "Reorder", "Purchase orders", "Proformas", "Suppliers",
      "Transit", "Stock on hand", "Stock by bin", "Reports: Sales", "Reports: Stock",
      "Categories", "Materials", "MCP tokens", "Import", "Archive", "My profile",
    ]);
  });

  it("shows books the money", () => {
    expect(forPreset("books")).toEqual([
      // Orders: the books preset holds sales.refunds, and refunds are taken on an order (one more than the mockup's 21).
      "Home", "Orders", "Invoices", "Credit notes", "Customers", "Suppliers (view)",
      "Bills", "Payments", "Bank reconciliation", "Journals", "Repeating invoices", "Chart of accounts", "VAT201", "Books periods",
      "Reports: Sales", "Reports: Stock", "Reports: Books", "Commission",
      "MCP tokens", "Audit log", "Archive", "My profile",
    ]);
  });

  it("decides from permission keys, not the role name", () => {
    expect(pagesFor("owner", [])).toEqual(["Home", "My profile"]);
    expect(pagesFor("deliveries-only", ["sales.deliveries"])).toEqual([
      "Home", "Orders", "Picks", "Deliveries", "My profile",
    ]);
    // The API checks books.journals and po.raise on no journal or purchase-order write: lookups only.
    expect(pagesFor("journals-only", ["books.journals"])).toEqual(["Home", "Journals (view)", "Reports: Books", "My profile"]);
    expect(pagesFor("credit-only", ["po.raise"])).toEqual([
      "Home", "Customers", "Purchase orders (view)", "Stock on hand", "Stock by bin", "Reports: Sales", "Reports: Stock", "Archive", "My profile",
    ]);
    expect(pagesFor("quotes-only", ["sales.quotes"])).toEqual([
      "Home", "Quotes", "Catalogue (view)", "Stock on hand", "Stock by bin", "My profile",
    ]);
    expect(pagesFor("stock-counter", ["stock.receive"])).toEqual([
      "Home", "Catalogue (view)", "Receive", "Transit (view)", "Stock on hand", "Stock by bin", "Stocktakes", "Adjustments", "Locations", "My profile",
    ]);
  });

  it("drops groups with nothing to show", () => {
    expect(navGroupsFor(userFor("custom", ["till.sell"])).map((group) => group.id)).toEqual(
      ["home", "till", "sell", "products", "warehouse", "stock"],
    );
    expect(navGroupsFor(userFor("custom", [])).map((group) => group.id)).toEqual(["home"]);
    expect(adminNavGroupsFor(userFor("custom", [])).map((group) => group.label)).toEqual(["My account"]);
  });

  it("tags only pages with actions as view-only", () => {
    expect(navAccess({ actions: ["books.mutate"], lookup: ["till.sell"] }, userFor("x", ["till.sell"]))).toBe("view");
    expect(navAccess({ lookup: ["till.sell"] }, userFor("x", ["till.sell"]))).toBe("do");
    expect(navAccess({ actions: ["books.mutate"] }, userFor("x", ["till.sell"]))).toBeNull();
    expect(navAccess({ everyone: true }, null)).toBe("do");
  });

  it("keeps Organisation to the owner, as its page does", () => {
    const manager = userFor("manager", ["users.manage"]);
    expect(adminNavGroupsFor(manager)[0]?.items.map(({ id }) => id)).toEqual(["team", "salesStaff", "roles"]);
    expect(administrationHome(manager)).toBe("/users");
    expect(administrationHome(userFor("owner", PRESETS.owner))).toBe("/organisation");
    expect(administrationHome(userFor("buyer", PRESETS.buyer))).toBe("/settings/categories");
    expect(administrationHome(userFor("till", PRESETS.till))).toBe("/profile");
    expect(administrationHome(userFor("warehouse", PRESETS.warehouse))).toBe("/locations");
    expect(administrationHome(userFor("books", PRESETS.books))).toBe("/audit");
    expect(administrationHome(userFor("settings-only", ["settings.mutate"]))).toBe("/settings");
    expect(administrationHome(userFor("credit-only", ["po.raise"]))).toBe("/history");
    expect(administrationHome(userFor("nobody", []))).toBe("/profile");
    expect(administrationHome(null)).toBe("/profile");
  });
});

describe("nav paths", () => {
  it("expands the group holding the current page", () => {
    expect(navGroupForPath("/catalogue/aaaaaaaa-bbbb")?.id).toBe("products");
    expect(navGroupForPath("/purchase-orders/abc")?.id).toBe("buy");
    expect(navGroupForPath("/suppliers")?.id).toBe("buy");
    expect(navGroupForPath("/deliveries")?.id).toBe("warehouse");
    expect(navGroupForPath("/wms")?.id).toBe("warehouse");
    expect(navGroupForPath("/stock")?.id).toBe("stock");
    expect(navGroupForPath("/stock-by-bin")?.id).toBe("stock");
    expect(navGroupForPath("/reorder")?.id).toBe("buy");
    expect(navGroupForPath("/invoices/abc")?.id).toBe("sell");
    expect(navGroupForPath("/reports")?.id).toBe("reports");
    expect(navGroupForPath("/commission")?.id).toBe("reports");
    expect(navGroupForPath("/bills/new")?.id).toBe("books");
    expect(navGroupForPath("/locations")).toBeUndefined();
    expect(navGroupForPath("/stockx")).toBeUndefined();
  });

  it("marks the current item, Reports by section", () => {
    expect(isNavLinkActive("/catalogue/abc", "/catalogue")).toBe(true);
    expect(isNavLinkActive("/proformas/read", "/proformas")).toBe(true);
    expect(isNavLinkActive("/stock-by-bin", "/stock")).toBe(false);
    expect(isNavLinkActive("/reports", "/reports?section=sales", "sales")).toBe(true);
    expect(isNavLinkActive("/reports", "/reports?section=sales", "books")).toBe(false);
    expect(isNavLinkActive("/reports", "/reports?section=sales", null)).toBe(false);
    expect(isNavLinkActive("/", "/")).toBe(true);
    expect(isNavLinkActive("/till", "/")).toBe(false);
  });

  it("puts every route in exactly one group", () => {
    const hrefs = NAV_GROUPS.flatMap((group) => group.pages.map((page) => page.href));
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });

  it("renders the moved pages inside the Administration shell", () => {
    for (const path of ["/locations", "/import", "/history", "/settings", "/settings/integrations/mcp-tokens", "/users", "/audit"]) {
      expect(isAdminPath(path)).toBe(true);
    }
    for (const path of ["/cin7-import", "/stock", "/reports", "/catalogue"]) {
      expect(isAdminPath(path)).toBe(false);
    }
  });
});

describe("Administration directory search", () => {
  const owner = { role: "owner", permissions: ["users.manage"] };
  const manager = { role: "manager", permissions: ["users.manage"] };
  const staff = { role: "till", permissions: ["till.sell"] };

  it("matches page names or descriptions and puts direct name matches first", () => {
    expect(searchAdminDestinations("  DoCuMeNt numbering  ", owner)[0]?.href).toBe("/settings?tab=documents");
    expect(searchAdminDestinations("MCP tokens", owner)[0]?.href).toBe("/settings/integrations/mcp-tokens");
    expect(searchAdminDestinations("location defaults", owner)[0]?.href).toBe("/settings?tab=locations");
    expect(searchAdminDestinations("archive", owner)[0]?.href).toBe("/history");
    expect(searchAdminDestinations("import", owner)[0]?.href).toBe("/import");
    expect(searchAdminDestinations("bins", staff)[0]?.href).toBe("/locations");
  });

  it("omits destinations outside the staff member's permissions", () => {
    expect(searchAdminDestinations("Team members", staff)).toEqual([]);
    expect(searchAdminDestinations("Roles & permissions", staff)).toEqual([]);
    expect(searchAdminDestinations("Organisation", manager).every(({ href }) => href !== "/organisation")).toBe(true);
    expect(searchAdminDestinations("Team members", manager)[0]?.href).toBe("/users");
    expect(searchAdminDestinations("MCP tokens", staff)[0]?.href).toBe("/settings/integrations/mcp-tokens");
    expect(searchAdminDestinations("MCP tokens", null)).toEqual([]);
    expect(searchAdminDestinations("   ", owner)).toEqual([]);
  });
});
