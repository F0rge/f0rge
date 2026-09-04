import { describe, expect, it } from "vitest";

import { showViewCanvasButton } from "@/lib/nia-canvas-nav";
import type { CanvasSpec } from "@/lib/nia-canvas-types";
import { canvasTableComponents } from "@/lib/nia-spreadsheet";

function overdueTableSpec(): CanvasSpec {
  return {
    kind: "canvas_spec",
    path: "/canvas",
    title: "Overdue invoices",
    components: [
      {
        type: "table",
        id: "overdue-invoices",
        title: "Overdue invoices (30-day terms)",
        headers: ["Invoice", "Customer", "Remaining"],
        rows: [["INV-0004", "Naledi Mokoena", "2070.00"]],
      },
    ],
  };
}

describe("canvas_spec dock card", () => {
  it("extracts table components for canvas only (dock does not mount Jspreadsheet)", () => {
    const tables = canvasTableComponents(overdueTableSpec());
    expect(tables).toHaveLength(1);
    expect(tables[0]?.headers).toEqual(["Invoice", "Customer", "Remaining"]);
    expect(tables[0]?.rows[0]?.[0]).toBe("INV-0004");
  });

  it("omits View Canvas when the dock is already on /canvas", () => {
    expect(showViewCanvasButton("/canvas")).toBe(false);
    expect(showViewCanvasButton("/canvas/")).toBe(false);
  });

  it("shows View Canvas off /canvas for table and mixed specs", () => {
    expect(showViewCanvasButton("/invoices")).toBe(true);
    expect(showViewCanvasButton("/")).toBe(true);
    const tableOnly = overdueTableSpec();
    expect(tableOnly.components.every((c) => c.type === "table")).toBe(true);
    const mixed: CanvasSpec = {
      ...overdueTableSpec(),
      components: [
        ...overdueTableSpec().components,
        { type: "metric", id: "count", label: "Overdue", value: "1" },
      ],
    };
    expect(mixed.components.every((c) => c.type === "table")).toBe(false);
  });
});
