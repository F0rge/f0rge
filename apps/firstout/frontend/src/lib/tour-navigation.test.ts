import { describe, expect, it } from "vitest";

import { headingMatches, routeMatches } from "./tour-navigation";

describe("tour navigation", () => {
  it("treats home as an exact path", () => {
    expect(routeMatches("/", "/")).toBe(true);
    expect(routeMatches("/catalogue", "/")).toBe(false);
    expect(routeMatches("/invoices/abc", "/invoices")).toBe(true);
    expect(routeMatches("/invoice", "/invoices")).toBe(false);
  });

  it("matches page headings loosely", () => {
    expect(headingMatches("Customers CRM", "Customers")).toBe(true);
    expect(headingMatches("  Bank   reconciliation ", "bank reconciliation")).toBe(true);
    expect(headingMatches("Till", "Settings")).toBe(false);
    expect(headingMatches(null, "Home")).toBe(false);
  });
});
