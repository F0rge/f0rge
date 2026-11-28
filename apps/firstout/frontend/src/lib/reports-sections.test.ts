import { describe, expect, it } from "vitest";
import { REPORT_TABS, reportsView } from "./reports-sections";

const labels = (section: string | null) => reportsView(section).tabs.map((tab) => tab.label);

describe("reports sections", () => {
  it("shows only the section's tabs", () => {
    expect(labels("sales")).toEqual(["Sales by SKU", "Criticality", "Sales VAT"]);
    expect(labels("stock")).toEqual(["Stock valuation", "Aged stock", "Lead times"]);
    expect(labels("books")).toEqual(["Aged AR", "Aged AP", "Profit & loss", "Balance sheet", "Trial balance", "Journals", "Cash summary"]);
  });

  it("shows all thirteen without a section, so old links keep working", () => {
    expect(labels(null)).toHaveLength(13);
    expect(labels("unknown")).toEqual(REPORT_TABS.map((tab) => tab.label));
    expect(reportsView(null).title).toBe("Reports");
    expect(reportsView(null).sectionLabel).toBeNull();
  });

  it("titles the page after the section", () => {
    expect(reportsView("sales").title).toBe("Sales reports");
    expect(reportsView("stock").title).toBe("Stock reports");
    expect(reportsView("books").title).toBe("Books reports");
  });

  it("selects the remembered tab within the section, else the first", () => {
    expect(reportsView("books", "journals").selected).toBe(5);
    expect(reportsView("sales", "sales-vat").selected).toBe(2);
    expect(reportsView("sales", "journals").selected).toBe(0);
    expect(reportsView(null, "sales-vat").selected).toBe(12);
    expect(reportsView("stock", null).selected).toBe(0);
  });
});
