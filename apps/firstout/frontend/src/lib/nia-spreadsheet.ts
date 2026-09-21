import type { CanvasComponent, CanvasSpec, CanvasTableComponent } from "@/lib/nia-canvas-types";

export type NiaSpreadsheetColumn = {
  type: "text";
  title: string;
  width: number;
  readOnly: boolean;
  align: "left";
  wordWrap: boolean;
};

export type NiaSpreadsheetWorksheet = {
  data: string[][];
  columns: NiaSpreadsheetColumn[];
  editable: boolean;
  columnSorting: boolean;
  columnResize: boolean;
  columnDrag: boolean;
  rowDrag: boolean;
  allowInsertRow: boolean;
  allowInsertColumn: boolean;
  allowDeleteRow: boolean;
  allowDeleteColumn: boolean;
  allowRenameColumn: boolean;
  allowComments: boolean;
  allowManualInsertRow: boolean;
  allowManualInsertColumn: boolean;
  tableOverflow: boolean;
  tableWidth: string;
  tableHeight: string;
  defaultColAlign: "left";
  parseTableFirstRowAsHeader: boolean;
  wordWrap: boolean;
  selectionCopy: boolean;
};

export type NiaSpreadsheetConfig = {
  tabs: false;
  toolbar: false;
  parseHTML: false;
  allowExport: boolean;
  contextMenu: () => [];
  worksheets: [NiaSpreadsheetWorksheet];
};

export type BuildSpreadsheetConfigInput = {
  headers: string[];
  rows: string[][];
  readOnly?: boolean;
  compact?: boolean;
};

const FULL_COL_MIN = 112;
const FULL_COL_MAX = 220;
const COMPACT_COL_MIN = 88;
const COMPACT_COL_MAX = 140;

function columnWidth(title: string, compact: boolean): number {
  const min = compact ? COMPACT_COL_MIN : FULL_COL_MIN;
  const max = compact ? COMPACT_COL_MAX : FULL_COL_MAX;
  const estimated = title.length * 8 + 24;
  return Math.min(max, Math.max(min, estimated));
}

function normalizeHeaders(headers: string[]): string[] {
  if (headers.length > 0) {
    return headers;
  }
  return ["Value"];
}

function normalizeRows(headers: string[], rows: string[][]): string[][] {
  const width = headers.length;
  if (rows.length === 0) {
    return [Array.from({ length: width }, () => "")];
  }
  return rows.map((row) => {
    const cells = row.slice(0, width).map((cell) => (cell == null ? "" : String(cell)));
    while (cells.length < width) {
      cells.push("");
    }
    return cells;
  });
}

export function canvasTableComponents(
  spec: Pick<CanvasSpec, "components"> | { components: CanvasComponent[] },
): CanvasTableComponent[] {
  return spec.components.filter((component): component is CanvasTableComponent => component.type === "table");
}

export function buildSpreadsheetConfig(input: BuildSpreadsheetConfigInput): NiaSpreadsheetConfig {
  const readOnly = input.readOnly !== false;
  const compact = input.compact === true;
  const headers = normalizeHeaders(input.headers);
  const data = normalizeRows(headers, input.rows);

  return {
    tabs: false,
    toolbar: false,
    parseHTML: false,
    allowExport: true,
    contextMenu: () => [],
    worksheets: [
      {
        data,
        columns: headers.map((title) => ({
          type: "text",
          title,
          width: columnWidth(title, compact),
          readOnly,
          align: "left",
          wordWrap: true,
        })),
        editable: !readOnly,
        columnSorting: true,
        columnResize: true,
        columnDrag: false,
        rowDrag: false,
        allowInsertRow: false,
        allowInsertColumn: false,
        allowDeleteRow: false,
        allowDeleteColumn: false,
        allowRenameColumn: false,
        allowComments: false,
        allowManualInsertRow: false,
        allowManualInsertColumn: false,
        tableOverflow: true,
        tableWidth: "100%",
        tableHeight: compact ? "168px" : "360px",
        defaultColAlign: "left",
        parseTableFirstRowAsHeader: false,
        wordWrap: true,
        selectionCopy: true,
      },
    ],
  };
}
