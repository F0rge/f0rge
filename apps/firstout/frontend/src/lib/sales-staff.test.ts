import { describe, expect, it } from "vitest";
import type { CommissionReport, CommissionRow } from "./api";
import { commissionBase, commissionCsvRows, recentMonths } from "./sales-staff";

const row = (name: string, fields: Partial<CommissionRow> = {}): CommissionRow => ({
  sales_staff_id: name === "Unattributed" ? null : name, name, short_name: null, is_active: true,
  commission_rate: "5.00", invoice_count: 1, commissionable_ex_vat: "100.00", excluded_ex_vat: "0.00",
  credit_deductions: "0.00", net_commissionable: "100.00", commission: "5.00", documents: [], ...fields,
});

describe("sales staff helpers", () => {
  it("bases commission on non-excluded lines after discount", () => {
    expect(commissionBase([
      { excluded: false, exVat: "900.00" },
      { excluded: true, exVat: "500.00" },
      { excluded: false, exVat: undefined },
    ])).toBe(900);
  });

  it("lists this month first", () => {
    const months = recentMonths(new Date(2026, 0, 15));
    expect(months).toHaveLength(12);
    expect(months[0].value).toBe("2026-01");
    expect(months[1].value).toBe("2025-12");
  });

  it("exports rows, unattributed without a rate, and totals", () => {
    const report: CommissionReport = {
      month: "2026-11", from_date: "2026-11-01", to_date: "2026-11-30",
      rows: [row("Thandi")], unattributed: row("Unattributed", { commission_rate: "0.00", commission: "0.00" }),
      invoice_count: 2, commissionable_ex_vat: "200.00", excluded_ex_vat: "0.00", credit_deductions: "0.00",
      net_commissionable: "200.00", commission: "5.00",
    };
    expect(commissionCsvRows(report)).toEqual([
      ["Thandi", "1", "100.00", "0.00", "0.00", "100.00", "5.00", "5.00"],
      ["Unattributed", "1", "100.00", "0.00", "0.00", "100.00", "", ""],
      ["Total", "2", "200.00", "0.00", "0.00", "200.00", "", "5.00"],
    ]);
  });
});
