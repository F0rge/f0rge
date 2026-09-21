import type {
  CanvasBarLineComponent,
  CanvasComponent,
  CanvasSpec,
} from "./nia-canvas-types";

export type CanvasExportCell = string | number;

export type CanvasExportSheet = {
  name: string;
  headers: string[];
  rows: CanvasExportCell[][];
};

const INVALID_SHEET_CHARS = /[\\/?*[\]]/g;

function validChartSeries(component: CanvasBarLineComponent) {
  return component.series.filter(
    (entry) => entry.values.length === component.categories.length,
  );
}

function sanitizeSheetBaseName(raw: string): string {
  const stripped = raw
    .replace(INVALID_SHEET_CHARS, "")
    .replace(/:/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const capped = stripped.slice(0, 31).trim();
  return capped.length > 0 ? capped : "Sheet";
}

function uniquifySheetNames(sheets: CanvasExportSheet[]): CanvasExportSheet[] {
  const used = new Set<string>();
  return sheets.map((sheet) => {
    const base = sanitizeSheetBaseName(sheet.name);
    let candidate = base;
    let n = 2;
    while (used.has(candidate.toLowerCase())) {
      const suffix = ` ${n}`;
      const maxBaseLen = Math.max(1, 31 - suffix.length);
      candidate = `${base.slice(0, maxBaseLen)}${suffix}`;
      n += 1;
    }
    used.add(candidate.toLowerCase());
    return { ...sheet, name: candidate };
  });
}

function sheetFromTable(component: Extract<CanvasComponent, { type: "table" }>): CanvasExportSheet {
  return {
    name: component.title,
    headers: component.headers,
    rows: component.rows.map((row) => [...row]),
  };
}

function sheetFromChart(component: CanvasBarLineComponent): CanvasExportSheet | null {
  const series = validChartSeries(component);
  if (series.length === 0 || component.categories.length === 0) {
    return null;
  }
  const headers = ["Category", ...series.map((entry) => entry.name)];
  const rows: CanvasExportCell[][] = component.categories.map((category, index) => [
    category,
    ...series.map((entry) => entry.values[index] ?? 0),
  ]);
  return {
    name: component.title,
    headers,
    rows,
  };
}

function sheetFromMetric(component: Extract<CanvasComponent, { type: "metric" }>): CanvasExportSheet {
  return {
    name: component.label,
    headers: ["Label", "Value"],
    rows: [[component.label, component.value]],
  };
}

function sheetFromComponent(component: CanvasComponent): CanvasExportSheet | null {
  if (component.type === "table") {
    return sheetFromTable(component);
  }
  if (component.type === "bar" || component.type === "line") {
    return sheetFromChart(component);
  }
  if (component.type === "metric") {
    return sheetFromMetric(component);
  }
  return null;
}

export function canvasExportSheets(
  spec: CanvasSpec | null | undefined,
): CanvasExportSheet[] {
  if (!spec || spec.components.length === 0) {
    return [];
  }
  const sheets = spec.components
    .map((component) => sheetFromComponent(component))
    .filter((sheet): sheet is CanvasExportSheet => sheet !== null);
  return uniquifySheetNames(sheets);
}

export function exportFilename(title: string, isoDate: string): string {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  const base = slug.length > 0 ? slug : "canvas";
  return `${base}-${isoDate}.xlsx`;
}
