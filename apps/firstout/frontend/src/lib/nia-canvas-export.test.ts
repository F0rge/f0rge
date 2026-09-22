import { describe, expect, it } from "vitest";

import type { CanvasSpec } from "./nia-canvas-types";
import { canvasExportSheets, exportFilename } from "./nia-canvas-export";

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

describe("canvasExportSheets", () => {
  it("flattens a mixed spec into sheets in component order", () => {
    const sheets = canvasExportSheets(mixedSpec());

    expect(sheets).toHaveLength(3);
    expect(sheets[0]?.name).toBe("Units");
    expect(sheets[0]?.headers).toEqual(["Label", "Value"]);
    expect(sheets[0]?.rows).toEqual([["Units", "12"]]);

    expect(sheets[1]?.name).toBe("Stock on hand");
    expect(sheets[1]?.headers).toEqual(["SKU", "Location", "On hand"]);
    expect(sheets[1]?.rows[0]?.[0]).toBe("VEL-SOFA-LONDON");

    expect(sheets[2]?.name).toBe("Sales");
    expect(sheets[2]?.headers).toEqual(["Category", "Sales"]);
    expect(sheets[2]?.rows).toEqual([["Dining", 1], ["Sofas", 2]]);
  });

  it("sanitises and uniquifies sheet names", () => {
    const sheets = canvasExportSheets({
      kind: "canvas_spec",
      path: "/canvas",
      title: "Duplicate tables",
      components: [
        {
          type: "table",
          id: "one",
          title: "Stock",
          headers: ["A"],
          rows: [["1"]],
        },
        {
          type: "table",
          id: "two",
          title: "Stock",
          headers: ["B"],
          rows: [["2"]],
        },
        {
          type: "table",
          id: "three",
          title: "Foo/Bar?*[]:messy   name",
          headers: ["C"],
          rows: [["3"]],
        },
        {
          type: "table",
          id: "four",
          title: "abcdefghijklmnopqrstuvwxyz1234567890",
          headers: ["D"],
          rows: [["4"]],
        },
      ],
    });

    expect(sheets.map((sheet) => sheet.name)).toEqual([
      "Stock",
      "Stock 2",
      "FooBar messy name",
      "abcdefghijklmnopqrstuvwxyz12345",
    ]);
  });

  it("avoids Excel sheet-name collisions across suffixes and case", () => {
    const sheets = canvasExportSheets({
      kind: "canvas_spec",
      path: "/canvas",
      title: "Collisions",
      components: [
        {
          type: "table",
          id: "one",
          title: "Sales",
          headers: ["A"],
          rows: [["1"]],
        },
        {
          type: "table",
          id: "two",
          title: "Sales",
          headers: ["B"],
          rows: [["2"]],
        },
        {
          type: "table",
          id: "three",
          title: "Sales 2",
          headers: ["C"],
          rows: [["3"]],
        },
        {
          type: "table",
          id: "four",
          title: "sales",
          headers: ["D"],
          rows: [["4"]],
        },
      ],
    });

    expect(sheets.map((sheet) => sheet.name)).toEqual([
      "Sales",
      "Sales 2",
      "Sales 2 2",
      "sales 3",
    ]);
  });

  it("returns an empty list for empty specs", () => {
    expect(canvasExportSheets(null)).toEqual([]);
    expect(
      canvasExportSheets({
        kind: "canvas_spec",
        path: "/canvas",
        title: "Empty",
        components: [],
      }),
    ).toEqual([]);
  });

  it("omits bar charts whose series lengths do not match categories", () => {
    expect(
      canvasExportSheets({
        kind: "canvas_spec",
        path: "/canvas",
        title: "Broken chart",
        components: [
          {
            type: "bar",
            id: "bad",
            title: "Sales",
            categories: ["Dining", "Sofas"],
            series: [{ name: "Sales", values: [1] }],
          },
        ],
      }),
    ).toEqual([]);
  });
});

describe("exportFilename", () => {
  it("builds a slugged filename with the provided date", () => {
    expect(exportFilename("Top 10 selling SKUs", "2026-09-13")).toBe(
      "top-10-selling-skus-2026-09-13.xlsx",
    );
    expect(exportFilename("***", "2026-09-13")).toBe("canvas-2026-09-13.xlsx");
  });
});
