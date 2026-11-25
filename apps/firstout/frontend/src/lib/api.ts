import type { components } from "./generated/api-schema";
import { localIsoDate } from "./dates";
import { staffFetch } from "./staff-fetch";
import { downloadApiFile } from "./download";
import {
  normalizePick,
  normalizePickList,
  normalizePickSettings,
  normalizePreview,
  type CreatePickPayload,
  type PickDefaultAllocations,
  type PickDocument,
  type PickPreview,
  type UpdatePickPayload,
} from "./picks";

/** Server shapes, generated from the backend's OpenAPI document (`npm run codegen:api`). */
type Schema = components["schemas"];
/** A server `str` field whose values the UI relies on; the backend types it as plain str. */
type WithLiteral<T, K extends keyof T, V extends T[K]> = Omit<T, K> & { [P in K]: V };

export type PresetRole = "owner" | "buyer" | "warehouse" | "till" | "books";
/** Role slug — five presets plus custom slugs from GET /roles. */
export type UserRole = string;

export type Team = Schema["TeamBrief"];

export type AuthUser = Schema["MeResponse"];

export type User = Schema["UserResponse"];

export type Role = Schema["RoleResponse"];

export type RoleCreatePayload = Schema["RoleCreate"];

export type RoleUpdatePayload = Schema["RoleUpdate"];

export type UpdateUserPayload = Schema["UserUpdate"];

export type UpdateProfilePayload = Schema["ProfileUpdate"];

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** The `code` of a 409 the server explained with `{ code, message, ... }`; null for any other failure. */
export function conflictCode(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const detail = error.detail;
  return detail && typeof detail === "object" && "code" in detail && typeof detail.code === "string"
    ? detail.code
    : null;
}

export type Page<T> = { items: T[]; total: number };
export const PAGE_SIZES = [10, 25, 50] as const;
export type ListParams = {
  limit?: number;
  offset?: number;
  q?: string;
  status?: string;
  invoice_id?: string;
  bill_id?: string;
  needs_skus?: boolean;
};

function buildListQuery(params?: ListParams): string {
  const search = new URLSearchParams();
  search.set("limit", String(params?.limit ?? 50));
  search.set("offset", String(params?.offset ?? 0));
  const q = params?.q?.trim();
  if (q) {
    search.set("q", q);
  }
  const status = params?.status?.trim();
  if (status) {
    search.set("status", status);
  }
  if (params?.invoice_id) {
    search.set("invoice_id", params.invoice_id);
  }
  if (params?.bill_id) {
    search.set("bill_id", params.bill_id);
  }
  if (params?.needs_skus) {
    search.set("needs_skus", "true");
  }
  return search.toString();
}

const TIMEOUT_STATUSES = new Set([408, 499, 504]);

export function callName(method: string, path: string): string {
  const route = (path.split("?")[0] || path).replace(/^\/api\/v1/, "") || path;
  return `${method.toUpperCase()} ${route}`;
}

export function isTimeoutStatus(status: number): boolean {
  return TIMEOUT_STATUSES.has(status);
}

export function isTimeoutError(error: unknown): boolean {
  if (!error || typeof error !== "object") {
    return false;
  }
  const name = "name" in error ? String(error.name) : "";
  const message = "message" in error ? String(error.message) : "";
  return name === "AbortError" || name === "TimeoutError" || /timed?\s*out/i.test(message);
}

export function formatTransportError(call: string, error: unknown): string {
  if (isTimeoutError(error)) {
    return `${call} timed out`;
  }
  return `${call} failed`;
}

export function formatHttpError(
  call: string,
  status: number,
  statusText: string,
  detail: string,
): string {
  if (
    isTimeoutStatus(status) ||
    /timed?\s*out/i.test(detail) ||
    /timed?\s*out/i.test(statusText)
  ) {
    return `${call} timed out`;
  }
  const trimmed = detail.trim();
  const generic =
    !trimmed ||
    trimmed === "Request failed" ||
    trimmed === statusText ||
    trimmed.toLowerCase() === "internal server error";
  if (generic) {
    return status ? `${call} failed (${status})` : `${call} failed`;
  }
  return trimmed;
}

function detailMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: unknown } | undefined;
    if (first && typeof first.msg === "string") {
      return first.msg;
    }
  }
  if (detail && typeof detail === "object" && "code" in detail) {
    const coded = detail as { code?: unknown; message?: unknown };
    const code = coded.code;
    if (code === "document_llm_unconfigured") {
      return "Document reading is not configured. Add the OpenRouter key on the API.";
    }
    if (typeof coded.message === "string" && coded.message.trim()) {
      return coded.message;
    }
    if (typeof code === "string") {
      return code;
    }
  }
  return fallback;
}

function payloadDetail(body: unknown): unknown {
  if (body && typeof body === "object" && !Array.isArray(body) && "detail" in body) {
    return (body as { detail: unknown }).detail;
  }
  return undefined;
}

async function readErrorPayload(
  response: Response,
): Promise<{ message: string; detail: unknown }> {
  const fallback = response.statusText || "Request failed";
  try {
    const body: unknown = await response.json();
    const detail = payloadDetail(body);
    return { message: detailMessage(detail, fallback), detail };
  } catch {
    return { message: fallback, detail: undefined };
  }
}

export async function parseErrorMessage(response: Response): Promise<string> {
  const payload = await readErrorPayload(response);
  return payload.message;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const call = callName(options.method ?? "GET", path);

  let response: Response;
  try {
    response = await staffFetch(`/api/v1${path}`, {
      ...options,
      credentials: "include",
      headers,
    });
  } catch (error) {
    throw new ApiError(0, formatTransportError(call, error));
  }

  if (!response.ok) {
    const payload = await readErrorPayload(response);
    throw new ApiError(
      response.status,
      formatHttpError(call, response.status, response.statusText, payload.message),
      payload.detail,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}

export function getMe(): Promise<AuthUser> {
  return apiFetch<AuthUser>("/auth/me");
}

export function listUsers(): Promise<User[]> {
  return apiFetch<User[]>("/users");
}

export function updateUser(id: string, payload: UpdateUserPayload): Promise<User> {
  return apiFetch<User>(`/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function listRoles(): Promise<Role[]> {
  return apiFetch<Role[]>("/roles");
}

export function createRole(payload: RoleCreatePayload): Promise<Role> {
  return apiFetch<Role>("/roles", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateRole(id: string, payload: RoleUpdatePayload): Promise<Role> {
  return apiFetch<Role>(`/roles/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteRole(id: string): Promise<void> {
  return apiFetch<void>(`/roles/${id}`, { method: "DELETE" });
}

export function updateProfile(payload: UpdateProfilePayload): Promise<AuthUser> {
  return apiFetch<AuthUser>("/profile", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export const USER_ROLES: { value: PresetRole; label: string }[] = [
  { value: "owner", label: "Owner" },
  { value: "buyer", label: "Buyer" },
  { value: "warehouse", label: "Warehouse" },
  { value: "till", label: "Till" },
  { value: "books", label: "Books" },
];

export {
  displayPrice,
  exVatToIncVat,
  formatFxGainLoss,
  formatPriceAmount,
  formatZarAmount,
  incVatToExVat,
  parsePriceInput,
  roundHalfUp,
  vatPercentLabel,
} from "./money";

export {
  can,
  canManageCustomerCredit,
  canManageLocations,
  canMutateBooks,
  canMutateCatalogue,
  canMutateCustomers,
  canMutateDeliveries,
  canMutateLaybys,
  canMutateOrders,
  canMutatePicks,
  canMutateQuotes,
  canMutateReturns,
  canMutateSettings,
  canManageUsers,
  canRaisePo,
  canReceive,
  canReceiveTransfer,
  canTransfer,
  canUseTill,
  canViewCostAudit,
  hasPermission,
} from "./permissions";

export type {
  CreatePickPayload,
  PickAllocation,
  PickDefaultAllocations,
  PickDocument,
  PickLine,
  PickPreview,
  PickPreviewLine,
  PickStatus,
  UpdatePickPayload,
} from "./picks";

export type LocationType = Schema["LocationType"];

export type Location = Schema["LocationResponse"];

export type CreateLocationPayload = Schema["LocationCreate"];

export type UpdateLocationPayload = Schema["LocationUpdate"];

export function listLocations(): Promise<Location[]> {
  return apiFetch<Location[]>("/locations");
}

export function createLocation(payload: CreateLocationPayload): Promise<Location> {
  return apiFetch<Location>("/locations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateLocation(id: string, payload: UpdateLocationPayload): Promise<Location> {
  return apiFetch<Location>(`/locations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export const LOCATION_TYPES: { value: LocationType; label: string }[] = [
  { value: "warehouse", label: "Warehouse" },
  { value: "showroom", label: "Showroom" },
];

export function isActiveLocation(loc: Location): boolean {
  return !loc.is_archived;
}

export type LocationBin = Schema["LocationBinResponse"];

export type CreateLocationBinPayload = Schema["BinCreate"];

export type LocationBinGridPayload = Schema["BinGridCreate"];

export type UpdateLocationBinPayload = Schema["BinUpdate"];

export type InventoryBinOnHand = Schema["BinOnHandResponse"];

export function listLocationBins(locationId: string): Promise<LocationBin[]> {
  return apiFetch<LocationBin[]>(`/locations/${locationId}/bins`);
}

export function createLocationBin(
  locationId: string,
  payload: CreateLocationBinPayload,
): Promise<LocationBin> {
  return apiFetch<LocationBin>(`/locations/${locationId}/bins`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function generateLocationBinGrid(
  locationId: string,
  payload: LocationBinGridPayload,
): Promise<LocationBin[]> {
  return apiFetch<LocationBin[]>(`/locations/${locationId}/bins/grid`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateLocationBin(
  locationId: string,
  binId: string,
  payload: UpdateLocationBinPayload,
): Promise<LocationBin> {
  return apiFetch<LocationBin>(`/locations/${locationId}/bins/${binId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const call = callName("POST", path);
  let response: Response;
  try {
    response = await staffFetch(`/api/v1${path}`, {
      method: "POST",
      credentials: "include",
      body: formData,
    });
  } catch (error) {
    throw new ApiError(0, formatTransportError(call, error));
  }

  if (!response.ok) {
    const payload = await readErrorPayload(response);
    throw new ApiError(
      response.status,
      formatHttpError(call, response.status, response.statusText, payload.message),
      payload.detail,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export type Supplier = Schema["SupplierResponse"];

export type CreateSupplierPayload = Schema["SupplierCreate"];

export type ArchiveCounts = Schema["PartyArchiveCounts"];

export function listSuppliers(filters?: { archived?: boolean }): Promise<Supplier[]> {
  const query = typeof filters?.archived === "boolean" ? `?archived=${filters.archived}` : "";
  return apiFetch<Supplier[]>(`/suppliers${query}`);
}

export function getSupplierArchiveCounts(): Promise<ArchiveCounts> {
  return apiFetch<ArchiveCounts>("/suppliers/archive-counts");
}

export function setSupplierArchived(id: string, isArchived: boolean): Promise<Supplier> {
  return apiFetch<Supplier>(`/suppliers/${id}/archive`, {
    method: "PATCH",
    body: JSON.stringify({ is_archived: isArchived }),
  });
}

export function createSupplier(payload: CreateSupplierPayload): Promise<Supplier> {
  return apiFetch<Supplier>("/suppliers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type PriceListItem = Schema["PriceListItemResponse"];

export type PriceList = Schema["PriceListResponse"];

export type CreatePriceListPayload = Schema["PriceListCreate"];

export type UpdatePriceListPayload = Schema["PriceListUpdate"];

export type UpsertPriceListItemPayload = Schema["PriceListItemUpsert"];

export function listPriceLists(): Promise<PriceList[]> {
  return apiFetch<PriceList[]>("/price-lists");
}

export function createPriceList(payload: CreatePriceListPayload): Promise<PriceList> {
  return apiFetch<PriceList>("/price-lists", {
    method: "POST",
    body: JSON.stringify({ ...payload, name: payload.name.trim() }),
  });
}

export function updatePriceList(id: string, payload: UpdatePriceListPayload): Promise<PriceList> {
  return apiFetch<PriceList>(`/price-lists/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ ...payload, name: payload.name.trim() }),
  });
}

export function deletePriceList(id: string): Promise<void> {
  return apiFetch<void>(`/price-lists/${id}`, {
    method: "DELETE",
  });
}

export function upsertPriceListItem(
  priceListId: string,
  payload: UpsertPriceListItemPayload,
): Promise<PriceList> {
  return apiFetch<PriceList>(`/price-lists/${priceListId}/items`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deletePriceListItem(priceListId: string, skuId: string): Promise<PriceList> {
  return apiFetch<PriceList>(`/price-lists/${priceListId}/items/${skuId}`, {
    method: "DELETE",
  });
}

export type Proforma = Schema["ProformaResponse"];

export type CreateProformaPayload = {
  supplier_id: string;
  invoice_number: string;
  invoice_date: string;
  currency?: string;
  file: File;
};

export function listProformas(): Promise<Proforma[]> {
  return apiFetch<Proforma[]>("/proformas");
}

export function createProforma(payload: CreateProformaPayload): Promise<Proforma> {
  const formData = new FormData();
  formData.append("supplier_id", payload.supplier_id);
  formData.append("invoice_number", payload.invoice_number);
  formData.append("invoice_date", payload.invoice_date);
  if (payload.currency) {
    formData.append("currency", payload.currency);
  }
  formData.append("file", payload.file);
  return apiUpload<Proforma>("/proformas", formData);
}

export async function downloadProformaPdf(id: string, invoiceNumber: string): Promise<void> {
  await downloadApiFile(`/api/v1/proformas/${id}/file`, `${invoiceNumber}.pdf`);
}

export type IntakeFlag = Schema["ReviewFlag"];

export type IntakeSupplierMatch = Schema["SupplierMatchOut"];

export type IntakeSkuMatch = Schema["SkuMatchOut"];

export type IntakeCharge = Schema["ChargeOut"];

export type IntakeReviewedLine = Schema["ReviewedLine"];

export type ProformaReview = Schema["ProformaReview"];

export type ProformaConfirmLine = {
  supplier_code?: string | null;
  description: string;
  qty: number;
  unit_price: string;
  discount_percent?: string | null;
  vat_rate?: string | null;
  sku_id?: string | null;
  skip: boolean;
};

export type ProformaConfirmPayload = {
  supplier_id?: string | null;
  create_supplier?: {
    name: string;
    vat_number?: string | null;
    address?: string | null;
    default_currency?: string | null;
  } | null;
  document_number: string;
  document_date: string;
  currency: string;
  payment_terms?: string | null;
  deposit?: string | null;
  vat_total?: string | null;
  total?: string | null;
  charges: { description: string; amount: string }[];
  lines: ProformaConfirmLine[];
  submit_for_approval?: boolean;
};

export type ProformaConfirmResult = Schema["ProformaConfirmResponse"];

export function extractProforma(file: File): Promise<ProformaReview> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload<ProformaReview>("/document-intake/proformas/extract", formData);
}

export function confirmProforma(
  file: File,
  payload: ProformaConfirmPayload,
): Promise<ProformaConfirmResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("payload", JSON.stringify(payload));
  return apiUpload<ProformaConfirmResult>("/document-intake/proformas/confirm", formData);
}

export type SkuSuggestion = Schema["SkuSuggestion"];

export function suggestIntakeSku(payload: {
  description: string;
  supplier_code?: string | null;
  unit_price?: string | null;
  currency?: string | null;
  vat_rate?: string | null;
  hint?: string | null;
  supplier_id?: string | null;
}): Promise<SkuSuggestion> {
  return apiFetch<SkuSuggestion>("/document-intake/sku-suggestions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createIntakeSku(payload: {
  our_ref: string;
  our_barcode: string;
  name: string;
  design: string;
  fabric: string;
  supplier_ref?: string | null;
  category?: string | null;
  supplier_id: string;
  supplier_sku?: string | null;
  latest_price?: string | null;
}): Promise<{ sku: Sku; supplier_price_id: string }> {
  return apiFetch("/document-intake/skus", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type Sku = Schema["SkuResponse"];
export type WorkspaceSkuRow = Schema["WorkspaceSkuRow"];

export type SkuProductDetails = Partial<
  Pick<Sku, "width_cm" | "depth_cm" | "height_cm" | "diameter_cm" | "piece_count" | "notes">
>;

export type UpdateSkuPricePayload = Schema["SkuUpdate"];

export type SkuPricePreviewRequest = Schema["SkuPricePreviewRequest"];
export type SkuPricePreviewResponse = Schema["SkuPricePreviewResponse"];

export type CreateSkuPayload = Schema["SkuCreate"];

export type SkuListParams = {
  lifecycle?: "active" | "archived" | "all";
  limit?: number;
  offset?: number;
  q?: string;
  category?: string;
  preferred_supplier_id?: string;
};

export type SkuListPage = Schema["SkuListPage"];

export type SkuUnitCost = Schema["SkuUnitCostItem"];

function skuListQuery(options?: SkuListParams): string {
  const params = new URLSearchParams();
  if (options?.lifecycle) params.set("lifecycle", options.lifecycle);
  if (options?.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  if (options?.offset) {
    params.set("offset", String(options.offset));
  }
  const q = options?.q?.trim();
  if (q) {
    params.set("q", q);
  }
  const category = options?.category?.trim();
  if (category) {
    params.set("category", category);
  }
  if (options?.preferred_supplier_id) {
    params.set("preferred_supplier_id", options.preferred_supplier_id);
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function listSkus(
  options?: Pick<SkuListParams, "category" | "q" | "preferred_supplier_id" | "lifecycle">,
): Promise<Sku[]> {
  return apiFetch<Sku[]>(`/skus${skuListQuery(options)}`);
}

export function listSkusPage(options: SkuListParams & { limit: number }): Promise<SkuListPage> {
  return apiFetch<SkuListPage>(`/skus${skuListQuery(options)}`);
}

export function listSkuUnitCosts(options?: SkuListParams): Promise<Page<SkuUnitCost>> {
  return apiFetch<Page<SkuUnitCost>>(`/skus/unit-costs${skuListQuery(options)}`);
}

export function getSku(id: string): Promise<Sku> {
  return apiFetch<Sku>(`/skus/${id}`);
}

export function createSku(payload: CreateSkuPayload): Promise<Sku> {
  const body: CreateSkuPayload = { ...payload };
  const barcode = body.our_barcode?.trim();
  if (barcode) {
    body.our_barcode = barcode;
  } else {
    delete body.our_barcode;
  }
  const category = body.category?.trim();
  if (category) {
    body.category = category;
  } else {
    delete body.category;
  }
  const openingDate = body.opening_date?.trim();
  if (openingDate) {
    body.opening_date = openingDate;
  } else {
    delete body.opening_date;
  }
  if (body.carton_count === undefined || body.carton_count < 1) {
    delete body.carton_count;
  }
  return apiFetch<Sku>("/skus", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function uploadSkuPhoto(id: string, photo: File): Promise<Sku> {
  const formData = new FormData();
  formData.append("photo", photo);
  return apiUpload<Sku>(`/skus/${id}/photo`, formData);
}

export function updateSku(id: string, payload: UpdateSkuPricePayload): Promise<Sku> {
  return apiFetch<Sku>(`/skus/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function previewSkuPrice(
  id: string,
  payload: SkuPricePreviewRequest,
  signal?: AbortSignal,
): Promise<SkuPricePreviewResponse> {
  return apiFetch<SkuPricePreviewResponse>(`/skus/${id}/price-preview`, {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export function deleteSku(id: string): Promise<void> {
  return apiFetch<void>(`/skus/${id}`, { method: "DELETE" });
}

export function skuPhotoUrl(id: string, slot?: number): string {
  return `/api/v1/skus/${id}/photo${slot ? `?slot=${slot}` : ""}`;
}

export type CuratedCatalogueResult = Schema["CuratedCatalogueResult"];
export type CuratedCatalogueScope = "catalogue" | "sku" | "photos";

export function uploadCuratedCatalogue(
  archive: File,
  dryRun: boolean,
  scope: CuratedCatalogueScope = "catalogue",
): Promise<CuratedCatalogueResult> {
  const form = new FormData();
  form.append("archive", archive);
  form.append("dry_run", String(dryRun));
  if (scope !== "catalogue") form.append("scope", scope);
  return apiUpload<CuratedCatalogueResult>("/skus/curated-catalogue", form);
}

export type SkuBomLine = Schema["SkuBomLineResponse"];

export type SkuBomLineWrite = Schema["SkuBomLineWrite"];

export type ReplaceSkuBomPayload = Schema["SkuBomReplace"];

export function listSkuBom(skuId: string): Promise<SkuBomLine[]> {
  return apiFetch<SkuBomLine[]>(`/skus/${skuId}/bom`);
}

export function replaceSkuBom(skuId: string, payload: ReplaceSkuBomPayload): Promise<SkuBomLine[]> {
  return apiFetch<SkuBomLine[]>(`/skus/${skuId}/bom`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export type CatalogueImportFileKind = "inventory" | "soh";

export type CatalogueImportError = Schema["CatalogueImportRowError"];

export type CatalogueImportInventoryPreview = Schema["CatalogueImportFilePreview"];

export type CatalogueImportSohPreview = Schema["CatalogueImportSohPreview"];

export type CatalogueImportPreview = Schema["CatalogueImportPreviewResponse"];

export type CatalogueImportCommit = Schema["CatalogueImportCommitResponse"];

export function previewCatalogueImport(formData: FormData): Promise<CatalogueImportPreview> {
  return apiUpload<CatalogueImportPreview>("/imports/preview", formData);
}

export function commitCatalogueImport(formData: FormData): Promise<CatalogueImportCommit> {
  return apiUpload<CatalogueImportCommit>("/imports/commit", formData);
}


export type PurchaseOrderStatus = Schema["PurchaseOrderStatus"];

export type PoLine = Schema["PoLineResponse"];

export type LandingBill = Schema["LandingBillResponse"];

export type PurchaseOrderListItem = WithLiteral<
  Schema["PurchaseOrderListItem"],
  "status",
  PurchaseOrderStatus
>;

export type PurchaseOrder = WithLiteral<Schema["PurchaseOrderResponse"], "status", PurchaseOrderStatus>;

export type CreatePoLinePayload = Schema["PoLineCreate"];

export type CreatePurchaseOrderPayload = Schema["PurchaseOrderCreate"];

export type PurchaseOrderLineWrite = Schema["PoLineWrite"];

export type PurchaseOrderLinesUpdate = Schema["PurchaseOrderLinesUpdate"];

export type PoLineSkuCreate = Schema["PoLineSkuCreate"];

export type InventorySku = Schema["InventorySkuResponse"];

export const PO_STATUS_LABELS: Record<PurchaseOrderStatus, string> = {
  pending_approval: "Pending approval",
  rejected: "Rejected",
  open: "Open",
  on_water: "On water",
  landed: "Landed",
  received: "Received",
};

export type TillTender = Schema["TillSaleCreate"]["tender"];

export type TillSaleLinePayload = Schema["TillSaleLineCreate"];

export type HeldSaleCreate = Schema["HeldSaleCreate"];

/** The signed-in user's open till basket for one showroom. */
export type TillBasket = Schema["TillBasket"];

/** The soonest-freeing reservation on a SKU; names the showroom, never the person. */
export type TillBlockingReservation = Schema["BlockingReservation"];

/** Stock reserved by holders other than the caller's own basket. */
export type TillReservation = Schema["TillReservation"];

export function listTillReservations(locationId: string, signal?: AbortSignal): Promise<TillReservation[]> {
  return apiFetch(`/till/reservations?location_id=${encodeURIComponent(locationId)}`, { signal });
}

/** Whole-basket replace; a stale version is rejected with basket_version_conflict. */
export type TillBasketUpdate = Schema["TillBasketUpdate"];

export function getTillBasket(locationId: string): Promise<TillBasket> {
  return apiFetch(`/till/basket?location_id=${encodeURIComponent(locationId)}`);
}

export function updateTillBasket(id: string, payload: TillBasketUpdate): Promise<TillBasket> {
  return apiFetch(`/till/basket/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export type HeldSale = Schema["HeldSale"];

export type HeldSaleResume = Schema["HeldSaleResume"];

export function listHeldSales(locationId: string, signal?: AbortSignal): Promise<HeldSale[]> {
  return apiFetch(`/till/held-sales?location_id=${encodeURIComponent(locationId)}`, { signal });
}

export function holdTillSale(payload: HeldSaleCreate): Promise<HeldSale> {
  return apiFetch("/till/held-sales", { method: "POST", body: JSON.stringify(payload) });
}

export function updateHeldSaleNote(id: string, locationId: string, version: number, note: string | null): Promise<HeldSale> {
  return apiFetch(`/till/held-sales/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ location_id: locationId, version, note }),
  });
}

export function resumeTillHeldSale(id: string, payload: HeldSaleResume): Promise<{
  resumed_id: string;
  held_current_id: string | null;
  basket?: TillBasket;
}> {
  return apiFetch(`/till/held-sales/${id}/resume`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteTillHeldSales(locationId: string, ids: string[], all: boolean): Promise<{
  deleted_count: number;
}> {
  return apiFetch("/till/held-sales/delete", {
    method: "POST",
    body: JSON.stringify({ location_id: locationId, ids, all }),
  });
}

export type TillPriceRequest = Schema["TillPriceRequest"];

// The server's Sale line pricing preview, shared by the till, quotes, invoices and laybys.
export type SalePricePreview = Schema["SalePricePreview"];

export type SaleLinePrice = Schema["SaleLinePrice"];

export type TillSalePayload = Schema["TillSaleCreate"];

export type TillSaleResult = Schema["TillSaleResponse"];

export function previewTillPrices(payload: TillPriceRequest, signal: AbortSignal): Promise<SalePricePreview> {
  return apiFetch<SalePricePreview>("/till/price-preview", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export function createTillSale(payload: TillSalePayload): Promise<TillSaleResult> {
  return apiFetch<TillSaleResult>("/till/sales", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listPurchaseOrders(params?: ListParams): Promise<Page<PurchaseOrderListItem>> {
  return apiFetch<Page<PurchaseOrderListItem>>(`/purchase-orders?${buildListQuery(params)}`);
}

export function createPurchaseOrder(payload: CreatePurchaseOrderPayload): Promise<PurchaseOrder> {
  return apiFetch<PurchaseOrder>("/purchase-orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updatePurchaseOrderLines(
  id: string,
  payload: PurchaseOrderLinesUpdate,
): Promise<PurchaseOrder> {
  return apiFetch<PurchaseOrder>(`/purchase-orders/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function createPurchaseOrderLineSku(
  poId: string,
  lineId: string,
  payload: PoLineSkuCreate,
): Promise<PurchaseOrder> {
  return apiFetch<PurchaseOrder>(`/purchase-orders/${poId}/lines/${lineId}/sku`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getPurchaseOrder(id: string): Promise<PurchaseOrder> {
  return apiFetch<PurchaseOrder>(`/purchase-orders/${id}`);
}

export async function downloadPackingSheet(id: string, poNumber: string): Promise<void> {
  await downloadApiFile(`/api/v1/purchase-orders/${id}/packing-sheet`, `${poNumber}-packing-sheet.pdf`);
}

export async function downloadPurchaseOrder(id: string, poNumber: string): Promise<void> {
  await downloadApiFile(`/api/v1/purchase-orders/${id}/pdf`, `${poNumber}.pdf`);
}

export function markOnWater(id: string): Promise<PurchaseOrder> {
  return apiFetch<PurchaseOrder>(`/purchase-orders/${id}/on-water`, {
    method: "POST",
  });
}

export function landPurchaseOrder(id: string, formData: FormData): Promise<PurchaseOrder> {
  return apiUpload<PurchaseOrder>(`/purchase-orders/${id}/land`, formData);
}

export function approvePurchaseOrder(id: string): Promise<PurchaseOrder> {
  return apiFetch<PurchaseOrder>(`/purchase-orders/${id}/approve`, {
    method: "POST",
  });
}

export function rejectPurchaseOrder(id: string): Promise<PurchaseOrder> {
  return apiFetch<PurchaseOrder>(`/purchase-orders/${id}/reject`, {
    method: "POST",
  });
}

export function receivePurchaseOrder(payload: {
  purchase_order_id: string;
  location_id: string;
  bin_id?: string;
}): Promise<void> {
  const body: {
    purchase_order_id: string;
    location_id: string;
    bin_id?: string;
  } = {
    purchase_order_id: payload.purchase_order_id,
    location_id: payload.location_id,
  };
  const binId = payload.bin_id?.trim();
  if (binId) {
    body.bin_id = binId;
  }
  return apiFetch<void>("/receive", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listInventory(): Promise<InventorySku[]> {
  return apiFetch<InventorySku[]>("/inventory");
}

export type TransferStatus = Schema["TransferStatus"];

export type TransferLine = Schema["TransferLineResponse"];

export type Transfer = Schema["TransferResponse"];

export type TransferLinePayload = Schema["TransferLineCreate"];

export type CreateTransferPayload = Schema["TransferCreate"];

export type TransferReceivePayload = Schema["TransferReceive"];

export const TRANSFER_STATUS_LABELS: Record<TransferStatus, string> = {
  draft: "Draft",
  in_transit: "In transit",
  received: "Received",
  cancelled: "Cancelled",
};

export function listTransfers(options?: {
  status?: TransferStatus;
  to_location_id?: string;
}): Promise<Transfer[]> {
  const params = new URLSearchParams();
  if (options?.status) {
    params.set("status", options.status);
  }
  const toLocationId = options?.to_location_id?.trim();
  if (toLocationId) {
    params.set("to_location_id", toLocationId);
  }
  const qs = params.toString();
  return apiFetch<Transfer[]>(`/transfers${qs ? `?${qs}` : ""}`);
}

export function getTransfer(id: string): Promise<Transfer> {
  return apiFetch<Transfer>(`/transfers/${id}`);
}

export function createTransfer(payload: CreateTransferPayload): Promise<Transfer> {
  const notes = payload.notes?.trim();
  const body: CreateTransferPayload = {
    from_location_id: payload.from_location_id,
    to_location_id: payload.to_location_id,
    lines: payload.lines.map((line) => {
      const next: TransferLinePayload = { sku_id: line.sku_id, qty: line.qty };
      const fromBin = line.from_bin_id?.trim();
      if (fromBin) {
        next.from_bin_id = fromBin;
      }
      const toBin = line.to_bin_id?.trim();
      if (toBin) {
        next.to_bin_id = toBin;
      }
      return next;
    }),
  };
  if (notes) {
    body.notes = notes;
  }
  return apiFetch<Transfer>("/transfers", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function dispatchTransfer(id: string): Promise<Transfer> {
  return apiFetch<Transfer>(`/transfers/${id}/dispatch`, { method: "POST" });
}

export function receiveTransfer(id: string, payload: TransferReceivePayload): Promise<Transfer> {
  return apiFetch<Transfer>(`/transfers/${id}/receive`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function cancelTransfer(id: string): Promise<Transfer> {
  return apiFetch<Transfer>(`/transfers/${id}/cancel`, { method: "POST" });
}

export async function downloadTransferPdf(id: string, transferNumber: string): Promise<void> {
  await downloadApiFile(`/api/v1/transfers/${id}/pdf`, `${transferNumber}.pdf`);
}

export function listPicks(sourceType?: string): Promise<PickDocument[]> {
  const query = sourceType ? `?source_type=${encodeURIComponent(sourceType)}` : "";
  return apiFetch<unknown>(`/picks${query}`).then(normalizePickList);
}

export function getPick(id: string): Promise<PickDocument> {
  return apiFetch<unknown>(`/picks/${id}`).then(normalizePick);
}

export function getPickDefaultAllocations(id: string): Promise<PickDefaultAllocations> {
  return apiFetch<PickDefaultAllocations>(`/picks/${id}/default-allocations`);
}

export function previewPick(payload: { sku_id: string; qty: number }): Promise<PickPreview> {
  return apiFetch<unknown>("/picks/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  }).then(normalizePreview);
}

export function createPick(payload: CreatePickPayload): Promise<PickDocument> {
  return apiFetch<unknown>("/picks", {
    method: "POST",
    body: JSON.stringify(payload),
  }).then(normalizePick);
}

export function updatePick(id: string, payload: UpdatePickPayload): Promise<PickDocument> {
  return apiFetch<unknown>(`/picks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }).then(normalizePick);
}

export function confirmPick(id: string, confirmSplit?: boolean): Promise<PickDocument> {
  const body: { confirm_split?: boolean } = {};
  if (confirmSplit) {
    body.confirm_split = true;
  }
  return apiFetch<unknown>(`/picks/${id}/confirm`, {
    method: "POST",
    body: JSON.stringify(body),
  }).then(normalizePick);
}

export function completePick(
  id: string,
  payload: { staging_location_id?: string; collect_from_showroom?: boolean } = {},
): Promise<PickDocument> {
  const body: { staging_location_id?: string; collect_from_showroom?: boolean } = {};
  if (payload.staging_location_id) {
    body.staging_location_id = payload.staging_location_id;
  }
  if (payload.collect_from_showroom) {
    body.collect_from_showroom = true;
  }
  return apiFetch<unknown>(`/picks/${id}/complete`, {
    method: "POST",
    body: JSON.stringify(body),
  }).then(normalizePick);
}

export function cancelPick(id: string): Promise<PickDocument> {
  return apiFetch<unknown>(`/picks/${id}/cancel`, { method: "POST" }).then(normalizePick);
}

export async function downloadPickPdf(id: string, _pickNumber: string): Promise<void> {
  await downloadApiFile(`/api/v1/picks/${id}/pdf`, `${_pickNumber}.pdf`, "open");
}

export type StocktakeStatus = Schema["StocktakeStatus"];

export type StocktakeLine = Schema["StocktakeLineResponse"];

export type StocktakeSummary = Schema["StocktakeResponse"];

export type Stocktake = Schema["StocktakeResponse"];

export const STOCKTAKE_STATUS_LABELS: Record<StocktakeStatus, string> = {
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
};

export function listStocktakes(): Promise<StocktakeSummary[]> {
  return apiFetch<StocktakeSummary[]>("/stocktakes");
}

export function startStocktake(payload: {
  location_id: string;
  category?: string;
}): Promise<Stocktake> {
  const category = payload.category?.trim();
  const body: { location_id: string; category?: string } = { location_id: payload.location_id };
  if (category) {
    body.category = category;
  }
  return apiFetch<Stocktake>("/stocktakes", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getStocktake(id: string): Promise<Stocktake> {
  return apiFetch<Stocktake>(`/stocktakes/${id}`);
}

export function patchStocktakeLine(
  stocktakeId: string,
  lineId: string,
  payload: { counted_qty: number },
): Promise<StocktakeLine> {
  return apiFetch<StocktakeLine>(`/stocktakes/${stocktakeId}/lines/${lineId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function lookupStocktakeBarcode(
  stocktakeId: string,
  payload: { barcode: string },
): Promise<StocktakeLine> {
  return apiFetch<StocktakeLine>(`/stocktakes/${stocktakeId}/lookup`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function completeStocktake(id: string): Promise<Stocktake> {
  return apiFetch<Stocktake>(`/stocktakes/${id}/complete`, { method: "POST" });
}

export function cancelStocktake(id: string): Promise<Stocktake> {
  return apiFetch<Stocktake>(`/stocktakes/${id}/cancel`, { method: "POST" });
}

export type AdjustmentReason = Schema["StockAdjustmentReason"];

export type AdjustmentStatus = Schema["StockAdjustmentStatus"];

export type AdjustmentLine = Schema["StockAdjustmentLineResponse"];

export type AdjustmentSummary = Schema["StockAdjustmentResponse"];

export type Adjustment = Schema["StockAdjustmentResponse"];

export const ADJUSTMENT_REASON_LABELS: Record<AdjustmentReason, string> = {
  opening: "Opening Stock (Equity)",
  damage: "Damage / Breakage (Expense)",
  theft: "Theft / Shrinkage (Expense)",
  count_fix: "Count Fix (COGS)",
  write_off: "Write-off (Expense)",
};

export const ADJUSTMENT_REASONS: AdjustmentReason[] = [
  "opening",
  "damage",
  "theft",
  "count_fix",
  "write_off",
];

export const ADJUSTMENT_STATUS_LABELS: Record<AdjustmentStatus, string> = {
  draft: "Draft",
  completed: "Completed",
  cancelled: "Cancelled",
};

export type CreateAdjustmentPayload = Schema["StockAdjustmentCreate"];

export type CreateAdjustmentLinePayload = Schema["StockAdjustmentLineCreate"];

export function listAdjustments(): Promise<AdjustmentSummary[]> {
  return apiFetch<AdjustmentSummary[]>("/adjustments");
}

export function createAdjustment(payload: CreateAdjustmentPayload): Promise<Adjustment> {
  const notes = payload.notes?.trim();
  const body: CreateAdjustmentPayload = {
    location_id: payload.location_id,
    reason: payload.reason,
  };
  if (notes) {
    body.notes = notes;
  }
  return apiFetch<Adjustment>("/adjustments", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getAdjustment(id: string): Promise<Adjustment> {
  return apiFetch<Adjustment>(`/adjustments/${id}`);
}

export function addAdjustmentLine(
  adjustmentId: string,
  payload: CreateAdjustmentLinePayload,
): Promise<AdjustmentLine> {
  const cost = payload.unit_cost_zar == null ? "" : String(payload.unit_cost_zar).trim();
  const body: CreateAdjustmentLinePayload = {
    sku_id: payload.sku_id,
    qty_delta: payload.qty_delta,
  };
  if (cost) {
    body.unit_cost_zar = cost;
  }
  return apiFetch<AdjustmentLine>(`/adjustments/${adjustmentId}/lines`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function patchAdjustmentLine(
  adjustmentId: string,
  lineId: string,
  payload: { qty_delta?: number; unit_cost_zar?: string },
): Promise<AdjustmentLine> {
  const body: { qty_delta?: number; unit_cost_zar?: string } = {};
  if (payload.qty_delta !== undefined) {
    body.qty_delta = payload.qty_delta;
  }
  const cost = payload.unit_cost_zar?.trim();
  if (cost) {
    body.unit_cost_zar = cost;
  }
  return apiFetch<AdjustmentLine>(`/adjustments/${adjustmentId}/lines/${lineId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteAdjustmentLine(adjustmentId: string, lineId: string): Promise<void> {
  return apiFetch<void>(`/adjustments/${adjustmentId}/lines/${lineId}`, { method: "DELETE" });
}

export function completeAdjustment(id: string): Promise<Adjustment> {
  return apiFetch<Adjustment>(`/adjustments/${id}/complete`, { method: "POST" });
}

export function cancelAdjustment(id: string): Promise<Adjustment> {
  return apiFetch<Adjustment>(`/adjustments/${id}/cancel`, { method: "POST" });
}

export type AccountType = Schema["AccountType"];

export type TaxTreatment = Schema["TaxTreatment"];

export type Account = Schema["AccountResponse"];

export type CreateAccountPayload = Schema["AccountCreate"];

export type UpdateAccountPayload = Schema["AccountUpdate"];

export const ACCOUNT_TYPES: { value: AccountType; label: string }[] = [
  { value: "asset", label: "Asset" },
  { value: "liability", label: "Liability" },
  { value: "equity", label: "Equity" },
  { value: "income", label: "Income" },
  { value: "expense", label: "Expense" },
];

export const TAX_TREATMENTS: { value: TaxTreatment; label: string }[] = [
  { value: "vat15", label: "VAT at the team's rate" },
  { value: "none", label: "None" },
];

export function defaultTaxTreatment(type: AccountType): TaxTreatment {
  return type === "income" || type === "expense" ? "vat15" : "none";
}

export function taxTreatmentLabel(value: TaxTreatment): string {
  return TAX_TREATMENTS.find((entry) => entry.value === value)?.label ?? value;
}

export function listAccounts(): Promise<Account[]> {
  return apiFetch<Account[]>("/accounts");
}

export function createAccount(payload: CreateAccountPayload): Promise<Account> {
  return apiFetch<Account>("/accounts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateAccount(id: string, payload: UpdateAccountPayload): Promise<Account> {
  return apiFetch<Account>(`/accounts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export type CategoryMap = Schema["CategoryAccountMapResponse"];

export type UpsertCategoryMapPayload = Schema["CategoryAccountMapUpsert"];

export function listCategoryMaps(): Promise<CategoryMap[]> {
  return apiFetch<CategoryMap[]>("/category-maps");
}

export function upsertCategoryMap(payload: UpsertCategoryMapPayload): Promise<CategoryMap> {
  return apiFetch<CategoryMap>("/category-maps", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export type InvoiceLine = Schema["InvoiceLineResponse"];

export type InvoiceListItem = Schema["InvoiceListItem"];

/** Where an invoice was made; Cin7 history is "imported". */
export type InvoiceSource = "till" | "manual" | "imported";
/** Settlement as filtered in the list; "unknown" for Cin7 history. */
export type InvoiceStatus = "paid" | "partially_paid" | "unpaid" | "on_statement" | "overdue" | "unknown";

export type Invoice = Schema["InvoiceResponse"];

export type CreateInvoiceLinePayload = Schema["InvoiceLineCreate"];

export type CreateInvoicePayload = Schema["ManualInvoiceCreate"];

export type InvoiceSummary = Schema["InvoiceSummary"];

export function getInvoiceSummary(): Promise<InvoiceSummary> {
  return apiFetch<InvoiceSummary>("/invoices/summary");
}

/** The invoice cart priced as creating it would: one preview line per request line, in order. */
export function previewInvoicePrices(
  payload: { customer_id: string; lines: CreateInvoiceLinePayload[] },
  signal: AbortSignal,
): Promise<SalePricePreview> {
  return apiFetch<SalePricePreview>("/invoices/preview", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

/** The invoices list for one customer, archived invoices included. */
export function customerInvoicesHref(customerName: string): string {
  const filters = [{ field: "customer_name", operator: "eq", value: customerName }];
  return `/invoices?lifecycle=all&filters=${encodeURIComponent(JSON.stringify(filters))}`;
}

export function invoiceAction(id: string, action: "archive" | "restore"): Promise<Invoice> {
  return apiFetch<Invoice>(`/invoices/${id}/${action}`, { method: "POST" });
}

export function listInvoices(params?: ListParams): Promise<Page<InvoiceListItem>> {
  return apiFetch<Page<InvoiceListItem>>(`/invoices?${buildListQuery(params)}`);
}

export function createInvoice(payload: CreateInvoicePayload): Promise<Invoice> {
  return apiFetch<Invoice>("/invoices", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getInvoice(id: string): Promise<Invoice> {
  return apiFetch<Invoice>(`/invoices/${id}`);
}

/** Longest printed or internal note the API accepts. */
export const INVOICE_NOTE_MAX = 2000;

/** Only the internal note changes after issue; blank clears it. */
export function updateInvoiceNote(id: string, noteInternal: string): Promise<Invoice> {
  return apiFetch<Invoice>(`/invoices/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ note_internal: noteInternal }),
  });
}

/** Credit the sale to a colleague (commission); null removes the colleague. */
export function updateInvoiceSalesStaff(id: string, salesStaffId: string | null): Promise<Invoice> {
  return apiFetch<Invoice>(`/invoices/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ sales_staff_id: salesStaffId }),
  });
}

export type SalesStaff = Schema["SalesStaffResponse"];

export type SalesStaffOption = Pick<SalesStaff, "id" | "name" | "short_name">;

export type SalesStaffPayload = Schema["SalesStaffCreate"];

export function listSalesStaff(status: "active" | "inactive" | "all" = "all"): Promise<SalesStaff[]> {
  return apiFetch<SalesStaff[]>(`/sales-staff?status=${status}`);
}

/** Active colleagues' names for the till and invoices (no rates). */
export function listSalesStaffOptions(): Promise<SalesStaffOption[]> {
  return apiFetch<SalesStaffOption[]>("/sales-staff/options");
}

export function createSalesStaff(payload: SalesStaffPayload): Promise<SalesStaff> {
  return apiFetch<SalesStaff>("/sales-staff", { method: "POST", body: JSON.stringify(payload) });
}

export function updateSalesStaff(id: string, payload: Schema["SalesStaffUpdate"]): Promise<SalesStaff> {
  return apiFetch<SalesStaff>(`/sales-staff/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

/** Only for a colleague no invoice or quote names (409 otherwise). */
export function deleteSalesStaff(id: string): Promise<void> {
  return apiFetch<void>(`/sales-staff/${id}`, { method: "DELETE" });
}

export type CommissionDocument = Schema["CommissionDocument"];

export type CommissionRow = Schema["CommissionRow"];

export type CommissionReport = Schema["CommissionReport"];

/** month: YYYY-MM. */
export function getCommissionReport(month: string): Promise<CommissionReport> {
  return apiFetch<CommissionReport>(`/reports/commission?month=${encodeURIComponent(month)}`);
}


export type RepeatingInvoiceLine = Schema["RepeatingInvoiceLineResponse"];

export type RepeatingInvoice = Schema["RepeatingInvoiceResponse"];

export type CreateRepeatingInvoicePayload = Schema["RepeatingInvoiceCreate"];

export type RepeatingInvoiceRun = Schema["RepeatingInvoiceRunResponse"];

export function listRepeatingInvoices(): Promise<RepeatingInvoice[]> {
  return apiFetch<RepeatingInvoice[]>("/repeating-invoices");
}

export function createRepeatingInvoice(
  payload: CreateRepeatingInvoicePayload,
): Promise<RepeatingInvoice> {
  return apiFetch<RepeatingInvoice>("/repeating-invoices", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runRepeatingInvoice(id: string): Promise<RepeatingInvoiceRun> {
  return apiFetch<RepeatingInvoiceRun>(`/repeating-invoices/${id}/run`, {
    method: "POST",
  });
}

export async function downloadInvoicePdf(id: string, invoiceNumber: string): Promise<void> {
  await downloadApiFile(`/api/v1/invoices/${id}/pdf`, `${invoiceNumber}.pdf`);
}

export type CreditNote = Schema["CreditNoteResponse"];

export type CreateCreditNotePayload = Schema["CreditNoteCreate"];

export function listCreditNotes(params?: ListParams): Promise<Page<CreditNote>> {
  return apiFetch<Page<CreditNote>>(`/credit-notes?${buildListQuery(params)}`);
}

export function createCreditNote(payload: CreateCreditNotePayload): Promise<CreditNote> {
  return apiFetch<CreditNote>("/credit-notes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function downloadCreditNotePdf(id: string, creditNoteNumber: string): Promise<void> {
  await downloadApiFile(`/api/v1/credit-notes/${id}/pdf`, `${creditNoteNumber}.pdf`);
}

export async function downloadLaybyPdf(id: string, laybyNumber: string): Promise<void> {
  await downloadApiFile(`/api/v1/laybys/${id}/pdf`, `${laybyNumber}.pdf`);
}

export type BillLine = Schema["BillLineResponse"];

export type BillApprovalStatus = "draft" | "awaiting_approval" | "approved";

/** Approval first, then settlement. Imported Cin7 bills are "unknown". */
export type BillStatus =
  | "draft"
  | "awaiting_approval"
  | "unpaid"
  | "partially_paid"
  | "overdue"
  | "paid"
  | "unknown";

export type BillAttachment = Schema["BillAttachmentResponse"];

export type BillListItem = Schema["BillListItem"];

export type Bill = Schema["BillResponse"];

export type BillSummary = Schema["BillSummary"];

export type CreateBillLinePayload = Schema["BillLineCreate"];

export type CreateBillPayload = Schema["BillCreate"];

export function createBill(payload: CreateBillPayload): Promise<Bill> {
  return apiFetch<Bill>("/bills", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getBill(id: string): Promise<Bill> {
  return apiFetch<Bill>(`/bills/${id}`);
}

export function getBillSummary(): Promise<BillSummary> {
  return apiFetch<BillSummary>("/bills/summary");
}

export function updateBill(
  id: string,
  payload: { due_date?: string; notes?: string | null },
): Promise<Bill> {
  return apiFetch<Bill>(`/bills/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function billAction(
  id: string,
  action: "submit" | "approve" | "archive" | "restore",
): Promise<Bill> {
  return apiFetch<Bill>(`/bills/${id}/${action}`, { method: "POST" });
}

export function uploadBillAttachment(id: string, file: File): Promise<Bill> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload<Bill>(`/bills/${id}/attachments`, formData);
}

export async function downloadBillAttachment(
  billId: string,
  attachment: BillAttachment,
): Promise<void> {
  await downloadApiFile(
    `/api/v1/bills/${billId}/attachments/${attachment.id}`,
    attachment.filename,
  );
}

export function deleteBillAttachment(billId: string, attachmentId: string): Promise<Bill> {
  return apiFetch<Bill>(`/bills/${billId}/attachments/${attachmentId}`, { method: "DELETE" });
}

export type PaymentDirection = "in" | "out";

export type PaymentMethod = "eft" | "card" | "cash" | "other";

export type Payment = Schema["PaymentResponse"];

type PaymentMethodPayload = {
  tender?: PaymentMethod;
  reference?: string;
};

export type CreatePaymentInPayload = PaymentMethodPayload & {
  direction: "in";
  invoice_id: string;
  amount: string;
  currency: "ZAR";
  paid_on: string;
};

export type CreatePaymentOutPayload = PaymentMethodPayload & {
  direction: "out";
  bill_id: string;
  amount: string;
  currency: string;
  fx_to_zar?: string;
  paid_on: string;
};

export type PaymentOpenDocument = Schema["PaymentOpenDocument"];

export type PaymentSummary = Schema["PaymentSummary"];

export function listOpenPaymentDocuments(
  direction: PaymentDirection,
): Promise<PaymentOpenDocument[]> {
  return apiFetch<PaymentOpenDocument[]>(`/payments/open-documents?direction=${direction}`);
}

export function getPaymentSummary(): Promise<PaymentSummary> {
  return apiFetch<PaymentSummary>("/payments/summary");
}

export function voidPayment(id: string, reason: string): Promise<Payment> {
  return apiFetch<Payment>(`/payments/${id}/void`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export type CreatePaymentPayload = Schema["PaymentCreate"];

export function listPayments(params?: ListParams): Promise<Page<Payment>> {
  return apiFetch<Page<Payment>>(`/payments?${buildListQuery(params)}`);
}

export type BooksDocumentType = Schema["BooksDocumentType"];

export type BooksEventAction = Schema["BooksEventAction"];

export type BooksEvent = Schema["BooksEventResponse"];

export function listBooksEvents(
  documentType: BooksDocumentType,
  documentId: string,
): Promise<BooksEvent[]> {
  const params = new URLSearchParams({
    document_type: documentType,
    document_id: documentId,
  });
  return apiFetch<BooksEvent[]>(`/books-events?${params.toString()}`);
}

export function createPayment(payload: CreatePaymentPayload): Promise<Payment> {
  return apiFetch<Payment>("/payments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function downloadPaymentPdf(id: string, paymentNumber: string): Promise<void> {
  await downloadApiFile(`/api/v1/payments/${id}/pdf`, `${paymentNumber}.pdf`);
}

export type JournalStatus = Schema["JournalStatus"];

export type JournalDocumentType =
  | "invoice"
  | "credit_note"
  | "bill"
  | "payment"
  | "stock_adjustment"
  | "manual";

export type JournalLine = Schema["JournalLineResponse"];

export type Journal = Schema["JournalResponse"];

export type CreateJournalLinePayload = Schema["JournalLineCreate"];

export type CreateJournalPayload = Schema["JournalCreate"];

export type JournalListItem = Schema["JournalListItem"];

export function listJournals(params?: ListParams): Promise<Page<JournalListItem>> {
  return apiFetch<Page<JournalListItem>>(`/journals?${buildListQuery(params)}`);
}

export function getJournal(id: string): Promise<Journal> {
  return apiFetch<Journal>(`/journals/${id}`);
}

export function createJournal(payload: CreateJournalPayload): Promise<Journal> {
  const memo = payload.memo?.trim();
  const source = payload.source?.trim();
  const entryDate = payload.entry_date.trim();
  if (!entryDate) {
    throw new ApiError(400, "Entry date is required");
  }
  const body: CreateJournalPayload = {
    entry_date: entryDate,
    source: source || "manual",
    lines: payload.lines,
  };
  if (memo) {
    body.memo = memo;
  }
  if (payload.status) {
    body.status = payload.status;
  }
  return apiFetch<Journal>("/journals", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function postJournal(id: string): Promise<Journal> {
  return apiFetch<Journal>(`/journals/${id}/post`, { method: "POST" });
}

export function voidJournal(id: string): Promise<Journal> {
  return apiFetch<Journal>(`/journals/${id}/void`, { method: "POST" });
}

export type JournalImportRowError = Schema["JournalImportRowError"];

export type JournalImportPreviewLine = Schema["JournalImportPreviewLine"];

export type JournalImportPreview = Schema["JournalImportPreviewResponse"];

export function previewJournalImport(file: File): Promise<JournalImportPreview> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload<JournalImportPreview>("/journal-imports/preview", formData);
}

export function commitJournalImport(file: File): Promise<Journal> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload<Journal>("/journal-imports/commit", formData);
}

export type BankDocumentSuggestion = Schema["BankDocumentSuggestion"];

export type BankLineAllocation = Schema["BankLineAllocationResponse"];

export type BankImportLine = Schema["BankImportLineResponse"];

export type AutoMatchPreviewItem = Schema["AutoMatchPreviewItem"];

export type BankRule = Schema["BankRuleResponse"];

export type CreateBankRulePayload = Schema["BankRuleCreate"];

export type UpdateBankRulePayload = Schema["BankRuleUpdate"];

export type BankImport = Schema["BankImportResponse"];

export type BankImportSummary = Schema["BankImportSummary"];

export type BankUnmatchedCount = Schema["BankUnmatchedCount"];

export type BankMatchTarget = { payment_id: string } | { journal_id: string };

export type AgedBucket = Schema["AgedBucket"];

export type AgedLine = Schema["AgedLine"];

export type AgedReport = Schema["AgedReport"];

export type ProfitLossLine = Schema["ProfitLossLine"];

export type ProfitLossReport = Schema["ProfitLossReport"];

export type BalanceSheetLine = Schema["BalanceSheetLine"];

export type BalanceSheetReport = Schema["BalanceSheetReport"];

export type Vat201Draft = Schema["Vat201Draft"];

export function listBankImports(): Promise<BankImportSummary[]> {
  return apiFetch<BankImportSummary[]>("/bank-imports");
}

export function getBankImport(id: string): Promise<BankImport> {
  return apiFetch<BankImport>(`/bank-imports/${id}`);
}

export function listUnmatchedCounts(): Promise<BankUnmatchedCount[]> {
  return apiFetch<BankUnmatchedCount[]>("/bank-imports/unmatched-counts");
}

export function listUnmatchedLines(accountId?: string): Promise<BankImportLine[]> {
  const params = new URLSearchParams();
  const id = accountId?.trim();
  if (id) {
    params.set("account_id", id);
  }
  const qs = params.toString();
  return apiFetch<BankImportLine[]>(`/bank-imports/unmatched-lines${qs ? `?${qs}` : ""}`);
}

export function uploadBankImport(file: File, accountId?: string): Promise<BankImport> {
  const formData = new FormData();
  formData.append("file", file);
  const id = accountId?.trim();
  if (id) {
    formData.append("account_id", id);
  }
  return apiUpload<BankImport>("/bank-imports", formData);
}

export function matchBankLine(
  importId: string,
  lineId: string,
  target: BankMatchTarget,
): Promise<BankImportLine> {
  const hasPayment = "payment_id" in target;
  const hasJournal = "journal_id" in target;
  if (hasPayment === hasJournal) {
    throw new ApiError(400, "Provide exactly one of payment_id or journal_id");
  }
  return apiFetch<BankImportLine>(`/bank-imports/${importId}/lines/${lineId}/match`, {
    method: "POST",
    body: JSON.stringify(target),
  });
}

export function matchBankDocument(
  importId: string,
  lineId: string,
  target: { invoice_id: string } | { bill_id: string },
): Promise<BankImportLine> {
  return apiFetch<BankImportLine>(`/bank-imports/${importId}/lines/${lineId}/match-document`, {
    method: "POST",
    body: JSON.stringify(target),
  });
}

export function splitBankLine(
  importId: string,
  lineId: string,
  allocations: Array<{ invoice_id?: string; bill_id?: string; amount: string }>,
): Promise<BankImportLine> {
  return apiFetch<BankImportLine>(`/bank-imports/${importId}/lines/${lineId}/split`, {
    method: "POST",
    body: JSON.stringify({ allocations }),
  });
}

export function previewAutoMatch(accountId?: string): Promise<{ matches: AutoMatchPreviewItem[] }> {
  const params = new URLSearchParams();
  if (accountId) {
    params.set("account_id", accountId);
  }
  const qs = params.toString();
  return apiFetch(`/bank-imports/auto-match/preview${qs ? `?${qs}` : ""}`, { method: "POST" });
}

export function confirmAutoMatch(lineIds: string[]): Promise<{
  applied: AutoMatchPreviewItem[];
  skipped: string[];
}> {
  return apiFetch("/bank-imports/auto-match/confirm", {
    method: "POST",
    body: JSON.stringify({ line_ids: lineIds }),
  });
}

export function listBankRules(bankAccountId?: string): Promise<BankRule[]> {
  const params = new URLSearchParams();
  const id = bankAccountId?.trim();
  if (id) {
    params.set("bank_account_id", id);
  }
  const qs = params.toString();
  return apiFetch<BankRule[]>(`/bank-rules${qs ? `?${qs}` : ""}`);
}

export function createBankRule(payload: CreateBankRulePayload): Promise<BankRule> {
  return apiFetch<BankRule>("/bank-rules", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateBankRule(id: string, payload: UpdateBankRulePayload): Promise<BankRule> {
  return apiFetch<BankRule>(`/bank-rules/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteBankRule(id: string): Promise<void> {
  return apiFetch<void>(`/bank-rules/${id}`, { method: "DELETE" });
}

export function applyRule(
  importId: string,
  lineId: string,
  ruleId: string,
): Promise<BankImportLine> {
  return apiFetch<BankImportLine>(`/bank-imports/${importId}/lines/${lineId}/apply-rule`, {
    method: "POST",
    body: JSON.stringify({ rule_id: ruleId }),
  });
}

export function recodeLine(
  importId: string,
  lineId: string,
  accountId: string,
): Promise<BankImportLine> {
  return apiFetch<BankImportLine>(`/bank-imports/${importId}/lines/${lineId}/recode`, {
    method: "POST",
    body: JSON.stringify({ account_id: accountId }),
  });
}

function reportMonthStartIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

function requireIsoDate(value: string, fallback: string): string {
  return value.trim() || fallback;
}

export function getAgedAr(asOf: string): Promise<AgedReport> {
  const date = requireIsoDate(asOf, localIsoDate());
  return apiFetch<AgedReport>(`/reports/aged-ar?as_of=${encodeURIComponent(date)}`);
}

export function getAgedAp(asOf: string): Promise<AgedReport> {
  const date = requireIsoDate(asOf, localIsoDate());
  return apiFetch<AgedReport>(`/reports/aged-ap?as_of=${encodeURIComponent(date)}`);
}

export function getProfitLoss(fromDate: string, toDate: string): Promise<ProfitLossReport> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  return apiFetch<ProfitLossReport>(
    `/reports/profit-loss?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
}

export function getBalanceSheet(asOf: string): Promise<BalanceSheetReport> {
  const date = requireIsoDate(asOf, localIsoDate());
  return apiFetch<BalanceSheetReport>(
    `/reports/balance-sheet?as_of=${encodeURIComponent(date)}`,
  );
}

export function getVat201Draft(fromDate: string, toDate: string): Promise<Vat201Draft> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  return apiFetch<Vat201Draft>(
    `/reports/vat201?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
}

export async function downloadVat201Csv(fromDate: string, toDate: string): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  await downloadApiFile(
    `/api/v1/reports/vat201/csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    `vat201-draft-${from}-to-${to}.csv`,
  );
}

export async function downloadVat201Pdf(fromDate: string, toDate: string): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  await downloadApiFile(
    `/api/v1/reports/vat201/pdf?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    `vat201-draft-${from}-to-${to}.pdf`,
  );
}

export type Vat201PeriodStatus = Schema["Vat201PeriodStatus"];

export type Vat201Period = Schema["Vat201PeriodResponse"];

export type Vat201PeriodDetail = Schema["Vat201PeriodDetailResponse"];

export type CreateVat201PeriodPayload = Schema["Vat201PeriodCreate"];

export function listVat201Periods(): Promise<Vat201Period[]> {
  return apiFetch<Vat201Period[]>("/vat201/periods");
}

export function createVat201Period(
  payload: CreateVat201PeriodPayload,
): Promise<Vat201PeriodDetail> {
  const period_from = payload.period_from.trim();
  const period_to = payload.period_to.trim();
  if (!period_from || !period_to) {
    throw new ApiError(400, "period_from and period_to are required");
  }
  return apiFetch<Vat201PeriodDetail>("/vat201/periods", {
    method: "POST",
    body: JSON.stringify({ period_from, period_to }),
  });
}

export function getVat201Period(id: string): Promise<Vat201PeriodDetail> {
  return apiFetch<Vat201PeriodDetail>(`/vat201/periods/${id}`);
}

export function lockVat201Period(
  id: string,
  options?: { lock_books?: boolean },
): Promise<Vat201PeriodDetail> {
  const body: { lock_books?: boolean } = {};
  if (options?.lock_books) {
    body.lock_books = true;
  }
  return apiFetch<Vat201PeriodDetail>(`/vat201/periods/${id}/lock`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function reopenVat201Period(id: string, reason: string): Promise<Vat201PeriodDetail> {
  const trimmed = reason.trim();
  if (!trimmed) {
    throw new ApiError(400, "reason is required");
  }
  return apiFetch<Vat201PeriodDetail>(`/vat201/periods/${id}/reopen`, {
    method: "POST",
    body: JSON.stringify({ reason: trimmed }),
  });
}

async function downloadVat201PeriodFile(id: string, kind: "csv" | "pdf"): Promise<void> {
  await downloadApiFile(`/api/v1/vat201/periods/${id}/${kind}`, `vat201-period-${id}.${kind}`);
}

export function downloadVat201PeriodCsv(id: string): Promise<void> {
  return downloadVat201PeriodFile(id, "csv");
}

export function downloadVat201PeriodPdf(id: string): Promise<void> {
  return downloadVat201PeriodFile(id, "pdf");
}

export type StockValuationLine = Schema["StockValuationLine"];

export type StockValuationReport = Schema["StockValuationReport"];

export type AgedStockLine = Schema["AgedStockLine"];

export type AgedStockBucket = Schema["AgedStockBucket"];

export type AgedStockReport = Schema["AgedStockReport"];

export type SalesBySkuLine = Schema["SalesBySkuLine"];

export type SalesBySkuReport = Schema["SalesBySkuReport"];

export type SalesVatReport = Schema["SalesVatReport"];

export type TrialBalanceLine = Schema["TrialBalanceLine"];

export type TrialBalanceReport = Schema["TrialBalanceReport"];

export type JournalReportLine = Schema["JournalReportLine"];

export type JournalReportEntry = Schema["JournalReportEntry"];

export type JournalReport = Schema["JournalReport"];

export type CashSummaryAccount = Schema["CashSummaryAccount"];

export type CashSummaryReport = Schema["CashSummaryReport"];

export function getStockValuation(): Promise<StockValuationReport> {
  return apiFetch<StockValuationReport>("/reports/stock-valuation");
}

export function getAgedStock(): Promise<AgedStockReport> {
  return apiFetch<AgedStockReport>("/reports/aged-stock");
}

export function getSalesBySku(fromDate: string, toDate: string): Promise<SalesBySkuReport> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  return apiFetch<SalesBySkuReport>(
    `/reports/sales-by-sku?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
}

export function getSalesVat(fromDate: string, toDate: string): Promise<SalesVatReport> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  return apiFetch<SalesVatReport>(
    `/reports/sales-vat?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
}

export type AbcClass = "A" | "B" | "C";

export type SkuCriticalityLine = WithLiteral<Schema["SkuCriticalityLine"], "abc_class", AbcClass>;

export type SkuCriticalityCategoryLine = WithLiteral<Schema["SkuCriticalityCategoryLine"], "abc_class", AbcClass>;

export type SkuCriticalityReport = Omit<Schema["SkuCriticalityReport"], "lines" | "categories"> & {
  lines: SkuCriticalityLine[];
  categories: SkuCriticalityCategoryLine[];
};

export function getSkuCriticality(fromDate: string, toDate: string): Promise<SkuCriticalityReport> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  return apiFetch<SkuCriticalityReport>(
    `/reports/sku-criticality?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
}

export type SupplierLeadTimeRow = Schema["SupplierLeadTimeLine"];

export type SkuLeadTimeRow = Schema["SkuLeadTimeLine"];

export type SupplierLeadTimesReport = {
  rows: SupplierLeadTimeRow[];
};

export type SkuLeadTimesReport = {
  rows: SkuLeadTimeRow[];
};

export async function getSupplierLeadTimes(): Promise<SupplierLeadTimesReport> {
  const payload = await apiFetch<Schema["SupplierLeadTimesReport"]>("/reports/supplier-lead-times");
  return { rows: payload.lines };
}

export async function getSkuLeadTimes(): Promise<SkuLeadTimesReport> {
  const payload = await apiFetch<Schema["SkuLeadTimesReport"]>("/reports/sku-lead-times");
  return { rows: payload.lines };
}

export async function downloadStockValuationCsv(): Promise<void> {
  await downloadApiFile("/api/v1/reports/stock-valuation/csv", `stock-valuation-${localIsoDate()}.csv`);
}

export async function downloadAgedStockCsv(): Promise<void> {
  await downloadApiFile("/api/v1/reports/aged-stock/csv", `aged-stock-${localIsoDate()}.csv`);
}

export async function downloadSalesBySkuCsv(fromDate: string, toDate: string): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  await downloadApiFile(
    `/api/v1/reports/sales-by-sku/csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    `sales-by-sku-${from}-to-${to}.csv`,
  );
}

export async function downloadSkuCriticalityCsv(fromDate: string, toDate: string): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  await downloadApiFile(
    `/api/v1/reports/sku-criticality/csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    `sku-criticality-${from}-to-${to}.csv`,
  );
}

export async function downloadSalesVatCsv(fromDate: string, toDate: string): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  await downloadApiFile(
    `/api/v1/reports/sales-vat/csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    `sales-vat-${from}-to-${to}.csv`,
  );
}

export async function downloadSupplierLeadTimesCsv(): Promise<void> {
  await downloadApiFile("/api/v1/reports/supplier-lead-times/csv", `supplier-lead-times-${localIsoDate()}.csv`);
}

export async function downloadSkuLeadTimesCsv(): Promise<void> {
  await downloadApiFile("/api/v1/reports/sku-lead-times/csv", `sku-lead-times-${localIsoDate()}.csv`);
}

function journalsReportQuery(fromDate: string, toDate: string, source?: string): string {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  const params = new URLSearchParams({ from, to });
  const trimmed = source?.trim();
  if (trimmed) {
    params.set("source", trimmed);
  }
  return params.toString();
}

export function getTrialBalance(asOf: string): Promise<TrialBalanceReport> {
  const date = requireIsoDate(asOf, localIsoDate());
  return apiFetch<TrialBalanceReport>(
    `/reports/trial-balance?as_of=${encodeURIComponent(date)}`,
  );
}

export function getJournalsReport(
  fromDate: string,
  toDate: string,
  source?: string,
): Promise<JournalReport> {
  return apiFetch<JournalReport>(`/reports/journals?${journalsReportQuery(fromDate, toDate, source)}`);
}

export function getCashSummary(fromDate: string, toDate: string): Promise<CashSummaryReport> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  return apiFetch<CashSummaryReport>(
    `/reports/cash-summary?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
}

export async function downloadTrialBalanceCsv(asOf: string): Promise<void> {
  const date = requireIsoDate(asOf, localIsoDate());
  await downloadApiFile(
    `/api/v1/reports/trial-balance/csv?as_of=${encodeURIComponent(date)}`,
    `trial-balance-${date}.csv`,
  );
}

export async function downloadJournalsCsv(
  fromDate: string,
  toDate: string,
  source?: string,
): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  await downloadApiFile(
    `/api/v1/reports/journals/csv?${journalsReportQuery(fromDate, toDate, source)}`,
    `journals-${from}-to-${to}.csv`,
  );
}

export async function downloadCashSummaryCsv(fromDate: string, toDate: string): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, localIsoDate());
  await downloadApiFile(
    `/api/v1/reports/cash-summary/csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    `cash-summary-${from}-to-${to}.csv`,
  );
}

export type HomeAttentionKind = "low_stock" | "stocktake" | "returns" | "layby" | "bank";

export type HomeAttentionItem = WithLiteral<Schema["HomeAttentionItem"], "kind", HomeAttentionKind>;

export type HomeMovementItem = Schema["HomeRecentMovement"];

export type HomeSummary = Omit<Schema["HomeSummaryResponse"], "needs_attention"> & {
  needs_attention: HomeAttentionItem[];
};

export type SkuSearchHit = Schema["SkuSearchHit"];

export type PurchaseOrderSearchHit = Schema["PurchaseOrderSearchHit"];

export type InvoiceSearchHit = Schema["InvoiceSearchHit"];

export type SearchResponse = Schema["SearchResponse"];

export type DocumentSequence = Schema["DocumentSequenceResponse"];

export type DocumentSequenceUpdate = Schema["DocumentSequenceUpdateItem"];

export type AppSettings = Schema["SettingsResponse"];

export type UnitCostAuditEntry = Schema["UnitCostAuditResponse"];

function withPickSettings(raw: AppSettings): AppSettings {
  const pick = normalizePickSettings(raw);
  return {
    ...raw,
    always_prefer_warehouse: pick.always_prefer_warehouse,
    pick_priority: pick.pick_priority,
  };
}

export function getHomeSummary(): Promise<HomeSummary> {
  return apiFetch<HomeSummary>("/home");
}

export function searchAll(q: string, signal?: AbortSignal): Promise<SearchResponse> {
  return apiFetch<SearchResponse>(`/search?q=${encodeURIComponent(q)}`, { signal });
}

export function getSettings(): Promise<AppSettings> {
  return apiFetch<AppSettings>("/settings").then(withPickSettings);
}


export function updateSettings(payload: Partial<import("./label-settings").LabelSettings> & {
  vat_rate?: string;
  home_currency?: string;
  always_prefer_warehouse?: boolean;
  pick_priority?: string[];
  legal_name?: string;
  trading_name?: string | null;
  address?: string;
  vat_number?: string;
  cipc_number?: string | null;
  bank_name?: string | null;
  bank_account?: string | null;
  bank_branch_code?: string | null;
  has_logo?: boolean;
  max_till_discount_percent?: string | null;
  po_approval_threshold_zar?: string | null;
  payment_terms_days?: number;
  default_receive_location_id?: string | null;
  default_till_location_id?: string | null;
  till_hold_hours?: number;
  document_sequences?: DocumentSequenceUpdate[];
}): Promise<AppSettings> {
  return apiFetch<AppSettings>("/settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
  }).then(withPickSettings);
}

export function uploadCompanyLogo(file: File): Promise<AppSettings> {
  const formData = new FormData();
  formData.append("logo", file);
  return apiUpload<AppSettings>("/settings/logo", formData).then(withPickSettings);
}

export function settingsLogoUrl(): string {
  return "/api/v1/settings/logo";
}

export type {
  DocumentKind,
  DocumentSectionKey,
  DocumentTemplate,
  DocumentTemplateResponse,
} from "./document-template";

export function getDocumentTemplate(): Promise<import("./document-template").DocumentTemplateResponse> {
  return apiFetch("/settings/document-template");
}

export function saveDocumentTemplate(
  template: import("./document-template").DocumentTemplate,
): Promise<import("./document-template").DocumentTemplateResponse> {
  return apiFetch("/settings/document-template", {
    method: "PUT",
    body: JSON.stringify(template),
  });
}

/** The draft template printed as a real PDF; sample data unless a document id is given. */
export async function previewDocumentTemplate(
  payload: {
    template: import("./document-template").DocumentTemplate;
    kind: import("./document-template").DocumentKind;
    sample_id: string | null;
  },
  signal?: AbortSignal,
): Promise<Blob> {
  const path = "/api/v1/settings/document-template/preview";
  const response = await staffFetch(path, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    throw new ApiError(
      response.status,
      formatHttpError(callName("POST", path), response.status, response.statusText, await parseErrorMessage(response)),
    );
  }
  return response.blob();
}

export type BooksPeriodStatus = Schema["BooksPeriodStatus"];

export type BooksPeriod = Schema["BooksPeriodResponse"];

export type CreateBooksPeriodPayload = Schema["BooksPeriodCreate"];

export function listBooksPeriods(): Promise<BooksPeriod[]> {
  return apiFetch<BooksPeriod[]>("/books-periods");
}

export function createBooksPeriod(payload: CreateBooksPeriodPayload): Promise<BooksPeriod> {
  const period_from = payload.period_from.trim();
  const period_to = payload.period_to.trim();
  if (!period_from || !period_to) {
    throw new ApiError(400, "period_from and period_to are required");
  }
  return apiFetch<BooksPeriod>("/books-periods", {
    method: "POST",
    body: JSON.stringify({ period_from, period_to }),
  });
}

export function lockBooksPeriod(id: string): Promise<BooksPeriod> {
  return apiFetch<BooksPeriod>(`/books-periods/${id}/lock`, { method: "POST" });
}

export function reopenBooksPeriod(id: string, reason: string): Promise<BooksPeriod> {
  const trimmed = reason.trim();
  if (!trimmed) {
    throw new ApiError(400, "reason is required");
  }
  return apiFetch<BooksPeriod>(`/books-periods/${id}/reopen`, {
    method: "POST",
    body: JSON.stringify({ reason: trimmed }),
  });
}

export type AuditSource = "books" | "cost" | "mcp";

export type AuditEvent = Schema["AuditEventItem"];

export function listAuditEvents(params?: {
  limit?: number;
  offset?: number;
  source?: AuditSource;
  q?: string;
}): Promise<Page<AuditEvent>> {
  const search = new URLSearchParams();
  search.set("limit", String(params?.limit ?? 50));
  search.set("offset", String(params?.offset ?? 0));
  if (params?.source) search.set("source", params.source);
  if (params?.q) search.set("q", params.q);
  return apiFetch<Page<AuditEvent>>(`/audit/events?${search.toString()}`);
}

export function listCostAudit(
  skuId: string,
  locationId?: string,
): Promise<UnitCostAuditEntry[]> {
  const query = locationId ? `?location_id=${encodeURIComponent(locationId)}` : "";
  return apiFetch<UnitCostAuditEntry[]>(`/skus/${skuId}/cost-audit${query}`);
}

export function correctUnitCost(
  skuId: string,
  payload: { location_id: string; unit_cost_zar: string },
): Promise<UnitCostAuditEntry> {
  return apiFetch<UnitCostAuditEntry>(`/skus/${skuId}/unit-cost`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export type StockReturnReason = Schema["StockReturnReason"];

export type StockReturnDisposition = Schema["StockReturnDisposition"];

export type StockReturnStatus = Schema["StockReturnStatus"];

export type StockReturnLine = Schema["StockReturnLineResponse"];

export type StockReturn = Schema["StockReturnResponse"];

export type CreateStockReturnLinePayload = Schema["StockReturnLineCreate"];

export type CreateStockReturnPayload = Schema["StockReturnCreate"];

export const RETURN_REASON_LABELS: Record<StockReturnReason, string> = {
  damaged: "Damaged",
  unwanted: "Unwanted",
  wrong_item: "Wrong item",
  other: "Other",
};

export const RETURN_REASONS: StockReturnReason[] = [
  "damaged",
  "unwanted",
  "wrong_item",
  "other",
];

export const RETURN_DISPOSITION_LABELS: Record<StockReturnDisposition, string> = {
  restock: "Restock",
  write_off: "Write-off",
};

export type StockReturnListItem = Schema["StockReturnListItem"];

export function listReturns(params?: ListParams): Promise<Page<StockReturnListItem>> {
  return apiFetch<Page<StockReturnListItem>>(`/returns?${buildListQuery(params)}`);
}

export function getReturn(id: string): Promise<StockReturn> {
  return apiFetch<StockReturn>(`/returns/${id}`);
}

export function createReturn(payload: CreateStockReturnPayload): Promise<StockReturn> {
  const notes = payload.notes?.trim();
  const body: CreateStockReturnPayload = {
    invoice_id: payload.invoice_id,
    location_id: payload.location_id,
    reason: payload.reason,
    disposition: payload.disposition,
    lines: payload.lines,
  };
  if (notes) {
    body.notes = notes;
  }
  return apiFetch<StockReturn>("/returns", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function completeReturn(id: string): Promise<StockReturn> {
  return apiFetch<StockReturn>(`/returns/${id}/complete`, { method: "POST" });
}

export function cancelReturn(id: string): Promise<StockReturn> {
  return apiFetch<StockReturn>(`/returns/${id}/cancel`, { method: "POST" });
}

export type LaybyStatus = Schema["LaybyStatus"];

export type LaybyTender = "cash" | "card";

export type LaybyLine = Schema["LaybyLineResponse"];

export type LaybyPayment = Schema["LaybyPaymentResponse"];

export type LaybyListItem = Schema["LaybyListItem"];

export type Layby = Schema["LaybyResponse"];

export type CreateLaybyLinePayload = Schema["LaybyLineCreate"];

export type CreateLaybyPayload = Schema["LaybyCreate"];

export type AddLaybyPaymentPayload = Schema["LaybyPaymentCreate"];

export function listLaybys(params?: ListParams): Promise<Page<LaybyListItem>> {
  return apiFetch<Page<LaybyListItem>>(`/laybys?${buildListQuery(params)}`);
}

export function getLayby(id: string): Promise<Layby> {
  return apiFetch<Layby>(`/laybys/${id}`);
}

export function createLayby(payload: CreateLaybyPayload): Promise<Layby> {
  const notes = payload.notes?.trim();
  const body: CreateLaybyPayload = {
    customer_id: payload.customer_id,
    location_id: payload.location_id,
    due_date: payload.due_date,
    hold_stock: payload.hold_stock,
    deposit_amount: payload.deposit_amount,
    tender: payload.tender,
    lines: payload.lines,
  };
  if (notes) {
    body.notes = notes;
  }
  return apiFetch<Layby>("/laybys", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** The layby cart priced exactly as creating it would. */
export function previewLaybyPrices(
  payload: Schema["LaybyPreviewRequest"],
  signal?: AbortSignal,
): Promise<SalePricePreview> {
  return apiFetch<SalePricePreview>("/laybys/preview", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export function addLaybyPayment(id: string, payload: AddLaybyPaymentPayload): Promise<Layby> {
  return apiFetch<Layby>(`/laybys/${id}/payments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function completeLayby(id: string): Promise<Layby> {
  return apiFetch<Layby>(`/laybys/${id}/complete`, { method: "POST" });
}

export function cancelLayby(id: string): Promise<Layby> {
  return apiFetch<Layby>(`/laybys/${id}/cancel`, { method: "POST" });
}

export type QuoteStatus = Schema["QuoteStatus"];
/** What staff see: open quotes past their date read as expired. */
export type QuoteState = "open" | "expired" | "converted" | "accepted" | "cancelled";

export type QuoteLine = Schema["QuoteLineResponse"];

export type QuoteListItem = WithLiteral<Schema["QuoteListItem"], "state", QuoteState>;

export type Quote = Schema["QuoteResponse"];

export type QuoteLinePayload = Schema["QuoteLineCreate"];

export type CreateQuotePayload = Schema["QuoteCreate"];

export type AcceptQuotePayload = Schema["QuoteAccept"];

export type SalesOrderStatus = Schema["SalesOrderStatus"];

export type SalesOrderLine = Schema["SalesOrderLineResponse"];

export type SalesOrderPayment = Schema["SalesOrderPaymentResponse"];

export type SalesOrderListItem = Schema["SalesOrderListItem"];

export type SalesOrder = Schema["SalesOrderResponse"];

export function listQuotes(params?: ListParams): Promise<Page<QuoteListItem>> {
  return apiFetch<Page<QuoteListItem>>(`/quotes?${buildListQuery(params)}`);
}

export function getQuote(id: string): Promise<Quote> {
  return apiFetch<Quote>(`/quotes/${id}`);
}

export function createQuote(payload: CreateQuotePayload): Promise<Quote> {
  return apiFetch<Quote>("/quotes", { method: "POST", body: JSON.stringify(payload) });
}

/** A fresh open quote with the same customer, lines, notes and colleague, at today's dates. */
export async function duplicateQuote(id: string): Promise<Quote> {
  const quote = await getQuote(id);
  return createQuote({
    customer_id: quote.customer_id,
    lines: quote.lines.map((line) => ({
      sku_id: line.sku_id,
      qty: line.qty,
      discount_percent: line.discount_percent,
    })),
    notes: quote.notes,
    internal_note: quote.internal_note,
    sales_staff_id: quote.sales_staff_id,
  });
}

/** Replaces the whole quote; omitted notes, validity or colleague are cleared. */
export function replaceQuote(id: string, payload: CreateQuotePayload): Promise<Quote> {
  return apiFetch<Quote>(`/quotes/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

/** Only quotes that were never converted. */
export function deleteQuote(id: string): Promise<void> {
  return apiFetch<void>(`/quotes/${id}`, { method: "DELETE" });
}

/** The quote cart priced exactly as saving it would; an edited quote keeps its saved prices. */
export function previewQuotePrices(
  payload: { customer_id: string; lines: QuoteLinePayload[]; quote_id?: string },
  signal: AbortSignal,
): Promise<SalePricePreview> {
  return apiFetch<SalePricePreview>("/quotes/preview", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export async function downloadQuotePdf(id: string, quoteNumber: string): Promise<void> {
  await downloadApiFile(`/api/v1/quotes/${id}/pdf`, `${quoteNumber}.pdf`);
}

/** Opens the saved quote's PDF in a new tab. */
export async function previewQuotePdf(id: string, quoteNumber: string): Promise<void> {
  await downloadApiFile(`/api/v1/quotes/${id}/pdf`, `${quoteNumber}.pdf`, "open");
}

export function listSalesOrders(params?: ListParams): Promise<Page<SalesOrderListItem>> {
  return apiFetch<Page<SalesOrderListItem>>(`/orders?${buildListQuery(params)}`);
}

export function getSalesOrder(id: string): Promise<SalesOrder> {
  return apiFetch<SalesOrder>(`/orders/${id}`);
}

export function confirmSalesOrder(
  id: string,
  payload: AcceptQuotePayload,
): Promise<SalesOrder> {
  return apiFetch<SalesOrder>(`/orders/${id}/confirm`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function addSalesOrderPayment(
  id: string,
  payload: { amount: string; tender: "cash" | "eft" },
): Promise<SalesOrder> {
  return apiFetch<SalesOrder>(`/orders/${id}/payments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function remainderInvoiceSalesOrder(id: string): Promise<SalesOrder> {
  return apiFetch<SalesOrder>(`/orders/${id}/invoice`, { method: "POST" });
}

export function cancelSalesOrder(id: string): Promise<SalesOrder> {
  return apiFetch<SalesOrder>(`/orders/${id}/cancel`, { method: "POST" });
}

export type StorefrontFulfillmentType = "delivery" | "collection";
export type StorefrontFulfillmentStatus =
  | "confirmed"
  | "ready_for_delivery"
  | "out_for_delivery"
  | "delivered"
  | "ready_for_collection"
  | "collected"
  | "cancelled";

export type StorefrontHandoff = Schema["StorefrontHandoffResponse"];

export function listStorefrontHandoffs(): Promise<{ items: StorefrontHandoff[] }> {
  return apiFetch<{ items: StorefrontHandoff[] }>("/storefront/orders");
}

export function retryStorefrontHandoff(id: string): Promise<StorefrontHandoff> {
  return apiFetch<StorefrontHandoff>(`/storefront/orders/${id}/retry`, { method: "POST" });
}

export function updateStorefrontCollectionStatus(
  id: string,
  status: "ready_for_collection" | "collected",
): Promise<StorefrontHandoff> {
  return apiFetch<StorefrontHandoff>(`/storefront/orders/${id}/collection-status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export type StorefrontRefund = Schema["StorefrontRefundResponse"];

export type StorefrontRefundStatus = Schema["StorefrontRefundStatusResponse"];

export type StorefrontRefundRequest = Schema["StorefrontRefundRequest"];

export function getStorefrontRefundStatus(handoffId: string): Promise<StorefrontRefundStatus> {
  return apiFetch<StorefrontRefundStatus>(`/storefront/orders/${handoffId}/refunds`);
}

export function requestStorefrontRefund(
  handoffId: string,
  payload: StorefrontRefundRequest,
): Promise<StorefrontRefund> {
  return apiFetch<StorefrontRefund>(`/storefront/orders/${handoffId}/refunds`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type PortalMe = Schema["PortalMeResponse"];

export type PortalCatalogueItem = Schema["PortalCatalogueItem"];

export type PortalAccess = {
  id: string;
  organisation_id: string;
  organisation_name: string;
  customer_id: string;
  customer_name: string;
  email: string;
  url: string;
};
export type CustomerPortalAccess = PortalAccess & { status: "active" | "revoked" };
export type PortalInvitation = {
  id: string;
  email: string;
  expires_at: string;
  status: "pending" | "accepted" | "revoked" | "expired";
};
export type CreatedPortalInvitation = PortalInvitation & { invitation_url: string };

export function portalLogout(): Promise<void> {
  return apiFetch("/portal/logout", { method: "POST" });
}
export function listPortalOrganisations(): Promise<PortalAccess[]> {
  return apiFetch("/portal/organisations");
}
export function acceptPortalInvitation(token: string): Promise<PortalAccess> {
  return apiFetch("/portal/invitations/accept", { method: "POST", body: JSON.stringify({ token }) });
}
function portalAccessHeaders(accessId: string): HeadersInit {
  if (!accessId) throw new Error("Choose a trade account first.");
  return { "X-Firstout-Portal-Access": accessId };
}
export function getPortalMe(accessId: string): Promise<PortalMe> {
  return apiFetch("/portal/me", { headers: portalAccessHeaders(accessId) });
}
export function listPortalCatalogue(accessId: string): Promise<PortalCatalogueItem[]> {
  return apiFetch("/portal/catalogue", { headers: portalAccessHeaders(accessId) });
}
export function placePortalOrder(accessId: string, payload: {
  lines: { sku_id: string; qty: number; notes?: string }[];
  notes?: string;
}): Promise<SalesOrder> {
  return apiFetch("/portal/orders", { method: "POST", headers: portalAccessHeaders(accessId), body: JSON.stringify(payload) });
}
export function listPortalOrders(accessId: string): Promise<SalesOrder[]> {
  return apiFetch("/portal/orders", { headers: portalAccessHeaders(accessId) });
}
export function createPortalInvitation(customerId: string, email: string): Promise<CreatedPortalInvitation> {
  return apiFetch(`/customers/${customerId}/portal-invitations`, { method: "POST", body: JSON.stringify({ email }) });
}
export function listPortalInvitations(customerId: string): Promise<PortalInvitation[]> {
  return apiFetch(`/customers/${customerId}/portal-invitations`);
}
export function revokePortalInvitation(customerId: string, invitationId: string): Promise<void> {
  return apiFetch(`/customers/${customerId}/portal-invitations/${invitationId}`, { method: "DELETE" });
}
export function listCustomerPortalAccess(customerId: string): Promise<CustomerPortalAccess[]> {
  return apiFetch(`/customers/${customerId}/portal-access`);
}
export function revokeCustomerPortalAccess(customerId: string, accessId: string): Promise<void> {
  return apiFetch(`/customers/${customerId}/portal-access/${accessId}`, { method: "DELETE" });
}

export type CustomerType = Schema["CustomerCrmResponse"]["customer_type"];

export type PriceClassification = NonNullable<Schema["CustomerCrmCreate"]["price_classification"]>;

export const PRICE_CLASSIFICATIONS: PriceClassification[] = [
  "Stockist",
  "Wholesale",
  "Decorator",
  "Retail",
];

export type CustomerCrm = Schema["CustomerCrmResponse"];

export type CustomerListFilters = {
  archived?: boolean;
  overdue?: boolean;
  active_layby?: boolean;
  on_hold?: boolean;
  q?: string;
};

export type CustomerDuplicateMatch = Schema["CustomerDuplicateMatch"];

export type CreateCustomerPayload = {
  name: string;
  email?: string;
  phone?: string;
  vat_number?: string;
  billing_address?: string;
  customer_type?: CustomerType;
  price_classification?: PriceClassification;
  price_tier?: string;
  credit_limit?: string | null;
  on_hold?: boolean;
  on_hold_reason?: string | null;
  payment_terms_days?: number | null;
  price_list_id?: string | null;
};

export type UpdateCustomerPayload = {
  name?: string;
  email?: string;
  phone?: string;
  vat_number?: string;
  billing_address?: string;
  customer_type?: CustomerType;
  price_classification?: PriceClassification;
  price_tier?: string;
  credit_limit?: string | null;
  on_hold?: boolean;
  on_hold_reason?: string | null;
  payment_terms_days?: number | null;
  price_list_id?: string | null;
};

export const CUSTOMER_TYPE_LABELS: Record<CustomerType, string> = {
  retail: "Retail",
  trade: "Trade",
};

export function listCustomers(filters?: CustomerListFilters): Promise<CustomerCrm[]> {
  const params = new URLSearchParams();
  if (typeof filters?.archived === "boolean") {
    params.set("archived", String(filters.archived));
  }
  if (filters?.overdue) {
    params.set("overdue", "true");
  }
  if (filters?.active_layby) {
    params.set("active_layby", "true");
  }
  if (filters?.on_hold) {
    params.set("on_hold", "true");
  }
  const q = filters?.q?.trim();
  if (q) {
    params.set("q", q);
  }
  const qs = params.toString();
  return apiFetch<CustomerCrm[]>(qs ? `/customers?${qs}` : "/customers");
}

export function getCustomerArchiveCounts(): Promise<ArchiveCounts> {
  return apiFetch<ArchiveCounts>("/customers/archive-counts");
}

export function setCustomerArchived(id: string, isArchived: boolean): Promise<CustomerCrm> {
  return apiFetch<CustomerCrm>(`/customers/${id}/archive`, {
    method: "PATCH",
    body: JSON.stringify({ is_archived: isArchived }),
  });
}

export function findCustomerDuplicates(query: {
  name?: string;
  email?: string;
  phone?: string;
}): Promise<CustomerDuplicateMatch[]> {
  const params = new URLSearchParams();
  const name = query.name?.trim();
  const email = query.email?.trim();
  const phone = query.phone?.trim();
  if (name) {
    params.set("name", name);
  }
  if (email) {
    params.set("email", email);
  }
  if (phone) {
    params.set("phone", phone);
  }
  const qs = params.toString();
  return apiFetch<CustomerDuplicateMatch[]>(`/customers/duplicates${qs ? `?${qs}` : ""}`);
}

export function getCustomer(id: string): Promise<CustomerCrm> {
  return apiFetch<CustomerCrm>(`/customers/${id}`);
}

/** POST /customers ignores the credit fields (CustomerCrmCreate has none); only PATCH applies them. */
function buildCustomerPayload(
  payload: CreateCustomerPayload | UpdateCustomerPayload,
): Schema["CustomerCrmUpdate"] {
  const body: Schema["CustomerCrmUpdate"] = {};
  if ("name" in payload && payload.name !== undefined) {
    body.name = payload.name.trim();
  }
  const email = payload.email?.trim();
  if (email) {
    body.email = email;
  }
  const phone = payload.phone?.trim();
  if (phone) {
    body.phone = phone;
  }
  const vat = payload.vat_number?.trim();
  if (vat) {
    body.vat_number = vat;
  }
  const billing = payload.billing_address?.trim();
  if (billing) {
    body.billing_address = billing;
  }
  if (payload.customer_type) {
    body.customer_type = payload.customer_type;
  }
  if (payload.price_classification) {
    body.price_classification = payload.price_classification;
  }
  const tier = payload.price_tier?.trim();
  if (tier) {
    body.price_tier = tier;
  }
  if (payload.credit_limit !== undefined) {
    const limit = payload.credit_limit?.trim();
    body.credit_limit = limit || null;
  }
  if (payload.on_hold !== undefined) {
    body.on_hold = payload.on_hold;
  }
  const holdReason = payload.on_hold_reason?.trim();
  if (holdReason) {
    body.on_hold_reason = holdReason;
  }
  if ("payment_terms_days" in payload && payload.payment_terms_days !== undefined) {
    body.payment_terms_days = payload.payment_terms_days;
  }
  if ("price_list_id" in payload && payload.price_list_id !== undefined) {
    const listId = payload.price_list_id?.trim?.() ?? payload.price_list_id;
    body.price_list_id = listId ? listId : null;
  }
  return body;
}

export function createCustomer(payload: CreateCustomerPayload): Promise<CustomerCrm> {
  return apiFetch<CustomerCrm>("/customers", {
    method: "POST",
    body: JSON.stringify(buildCustomerPayload(payload)),
  });
}

export function updateCustomer(
  id: string,
  payload: UpdateCustomerPayload,
): Promise<CustomerCrm> {
  return apiFetch<CustomerCrm>(`/customers/${id}`, {
    method: "PATCH",
    body: JSON.stringify(buildCustomerPayload(payload)),
  });
}

export function repriceCustomerDrafts(
  id: string,
): Promise<{ quotes: number; sales_orders: number }> {
  return apiFetch(`/customers/${id}/reprice-drafts`, { method: "POST" });
}

export type DeliveryStatus = Schema["DeliveryStatus"];

export type DeliverySourceType = Schema["DeliverySourceType"];

export type DeliveryLine = Schema["DeliveryLineResponse"];

export type DeliveryListItem = Schema["DeliveryListItem"];

export type Delivery = Schema["DeliveryResponse"];

export type CreateDeliveryPayload = Schema["DeliveryCreate"];

export type CompleteDeliveryPayload = Schema["DeliveryComplete"];

export const DELIVERY_STATUS_LABELS: Record<DeliveryStatus, string> = {
  draft: "Draft",
  packed: "Packed",
  loaded: "Loaded",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

export function listDeliveries(params?: ListParams): Promise<Page<DeliveryListItem>> {
  return apiFetch<Page<DeliveryListItem>>(`/deliveries?${buildListQuery(params)}`);
}

export function getDelivery(id: string): Promise<Delivery> {
  return apiFetch<Delivery>(`/deliveries/${id}`);
}

export function createDelivery(payload: CreateDeliveryPayload): Promise<Delivery> {
  const notes = payload.notes?.trim();
  const body: CreateDeliveryPayload = {
    source_type: payload.source_type,
    location_id: payload.location_id,
  };
  if (payload.source_type === "invoice" && payload.invoice_id) {
    body.invoice_id = payload.invoice_id;
  }
  if (payload.source_type === "layby" && payload.layby_id) {
    body.layby_id = payload.layby_id;
  }
  if (payload.source_type === "sales_order" && payload.sales_order_id) {
    body.sales_order_id = payload.sales_order_id;
  }
  if (notes) {
    body.notes = notes;
  }
  return apiFetch<Delivery>("/deliveries", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function packDelivery(id: string, cartonCount?: number): Promise<Delivery> {
  return apiFetch<Delivery>(`/deliveries/${id}/pack`, {
    method: "POST",
    body: JSON.stringify(cartonCount == null ? {} : { carton_count: cartonCount }),
  });
}

export function loadDelivery(id: string): Promise<Delivery> {
  return apiFetch<Delivery>(`/deliveries/${id}/load`, { method: "POST" });
}

export function updateDeliveryTracking(
  id: string,
  payload: { tracking_number?: string; carrier?: string },
): Promise<Delivery> {
  return apiFetch<Delivery>(`/deliveries/${id}/tracking`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function completeDelivery(
  id: string,
  payload?: CompleteDeliveryPayload,
): Promise<Delivery> {
  const deliveryDate = payload?.delivery_date?.trim();
  const body: CompleteDeliveryPayload = {};
  if (deliveryDate) {
    body.delivery_date = deliveryDate;
  }
  if (payload?.tracking_number) {
    body.tracking_number = payload.tracking_number;
  }
  if (payload?.carrier) {
    body.carrier = payload.carrier;
  }
  return apiFetch<Delivery>(`/deliveries/${id}/complete`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function cancelDelivery(id: string): Promise<Delivery> {
  return apiFetch<Delivery>(`/deliveries/${id}/cancel`, { method: "POST" });
}

export function isInvoiceFullyPaid(invoice: InvoiceListItem): boolean {
  return invoice.payment_status === "paid";
}

export type ReorderRow = Schema["ReorderItemResponse"];

export type CreateReorderDraftPoResponse = Omit<Schema["ReorderDraftPoResponse"], "purchase_orders"> & {
  purchase_orders: PurchaseOrderListItem[];
};

export function listReorder(): Promise<ReorderRow[]> {
  return apiFetch<ReorderRow[]>("/reorder");
}

export function createReorderDraftPo(skuIds: string[]): Promise<CreateReorderDraftPoResponse> {
  return apiFetch<CreateReorderDraftPoResponse>("/reorder/draft-po", {
    method: "POST",
    body: JSON.stringify({ sku_ids: skuIds }),
  });
}

// --- Imported records (Cin7): party detail, supplier prices, history, stock by bin ---

export type PartyAddress = Schema["AddressResponse"];

export type PartyContact = Schema["ContactResponse"];

export type PartyKind = "customers" | "suppliers";

export function listPartyAddresses(kind: PartyKind, id: string): Promise<PartyAddress[]> {
  return apiFetch<PartyAddress[]>(`/${kind}/${id}/addresses`);
}

export function listPartyContacts(kind: PartyKind, id: string): Promise<PartyContact[]> {
  return apiFetch<PartyContact[]>(`/${kind}/${id}/contacts`);
}

export type SupplierPriceRow = Schema["SupplierPriceRow"];

export type SalesHistoryRow = Schema["SalesHistoryRow"];

export type PurchaseHistoryRow = Schema["PurchaseHistoryRow"];

export type StockByBinRow = Schema["StockByBinRow"];

type RecordFilters = Record<string, string | undefined>;

function recordsQuery(params?: ListParams, filters?: RecordFilters): string {
  const search = new URLSearchParams(buildListQuery(params));
  for (const [key, value] of Object.entries(filters ?? {})) {
    if (value) {
      search.set(key, value);
    }
  }
  return search.toString();
}

export function listSupplierPrices(
  params?: ListParams,
  filters?: { supplier_id?: string; sku_id?: string },
): Promise<Page<SupplierPriceRow>> {
  return apiFetch<Page<SupplierPriceRow>>(`/supplier-prices?${recordsQuery(params, filters)}`);
}

export function listSalesHistory(
  params?: ListParams,
  filters?: { customer_id?: string; sku_id?: string; from?: string; to?: string },
): Promise<Page<SalesHistoryRow>> {
  return apiFetch<Page<SalesHistoryRow>>(`/history/sales?${recordsQuery(params, filters)}`);
}

export function listPurchaseHistory(
  params?: ListParams,
  filters?: { supplier_id?: string; from?: string; to?: string },
): Promise<Page<PurchaseHistoryRow>> {
  return apiFetch<Page<PurchaseHistoryRow>>(`/history/purchases?${recordsQuery(params, filters)}`);
}

export function listStockByBin(
  params?: ListParams,
  filters?: { location_id?: string },
): Promise<Page<StockByBinRow>> {
  return apiFetch<Page<StockByBinRow>>(`/stock/by-bin?${recordsQuery(params, filters)}`);
}

export function getSupplier(id: string): Promise<Supplier> {
  return apiFetch<Supplier>(`/suppliers/${id}`);
}
