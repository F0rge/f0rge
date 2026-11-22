import { describe, expect, it } from "vitest";

import { can, PERMISSION_CATALOG, permissionLabel } from "./permissions";

describe("sale price authority (Firstout ADR 0002)", () => {
  it("is granted by permission keys, never by role", () => {
    const owner = { role: "owner", permissions: ["till.discount", "sales.price_override"] };
    const warehouse = { role: "warehouse", permissions: ["till.discount"] };
    const custom = { role: "owner", permissions: [] };
    expect(can(owner, "sales.price_override")).toBe(true);
    expect(can(warehouse, "till.discount")).toBe(true);
    expect(can(warehouse, "sales.price_override")).toBe(false);
    expect(can(custom, "till.discount")).toBe(false);
    expect(can(null, "till.discount")).toBe(false);
  });

  it("lists both keys with plain labels for the roles screen", () => {
    expect(PERMISSION_CATALOG).toContain("sales.price_override");
    expect(permissionLabel("sales.price_override")).toBe("Override unit prices");
    expect(permissionLabel("till.discount")).toBe("Apply discounts");
  });
});
