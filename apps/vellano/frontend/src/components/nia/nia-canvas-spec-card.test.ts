import { describe, expect, it } from "vitest";

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

describe("canvas_spec dock tables", () => {
  it("exposes table components for inline Jspreadsheet preview", () => {
    const tables = canvasTableComponents(overdueTableSpec());
    expect(tables).toHaveLength(1);
    expect(tables[0]?.headers).toEqual(["Invoice", "Customer", "Remaining"]);
    expect(tables[0]?.rows[0]?.[0]).toBe("INV-0004");
  });

  it("treats a table-only canvas_spec as inline-primary", () => {
    const spec = overdueTableSpec();
    const tables = canvasTableComponents(spec);
    const tableOnly =
      tables.length > 0 && spec.components.every((component) => component.type === "table");
    expect(tableOnly).toBe(true);
  });
});
