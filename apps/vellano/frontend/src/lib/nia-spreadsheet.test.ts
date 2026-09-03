import { describe, expect, it } from "vitest";

import type { CanvasSpec } from "./nia-canvas-types";
import { buildSpreadsheetConfig, canvasTableComponents } from "./nia-spreadsheet";

function mixedSpec(): CanvasSpec {
  return {
    kind: "canvas_spec",
    path: "/canvas",
    title: "Stock on hand",
    components: [
      {
        type: "metric",
        id: "units",
        label: "Units",
        value: "12",
      },
      {
        type: "table",
        id: "stock-table",
        title: "Stock on hand",
        headers: ["SKU", "Location", "On hand"],
        rows: [
          ["VEL-SOFA-LONDON", "Kramerville", "4"],
          ["PG-TABLE", "Bedfordview", "1"],
        ],
      },
      {
        type: "bar",
        id: "sales",
        title: "Sales",
        categories: ["Dining", "Sofas"],
        series: [{ name: "Sales", values: [1, 2] }],
      },
    ],
  };
}

describe("buildSpreadsheetConfig", () => {
  it("maps headers and rows into a jspreadsheet CE worksheet", () => {
    const config = buildSpreadsheetConfig({
      headers: ["Invoice", "Remaining"],
      rows: [["INV-0001", "2070.00"]],
    });

    expect(config.tabs).toBe(false);
    expect(config.toolbar).toBe(false);
    expect(config.parseHTML).toBe(false);
    expect(config.contextMenu()).toEqual([]);
    expect(config.worksheets).toHaveLength(1);

    const worksheet = config.worksheets[0];
    expect(worksheet.data).toEqual([["INV-0001", "2070.00"]]);
    expect(worksheet.columns.map((column) => column.title)).toEqual(["Invoice", "Remaining"]);
    expect(worksheet.columns.every((column) => column.type === "text")).toBe(true);
    expect(worksheet.columns.every((column) => column.readOnly)).toBe(true);
    expect(worksheet.columns.every((column) => column.align === "left")).toBe(true);
    expect(worksheet.editable).toBe(false);
    expect(worksheet.columnSorting).toBe(true);
    expect(worksheet.columnResize).toBe(true);
    expect(worksheet.allowInsertRow).toBe(false);
    expect(worksheet.allowDeleteRow).toBe(false);
  });

  it("defaults to read-only viewing and uses compact height when requested", () => {
    const full = buildSpreadsheetConfig({
      headers: ["SKU"],
      rows: [["VEL-BI-V1"]],
    });
    const compact = buildSpreadsheetConfig({
      headers: ["SKU"],
      rows: [["VEL-BI-V1"]],
      compact: true,
    });

    expect(full.worksheets[0].editable).toBe(false);
    expect(full.worksheets[0].tableHeight).toBe("360px");
    expect(compact.worksheets[0].tableHeight).toBe("168px");
    expect(compact.worksheets[0].columns[0].width).toBeLessThan(full.worksheets[0].columns[0].width);
  });

  it("pads short rows and uses a Value column when headers are empty", () => {
    const config = buildSpreadsheetConfig({
      headers: [],
      rows: [["only-cell"], []],
    });
    const worksheet = config.worksheets[0];
    expect(worksheet.columns.map((column) => column.title)).toEqual(["Value"]);
    expect(worksheet.data).toEqual([["only-cell"], [""]]);
  });

  it("allows edits only when readOnly is explicitly false", () => {
    const config = buildSpreadsheetConfig({
      headers: ["Note"],
      rows: [["draft"]],
      readOnly: false,
    });
    expect(config.worksheets[0].editable).toBe(true);
    expect(config.worksheets[0].columns[0].readOnly).toBe(false);
  });
});

describe("canvasTableComponents", () => {
  it("returns only table components from a canvas_spec", () => {
    const tables = canvasTableComponents(mixedSpec());
    expect(tables).toHaveLength(1);
    expect(tables[0]?.id).toBe("stock-table");
    expect(tables[0]?.headers).toEqual(["SKU", "Location", "On hand"]);
    expect(tables[0]?.rows).toEqual([
      ["VEL-SOFA-LONDON", "Kramerville", "4"],
      ["PG-TABLE", "Bedfordview", "1"],
    ]);
  });

  it("returns an empty list when the spec has no tables", () => {
    expect(
      canvasTableComponents({
        components: [
          {
            type: "metric",
            id: "units",
            label: "Units",
            value: "12",
          },
        ],
      }),
    ).toEqual([]);
  });
});
