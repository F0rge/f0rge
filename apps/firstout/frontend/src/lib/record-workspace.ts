import type {
  WorkspaceFilter,
  WorkspaceOperator,
  WorkspaceQuery,
  WorkspaceValue,
} from "./record-workspace-api";
import type { AuthUser } from "./api";

export function workspaceIdentity(user: AuthUser | null): string {
  return JSON.stringify([
    user?.team.id,
    user?.id,
    user?.role,
    [...(user?.permissions ?? [])].sort(),
  ]);
}

// Persist this reconciliation in component state when the URL key changes.
// A render-only fallback would resurrect an old draft when Back/Reset revisits it.
export function workspaceStateForKey<T extends { key: string }>(
  state: T,
  current: T,
): T {
  return state.key === current.key ? state : current;
}

export const WORKSPACE_PAGE_SIZES = [10, 25, 50, 100];
const OPERATORS: WorkspaceOperator[] = [
  "eq",
  "ne",
  "contains",
  "gt",
  "gte",
  "lt",
  "lte",
  "empty",
  "not_empty",
];
interface SearchValues {
  get: (key: string) => string | null;
}
export function isWorkspaceFilter(value: unknown): value is WorkspaceFilter {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.field === "string" &&
    item.field.length > 0 &&
    item.field.length <= 64 &&
    OPERATORS.includes(item.operator as WorkspaceOperator) &&
    (item.value === null ||
      typeof item.value === "string" ||
      typeof item.value === "boolean" ||
      (typeof item.value === "number" && Number.isFinite(item.value)))
  );
}
export function readWorkspaceQuery(
  params: SearchValues,
  defaultSort = "name",
): WorkspaceQuery {
  let filters: WorkspaceFilter[] = [];
  try {
    const parsed: unknown = JSON.parse(params.get("filters") || "[]");
    if (Array.isArray(parsed))
      filters = parsed.filter(isWorkspaceFilter).slice(0, 20);
  } catch {
    /* Invalid copied URLs start with no filter clauses. */
  }
  const limit = Number(params.get("size") || 25);
  const page = Math.max(1, Number(params.get("page")) || 1);
  const lifecycle = params.get("lifecycle");
  return {
    q: (params.get("q") || "").slice(0, 200),
    lifecycle:
      lifecycle === "all"
        ? "all"
        : lifecycle === "archived" || params.get("archived") === "true"
          ? "archived"
          : "active",
    match: params.get("match") === "any" ? "any" : "all",
    filters,
    sort: {
      field: params.get("sort") || defaultSort,
      direction: params.get("direction") === "desc" ? "desc" : "asc",
    },
    limit: WORKSPACE_PAGE_SIZES.includes(limit) ? limit : 25,
    offset:
      (Math.min(Math.floor(page), 100000) - 1) *
      (WORKSPACE_PAGE_SIZES.includes(limit) ? limit : 25),
  };
}
export function workspaceSearch(
  query: WorkspaceQuery,
  record?: string,
): string {
  const values = new URLSearchParams();
  if (query.q) values.set("q", query.q);
  if (query.lifecycle !== "active") values.set("lifecycle", query.lifecycle);
  if (query.match !== "all") values.set("match", query.match);
  if (query.filters.length)
    values.set("filters", JSON.stringify(query.filters));
  values.set("sort", query.sort.field);
  values.set("direction", query.sort.direction);
  values.set("size", String(query.limit));
  values.set("page", String(Math.floor(query.offset / query.limit) + 1));
  if (record) values.set("record", record);
  return values.toString();
}
export function selectionContext(
  query: WorkspaceQuery,
  identity: string,
  resource: string,
): string {
  return JSON.stringify([
    identity,
    resource,
    query.q,
    query.lifecycle,
    query.match,
    query.filters,
    query.sort,
  ]);
}
export function fieldOperators(
  type: string,
): { value: WorkspaceOperator; label: string }[] {
  const base: { value: WorkspaceOperator; label: string }[] = [
    { value: "eq", label: "is" },
    { value: "ne", label: "is not" },
  ];
  if (type === "text") base.push({ value: "contains", label: "contains" });
  if (type === "number" || type === "date")
    base.push(
      { value: "gt", label: "is greater than" },
      { value: "gte", label: "is at least" },
      { value: "lt", label: "is less than" },
      { value: "lte", label: "is at most" },
    );
  return [
    ...base,
    { value: "empty", label: "is empty" },
    { value: "not_empty", label: "is not empty" },
  ];
}
export function workspaceScalar(value: string, type: string): WorkspaceValue {
  if (value === "") return "";
  if (type === "boolean") return value === "true";
  if (type === "number") return Number(value);
  return value;
}
export function quickFilterValue(
  type: string,
  filter?: WorkspaceFilter,
): string {
  if (type === "number") {
    if (filter?.value !== 0) return "";
    return filter.operator === "gt"
      ? "positive"
      : filter.operator === "eq"
        ? "zero"
        : "";
  }
  return filter?.operator === "eq" ? String(filter.value) : "";
}
export interface BulkFieldChange {
  mode: "keep" | "set" | "clear";
  value: string;
}
export interface BulkFieldSchema {
  key: string;
  label: string;
  type: string;
  nullable?: boolean;
}
export function bulkPatch(
  fields: readonly BulkFieldSchema[],
  changes: Record<string, BulkFieldChange>,
): Record<string, WorkspaceValue> {
  const patch: Record<string, WorkspaceValue> = {};
  for (const field of fields) {
    const change = changes[field.key];
    if (!change || change.mode === "keep") continue;
    if (change.mode === "clear") {
      if (!field.nullable) throw new Error(`${field.label} cannot be cleared.`);
      patch[field.key] = null;
      continue;
    }
    if (!change.value.trim())
      throw new Error(`Enter a value for ${field.label.toLowerCase()}.`);
    if (field.type === "number") {
      const value = Number(change.value);
      if (!Number.isFinite(value))
        throw new Error(`${field.label} must be a number.`);
      patch[field.key] = value;
    } else if (field.type === "boolean") {
      if (change.value !== "true" && change.value !== "false")
        throw new Error(`${field.label} must be Yes or No.`);
      patch[field.key] = change.value === "true";
    } else patch[field.key] = change.value;
  }
  if (!Object.keys(patch).length)
    throw new Error("Choose at least one field to change.");
  return patch;
}
