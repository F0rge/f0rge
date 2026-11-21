import { apiFetch } from "./api";

export type WorkspaceResource =
  | "skus"
  | "customers"
  | "suppliers"
  | "price-lists"
  | "locations"
  | "users"
  | "roles"
  | "accounts"
  | "repeating-invoices"
  | "proformas"
  | "quotes"
  | "payments"
  | "bills";
export type WorkspaceValue = string | number | boolean | null;
export type WorkspaceOperator =
  | "eq"
  | "ne"
  | "contains"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "empty"
  | "not_empty";
export interface WorkspaceFilter {
  field: string;
  operator: WorkspaceOperator;
  value: WorkspaceValue;
}
export interface WorkspaceQuery {
  q: string;
  lifecycle: "active" | "archived" | "all";
  match: "all" | "any";
  filters: WorkspaceFilter[];
  sort: { field: string; direction: "asc" | "desc" };
  limit: number;
  offset: number;
}
export interface WorkspacePage<T> {
  items: T[];
  total: number;
  counts: { active: number; archived: number };
  revisions: Record<string, string>;
  selection_token: string | null;
  selection_count: number;
  selection_ids: string[];
  bulk_available: boolean;
}
export type WorkspaceAction =
  | "edit"
  | "archive"
  | "restore"
  | "delete"
  | "disable"
  | "enable"
  | "pause"
  | "resume";
export interface WorkspaceSelection {
  ids?: string[];
  selection_token?: string;
  excluded_ids?: string[];
  revisions?: Record<string, string>;
}
export interface WorkspacePreflightRequest extends WorkspaceSelection {
  action: WorkspaceAction;
  patch?: Record<string, WorkspaceValue>;
}
export interface WorkspacePreflight {
  preflight_token: string;
  eligible: { id: string; label: string; warnings?: string[] }[];
  blocked: { id: string; label: string; reason: string; warnings?: string[]; dependencies?: { id: string; label: string }[] }[];
  eligible_count: number;
  blocked_count: number;
}
export interface WorkspaceExecution {
  request_id: string;
  succeeded: string[];
  failed: { id: string; reason: string }[];
  replayed: boolean;
}

export function queryWorkspace<T>(
  resource: WorkspaceResource,
  query: WorkspaceQuery,
  signal?: AbortSignal,
): Promise<WorkspacePage<T>> {
  return apiFetch(`/record-workspaces/${resource}/query`, {
    method: "POST",
    body: JSON.stringify(query),
    signal,
  });
}
export function preflightWorkspace(
  resource: WorkspaceResource,
  request: WorkspacePreflightRequest,
): Promise<WorkspacePreflight> {
  return apiFetch(`/record-workspaces/${resource}/preflight`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}
export function executeWorkspace(
  resource: WorkspaceResource,
  preflight_token: string,
  request_id: string,
): Promise<WorkspaceExecution> {
  return apiFetch(`/record-workspaces/${resource}/execute`, {
    method: "POST",
    body: JSON.stringify({ preflight_token, request_id }),
  });
}
