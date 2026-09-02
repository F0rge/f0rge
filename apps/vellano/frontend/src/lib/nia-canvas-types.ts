export type CanvasBarLineComponent = {
  type: "bar" | "line";
  id: string;
  title: string;
  categories: string[];
  series: { name: string; values: number[] }[];
};

export type CanvasTableComponent = {
  type: "table";
  id: string;
  title: string;
  headers: string[];
  rows: string[][];
};

export type CanvasMetricComponent = {
  type: "metric";
  id: string;
  label: string;
  value: string;
};

export type CanvasComponent =
  | CanvasBarLineComponent
  | CanvasTableComponent
  | CanvasMetricComponent;

export type CanvasSpec = {
  kind: "canvas_spec";
  path: "/canvas";
  title: string;
  components: CanvasComponent[];
};

export type CanvasClearedPayload = {
  kind: "canvas_cleared";
  path?: "/canvas";
  cleared_at?: string;
};

const CHART_TYPES = new Set(["bar", "line", "table", "metric"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseSeries(value: unknown): { name: string; values: number[] }[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const series: { name: string; values: number[] }[] = [];
  for (const entry of value) {
    if (!isRecord(entry) || typeof entry.name !== "string" || !Array.isArray(entry.values)) {
      return null;
    }
    const values: number[] = [];
    for (const raw of entry.values) {
      if (typeof raw !== "number" || !Number.isFinite(raw)) {
        return null;
      }
      values.push(raw);
    }
    series.push({ name: entry.name, values });
  }
  return series;
}

function parseBarLineComponent(raw: Record<string, unknown>): CanvasBarLineComponent | null {
  const type = raw.type;
  if (type !== "bar" && type !== "line") {
    return null;
  }
  if (typeof raw.id !== "string" || typeof raw.title !== "string" || !Array.isArray(raw.categories)) {
    return null;
  }
  const categories = raw.categories.filter((item): item is string => typeof item === "string");
  if (categories.length !== raw.categories.length) {
    return null;
  }
  const series = parseSeries(raw.series);
  if (!series) {
    return null;
  }
  return { type, id: raw.id, title: raw.title, categories, series };
}

function parseTableComponent(raw: Record<string, unknown>): CanvasTableComponent | null {
  if (raw.type !== "table") {
    return null;
  }
  if (typeof raw.id !== "string" || typeof raw.title !== "string" || !Array.isArray(raw.headers)) {
    return null;
  }
  const headers = raw.headers.filter((item): item is string => typeof item === "string");
  if (headers.length !== raw.headers.length || !Array.isArray(raw.rows)) {
    return null;
  }
  const rows: string[][] = [];
  for (const row of raw.rows) {
    if (!Array.isArray(row)) {
      return null;
    }
    const cells = row.filter((cell): cell is string => typeof cell === "string");
    if (cells.length !== row.length) {
      return null;
    }
    rows.push(cells);
  }
  return { type: "table", id: raw.id, title: raw.title, headers, rows };
}

function parseMetricComponent(raw: Record<string, unknown>): CanvasMetricComponent | null {
  if (raw.type !== "metric") {
    return null;
  }
  if (typeof raw.id !== "string" || typeof raw.label !== "string" || typeof raw.value !== "string") {
    return null;
  }
  return { type: "metric", id: raw.id, label: raw.label, value: raw.value };
}

function parseCanvasComponent(raw: unknown): CanvasComponent | null {
  if (!isRecord(raw) || typeof raw.type !== "string" || !CHART_TYPES.has(raw.type)) {
    return null;
  }
  if (raw.type === "bar" || raw.type === "line") {
    return parseBarLineComponent(raw);
  }
  if (raw.type === "table") {
    return parseTableComponent(raw);
  }
  if (raw.type === "metric") {
    return parseMetricComponent(raw);
  }
  return null;
}

export function parseCanvasSpec(raw: unknown): CanvasSpec | null {
  if (!isRecord(raw) || raw.kind !== "canvas_spec") {
    return null;
  }
  if (raw.path !== "/canvas" || typeof raw.title !== "string" || !Array.isArray(raw.components)) {
    return null;
  }
  const components: CanvasComponent[] = [];
  for (const entry of raw.components) {
    const component = parseCanvasComponent(entry);
    if (component) {
      components.push(component);
    }
  }
  return {
    kind: "canvas_spec",
    path: "/canvas",
    title: raw.title,
    components,
  };
}

export function isCanvasSpecPayload(
  payload: { kind: string; [key: string]: unknown },
): payload is CanvasSpec {
  return parseCanvasSpec(payload) !== null;
}

export function isCanvasClearedPayload(
  payload: { kind: string; [key: string]: unknown },
): payload is CanvasClearedPayload {
  if (payload.kind !== "canvas_cleared") {
    return false;
  }
  return payload.path === "/canvas" || payload.path === undefined;
}

export function isEmptyCanvasSpec(spec: CanvasSpec | null): boolean {
  return spec === null || spec.components.length === 0;
}
