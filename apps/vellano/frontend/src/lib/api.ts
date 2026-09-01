import {
  normalizePick,
  normalizePickList,
  normalizePickSettings,
  normalizePreview,
  type CreatePickPayload,
  type PickDocument,
  type PickPreview,
  type UpdatePickPayload,
} from "./picks";

export type PresetRole = "owner" | "buyer" | "warehouse" | "till" | "books";
/** Role slug — five presets plus custom slugs from GET /roles. */
export type UserRole = string;

export type Team = {
  id: string;
  name: string;
};

export type AuthUser = {
  id: string;
  email: string;
  role: UserRole;
  permissions: string[];
  team: Team;
  display_name: string | null;
  default_location_id: string | null;
};

export type User = {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_disabled: boolean;
  team_id: string;
  team: Team;
  default_location_id: string | null;
};

export type Role = {
  id: string;
  slug: string;
  name: string;
  is_system: boolean;
  is_owner_preset: boolean;
  permissions: string[];
};

export type RoleCreatePayload = {
  name: string;
  permissions: string[];
};

export type RoleUpdatePayload = {
  name?: string;
  permissions?: string[];
};

export type LoginResponse = {
  email: string;
};

export type CreateUserPayload = {
  email: string;
  password: string;
  role: UserRole;
  display_name?: string;
  default_location_id?: string | null;
};

export type UpdateUserPayload = {
  email?: string;
  password?: string;
  role?: UserRole;
  display_name?: string;
  is_disabled?: boolean;
  default_location_id?: string | null;
};

export type UpdateProfilePayload = {
  email?: string;
  display_name?: string;
  password?: string;
  default_location_id?: string | null;
};

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string | { msg?: string }[] };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      return body.detail[0].msg;
    }
  } catch {
    // ignore parse errors
  }
  return response.statusText || "Request failed";
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`/api/v1${path}`, {
    ...options,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
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

export function createUser(payload: CreateUserPayload): Promise<User> {
  return apiFetch<User>("/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
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
  can,
  canManageCustomerCredit,
  canManageLocations,
  canMutateBooks,
  canMutateCatalogue,
  canMutateCustomers,
  canMutateDeliveries,
  canMutateLaybys,
  canMutatePicks,
  canMutateReturns,
  canMutateSettings,
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
  PickDocument,
  PickLine,
  PickPreview,
  PickPreviewLine,
  PickStatus,
  UpdatePickPayload,
} from "./picks";

export type LocationType = "warehouse" | "showroom";

export type Location = {
  id: string;
  name: string;
  type: LocationType;
  is_archived: boolean;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateLocationPayload = {
  name: string;
  type: LocationType;
};

export type UpdateLocationPayload = {
  name?: string;
  is_archived?: boolean;
};

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

export type LocationBin = {
  id: string;
  location_id: string;
  code: string;
  row_code: string;
  bay: number;
  level: number;
  is_default: boolean;
  is_archived: boolean;
  archived_at: string | null;
};

export type CreateLocationBinPayload = {
  row_code: string;
  bay: number;
  level: number;
};

export type LocationBinGridPayload = {
  rows: string[];
  bays: number;
  levels: number;
};

export type UpdateLocationBinPayload = {
  is_archived?: boolean;
  is_default?: boolean;
};

export type InventoryBinOnHand = {
  bin_id: string;
  code: string;
  on_hand: number;
};

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
  const response = await fetch(`/api/v1${path}`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export type Supplier = {
  id: string;
  name: string;
  default_currency: string;
  created_at: string;
  updated_at: string;
};

export type CreateSupplierPayload = {
  name: string;
  default_currency?: string;
};

export function listSuppliers(): Promise<Supplier[]> {
  return apiFetch<Supplier[]>("/suppliers");
}

export function createSupplier(payload: CreateSupplierPayload): Promise<Supplier> {
  return apiFetch<Supplier>("/suppliers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type Proforma = {
  id: string;
  supplier_id: string;
  supplier_name: string;
  invoice_number: string;
  invoice_date: string;
  currency: string;
  pdf_storage_key: string;
  created_at: string;
  updated_at: string;
};

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

export type Sku = {
  id: string;
  our_ref: string;
  our_barcode: string;
  name: string;
  design: string;
  fabric: string;
  category: string | null;
  supplier_ref: string | null;
  preferred_supplier_id: string | null;
  preferred_supplier_name: string | null;
  lead_time_days: number | null;
  reorder_min: number | null;
  last_landed_cost_zar: string | null;
  photo_storage_key: string | null;
  wholesale_ex_vat: string | null;
  wholesale_inc_vat: string | null;
  retail_ex_vat: string | null;
  retail_inc_vat: string | null;
  carton_count: number;
  is_kit: boolean;
  created_at: string;
  updated_at: string;
};

export type UpdateSkuPricePayload = {
  our_ref?: string;
  our_barcode?: string;
  name?: string;
  design?: string;
  fabric?: string;
  category?: string | null;
  wholesale_ex_vat?: string | number | null;
  wholesale_inc_vat?: string | number | null;
  retail_ex_vat?: string | number | null;
  retail_inc_vat?: string | number | null;
  preferred_supplier_id?: string | null;
  lead_time_days?: number | null;
  reorder_min?: number | null;
  supplier_ref?: string | null;
  carton_count?: number;
};

const VAT_MULTIPLIER = 1.15;

/** Round to cents using ROUND_HALF_UP (ties away from zero). */
export function roundHalfUp(value: number, decimals = 2): number {
  const factor = 10 ** decimals;
  const scaled = value * factor;
  return (Math.sign(scaled) * Math.round(Math.abs(scaled))) / factor;
}

export function exVatToIncVat(ex: number): number {
  return roundHalfUp(ex * VAT_MULTIPLIER, 2);
}

export function incVatToExVat(inc: number): number {
  return roundHalfUp(inc / VAT_MULTIPLIER, 2);
}

export function formatPriceAmount(value: number): string {
  return value.toFixed(2);
}

export function parsePriceInput(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return parsed;
}

export function displayPrice(value: string | null | undefined): string {
  return value ?? "—";
}

export type CreateSkuPayload = {
  our_ref: string;
  our_barcode: string;
  name: string;
  design: string;
  fabric: string;
  category?: string;
  supplier_ref?: string;
  opening_location_id?: string;
  opening_qty?: number;
  opening_unit_cost_zar?: string;
  opening_date?: string;
  carton_count?: number;
};

export function listSkus(options?: { category?: string }): Promise<Sku[]> {
  const params = new URLSearchParams();
  const category = options?.category?.trim();
  if (category) {
    params.set("category", category);
  }
  const qs = params.toString();
  return apiFetch<Sku[]>(`/skus${qs ? `?${qs}` : ""}`);
}

export function createSku(payload: CreateSkuPayload): Promise<Sku> {
  const body: CreateSkuPayload = { ...payload };
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

export function deleteSku(id: string): Promise<void> {
  return apiFetch<void>(`/skus/${id}`, { method: "DELETE" });
}

export function skuPhotoUrl(id: string): string {
  return `/api/v1/skus/${id}/photo`;
}

export type SkuBomLine = {
  id: string;
  parent_sku_id: string;
  component_sku_id: string;
  qty: number;
  created_at: string;
  updated_at: string;
};

export type SkuBomLineWrite = {
  component_sku_id: string;
  qty: number;
};

export type ReplaceSkuBomPayload = {
  lines: SkuBomLineWrite[];
};

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

export type CatalogueImportError = {
  file: CatalogueImportFileKind;
  row: number;
  message: string;
};

export type CatalogueImportInventoryPreview = {
  headers: string[];
  suggested_map: Record<string, string>;
  applied_map: Record<string, string>;
  sample_row: Record<string, string> | null;
  row_count: number;
  create_count: number;
  update_count: number;
};

export type CatalogueImportSohPreview = {
  headers: string[];
  suggested_map: Record<string, string>;
  applied_map: Record<string, string>;
  sample_row: Record<string, string> | null;
  row_count: number;
};

export type CatalogueImportPreview = {
  ok: boolean;
  errors: CatalogueImportError[];
  inventory: CatalogueImportInventoryPreview;
  soh: CatalogueImportSohPreview | null;
};

export type CatalogueImportCommit = {
  created_skus: number;
  updated_skus: number;
  soh_rows: number;
};

export function previewCatalogueImport(formData: FormData): Promise<CatalogueImportPreview> {
  return apiUpload<CatalogueImportPreview>("/imports/preview", formData);
}

export function commitCatalogueImport(formData: FormData): Promise<CatalogueImportCommit> {
  return apiUpload<CatalogueImportCommit>("/imports/commit", formData);
}

export type PurchaseOrderStatus = "open" | "on_water" | "landed" | "received";

export type PoLine = {
  id: string;
  sku_id: string;
  our_ref: string;
  our_barcode: string;
  name: string;
  fabric: string;
  qty: number;
  factory_unit_amount: string;
  unit_cost_zar: string | null;
};

export type LandingBill = {
  kind: string;
  invoice_number: string;
  amount: string;
  currency: string;
};

export type PurchaseOrder = {
  id: string;
  po_number: string;
  status: PurchaseOrderStatus;
  supplier_id: string;
  supplier_name: string;
  proforma_id: string | null;
  fx_to_zar: string | null;
  lines: PoLine[];
  bills: LandingBill[];
  received_location_id: string | null;
  ordered_at: string | null;
  on_water_at: string | null;
  landed_at: string | null;
  received_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreatePoLinePayload = {
  sku_id: string;
  qty: number;
  factory_unit_amount: string;
};

export type CreatePurchaseOrderPayload = {
  supplier_id: string;
  proforma_id?: string;
  lines: CreatePoLinePayload[];
};

export type InventorySku = {
  sku_id: string;
  our_ref: string;
  name: string;
  on_order: number;
  on_hand: number;
  sellable: boolean;
  unit_cost_zar: string | null;
  locations: {
    location_id: string;
    location_name: string;
    on_hand: number;
    unit_cost_zar: string | null;
    bins: InventoryBinOnHand[];
  }[];
};

export const PO_STATUS_LABELS: Record<PurchaseOrderStatus, string> = {
  open: "Open",
  on_water: "On water",
  landed: "Landed",
  received: "Received",
};

export type TillTender = "cash" | "card" | "deposit" | "eft";

export type TillSaleLinePayload = {
  sku_id: string;
  qty: number;
  discount_percent?: number;
};

export type TillSalePayload = {
  location_id: string;
  lines: TillSaleLinePayload[];
  tender: TillTender;
  customer_id?: string;
  pick_id?: string;
  credit_override?: boolean;
  credit_override_reason?: string;
};

export type TillSaleResult = {
  invoice_id: string;
  invoice_number: string;
  payment_id: string;
  payment_number: string;
  tender: TillTender;
  issue_date: string;
  subtotal_ex_vat: string;
  vat_amount: string;
  total_inc_vat: string;
  lines: InvoiceLine[];
  location: {
    location_id: string;
    location_name: string;
    on_hand: number;
  };
};

export function createTillSale(payload: TillSalePayload): Promise<TillSaleResult> {
  return apiFetch<TillSaleResult>("/till/sales", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listPurchaseOrders(): Promise<PurchaseOrder[]> {
  return apiFetch<PurchaseOrder[]>("/purchase-orders");
}

export function createPurchaseOrder(payload: CreatePurchaseOrderPayload): Promise<PurchaseOrder> {
  return apiFetch<PurchaseOrder>("/purchase-orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getPurchaseOrder(id: string): Promise<PurchaseOrder> {
  return apiFetch<PurchaseOrder>(`/purchase-orders/${id}`);
}

export async function downloadPackingSheet(id: string, poNumber: string): Promise<void> {
  const response = await fetch(`/api/v1/purchase-orders/${id}/packing-sheet`, {
    credentials: "include",
  });

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${poNumber}-packing-sheet.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export function markOnWater(id: string): Promise<PurchaseOrder> {
  return apiFetch<PurchaseOrder>(`/purchase-orders/${id}/on-water`, {
    method: "POST",
  });
}

export function landPurchaseOrder(id: string, formData: FormData): Promise<PurchaseOrder> {
  return apiUpload<PurchaseOrder>(`/purchase-orders/${id}/land`, formData);
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

export type TransferStatus = "draft" | "in_transit" | "received" | "cancelled";

export type TransferLine = {
  id: string;
  sku_id: string;
  sku_our_ref: string;
  sku_name: string;
  qty_dispatched: number;
  qty_received: number | null;
  from_bin_id: string | null;
  to_bin_id: string | null;
};

export type Transfer = {
  id: string;
  transfer_number: string;
  status: TransferStatus;
  from_location_id: string;
  from_location_name: string;
  to_location_id: string;
  to_location_name: string;
  notes: string | null;
  dispatched_at: string | null;
  received_at: string | null;
  received_display_name: string | null;
  lines: TransferLine[];
  created_at: string;
  updated_at: string;
};

export type TransferLinePayload = {
  sku_id: string;
  qty: number;
  from_bin_id?: string;
  to_bin_id?: string;
};

export type CreateTransferPayload = {
  from_location_id: string;
  to_location_id: string;
  notes?: string;
  lines: TransferLinePayload[];
};

export type TransferReceivePayload = {
  lines: { line_id: string; qty_received: number }[];
};

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
  const response = await fetch(`/api/v1/transfers/${id}/pdf`, {
    credentials: "include",
  });

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${transferNumber}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export function listPicks(): Promise<PickDocument[]> {
  return apiFetch<unknown>("/picks").then(normalizePickList);
}

export function getPick(id: string): Promise<PickDocument> {
  return apiFetch<unknown>(`/picks/${id}`).then(normalizePick);
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
  const response = await fetch(`/api/v1/picks/${id}/pdf`, {
    credentials: "include",
  });

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const opened = window.open(url, "_blank");
  if (!opened) {
    URL.revokeObjectURL(url);
    window.alert("Allow pop-ups to print.");
    return;
  }
  opened.addEventListener("load", () => {
    URL.revokeObjectURL(url);
  });
}

export type StocktakeStatus = "in_progress" | "completed" | "cancelled";

export type StocktakeLine = {
  id: string;
  sku_id: string;
  our_ref: string;
  our_barcode: string;
  name: string;
  category: string | null;
  expected_qty: number;
  counted_qty: number | null;
  variance: number | null;
};

export type StocktakeSummary = {
  id: string;
  location_id: string;
  location_name: string;
  status: StocktakeStatus;
  started_at: string;
  completed_at: string | null;
};

export type Stocktake = StocktakeSummary & {
  lines: StocktakeLine[];
};

export const STOCKTAKE_STATUS_LABELS: Record<StocktakeStatus, string> = {
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
};

export function listStocktakes(): Promise<StocktakeSummary[]> {
  return apiFetch<StocktakeSummary[]>("/stocktakes");
}

export function startStocktake(payload: { location_id: string }): Promise<Stocktake> {
  return apiFetch<Stocktake>("/stocktakes", {
    method: "POST",
    body: JSON.stringify(payload),
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

export type AdjustmentReason = "opening" | "damage" | "theft" | "count_fix" | "write_off";

export type AdjustmentStatus = "draft" | "completed" | "cancelled";

export type AdjustmentLine = {
  id: string;
  sku_id: string;
  our_ref: string;
  name: string;
  qty_delta: number;
  unit_cost_zar: string | null;
  current_qty?: number;
  new_qty?: number;
};

export type AdjustmentSummary = {
  id: string;
  location_id: string;
  location_name?: string;
  reason: AdjustmentReason;
  notes?: string | null;
  status: AdjustmentStatus;
  created_at?: string;
  started_at?: string;
  completed_at?: string | null;
  cancelled_at?: string | null;
  lines?: AdjustmentLine[];
};

export type Adjustment = AdjustmentSummary & {
  lines: AdjustmentLine[];
};

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

export type CreateAdjustmentPayload = {
  location_id: string;
  reason: AdjustmentReason;
  notes?: string;
};

export type CreateAdjustmentLinePayload = {
  sku_id: string;
  qty_delta: number;
  unit_cost_zar?: string;
};

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
  const cost = payload.unit_cost_zar?.trim();
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

export type AccountType = "asset" | "liability" | "equity" | "income" | "expense";

export type TaxTreatment = "none" | "vat15";

export type Account = {
  id: string;
  code: string;
  name: string;
  type: AccountType;
  is_system: boolean;
  is_archived: boolean;
  is_bank: boolean;
  tax_treatment: TaxTreatment;
  balance_zar: string;
  created_at: string;
  updated_at: string;
};

export type CreateAccountPayload = {
  code: string;
  name: string;
  type: AccountType;
  tax_treatment?: TaxTreatment;
  is_bank?: boolean;
};

export type UpdateAccountPayload = {
  name?: string;
  is_archived?: boolean;
  tax_treatment?: TaxTreatment;
  is_bank?: boolean;
};

export const ACCOUNT_TYPES: { value: AccountType; label: string }[] = [
  { value: "asset", label: "Asset" },
  { value: "liability", label: "Liability" },
  { value: "equity", label: "Equity" },
  { value: "income", label: "Income" },
  { value: "expense", label: "Expense" },
];

export const TAX_TREATMENTS: { value: TaxTreatment; label: string }[] = [
  { value: "vat15", label: "VAT 15%" },
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

export type CategoryMap = {
  id: string;
  category: string;
  sales_code: string;
  cogs_code: string;
  stock_adj_code: string;
  count_var_code: string;
};

export type UpsertCategoryMapPayload = {
  category: string;
  sales_code: string;
  cogs_code: string;
  stock_adj_code: string;
  count_var_code: string;
};

export function listCategoryMaps(): Promise<CategoryMap[]> {
  return apiFetch<CategoryMap[]>("/category-maps");
}

export function upsertCategoryMap(payload: UpsertCategoryMapPayload): Promise<CategoryMap> {
  return apiFetch<CategoryMap>("/category-maps", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export type ContactKind = "customer" | "supplier";

export type Contact = {
  id: string;
  kind: ContactKind;
  name: string;
  currency: string | null;
  email: string | null;
  vat_number: string | null;
  billing_address: string | null;
};

export type CreateContactPayload = {
  name: string;
  email?: string;
  vat_number?: string;
  billing_address?: string;
};

export function listContacts(): Promise<Contact[]> {
  return apiFetch<Contact[]>("/contacts");
}

export function createContact(payload: CreateContactPayload): Promise<Contact> {
  return apiFetch<Contact>("/contacts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type InvoiceLine = {
  id: string;
  description: string;
  qty: number;
  unit_ex_vat: string;
  ex_vat: string;
  inc_vat: string;
  vat_amount: string;
  sort_order: number;
  sku_id?: string | null;
};

export type Invoice = {
  id: string;
  invoice_number: string;
  customer_id: string;
  customer_name: string;
  issue_date: string;
  subtotal_ex_vat: string;
  vat_amount: string;
  total_inc_vat: string;
  amount_paid: string;
  balance: string;
  lines: InvoiceLine[];
  created_at: string;
  updated_at: string;
};

export type CreateInvoiceLinePayload = {
  description: string;
  qty: number;
  unit_ex_vat: string;
};

export type CreateInvoicePayload = {
  customer_id: string;
  issue_date: string;
  lines: CreateInvoiceLinePayload[];
};

export function listInvoices(): Promise<Invoice[]> {
  return apiFetch<Invoice[]>("/invoices");
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

export type RepeatingInvoiceLine = {
  id: string;
  description: string;
  qty: number;
  unit_ex_vat: string;
  sort_order: number;
};

export type RepeatingInvoice = {
  id: string;
  customer_id: string;
  name: string | null;
  day_of_month: number;
  next_date: string;
  is_active: boolean;
  created_by: string | null;
  lines: RepeatingInvoiceLine[];
  created_at: string;
  updated_at: string;
};

export type CreateRepeatingInvoicePayload = {
  customer_id: string;
  name?: string;
  day_of_month: number;
  next_date: string;
  lines: CreateInvoiceLinePayload[];
};

export type RepeatingInvoiceRun = {
  schedule: RepeatingInvoice;
  invoice: Invoice;
};

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
  const response = await fetch(`/api/v1/invoices/${id}/pdf`, {
    credentials: "include",
  });

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${invoiceNumber}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export type CreditNote = {
  id: string;
  credit_note_number: string;
  invoice_id: string;
  invoice_number: string;
  reason: string | null;
  issue_date: string;
  subtotal_ex_vat: string;
  vat_amount: string;
  total_inc_vat: string;
  created_at: string;
  updated_at: string;
};

export type CreateCreditNotePayload = {
  invoice_id: string;
  reason?: string;
};

export function listCreditNotes(): Promise<CreditNote[]> {
  return apiFetch<CreditNote[]>("/credit-notes");
}

export function createCreditNote(payload: CreateCreditNotePayload): Promise<CreditNote> {
  return apiFetch<CreditNote>("/credit-notes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type BillLine = {
  id: string;
  description: string;
  qty: number;
  unit_amount: string;
  amount_foreign: string;
  sort_order: number;
};

export type Bill = {
  id: string;
  bill_number: string;
  supplier_id: string;
  supplier_name: string;
  supplier_ref: string;
  issue_date: string;
  currency: string;
  fx_to_zar: string;
  amount_foreign: string;
  amount_zar: string;
  amount_paid_zar: string;
  balance_zar: string;
  pdf_storage_key: string | null;
  lines: BillLine[];
  created_at: string;
  updated_at: string;
};

export type CreateBillLinePayload = {
  description: string;
  qty: number;
  unit_amount: string;
};

export type CreateBillPayload = {
  supplier_id: string;
  supplier_ref: string;
  issue_date: string;
  currency: string;
  fx_to_zar?: string;
  lines: CreateBillLinePayload[];
};

export function listBills(): Promise<Bill[]> {
  return apiFetch<Bill[]>("/bills");
}

export function createBill(payload: CreateBillPayload): Promise<Bill> {
  return apiFetch<Bill>("/bills", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getBill(id: string): Promise<Bill> {
  return apiFetch<Bill>(`/bills/${id}`);
}

export function uploadBillAttachment(id: string, file: File): Promise<Bill> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload<Bill>(`/bills/${id}/attachment`, formData);
}

export async function downloadBillAttachment(id: string, billNumber: string): Promise<void> {
  const response = await fetch(`/api/v1/bills/${id}/attachment`, {
    credentials: "include",
  });

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${billNumber}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export type PaymentDirection = "in" | "out";

export type Payment = {
  id: string;
  payment_number: string;
  direction: PaymentDirection;
  invoice_id: string | null;
  bill_id: string | null;
  amount: string;
  currency: string;
  fx_to_zar: string;
  amount_zar: string;
  fx_gain_loss_zar: string;
  paid_on: string;
  is_reconciled: boolean;
  reconciled_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreatePaymentInPayload = {
  direction: "in";
  invoice_id: string;
  amount: string;
  currency: "ZAR";
  paid_on: string;
};

export type CreatePaymentOutPayload = {
  direction: "out";
  bill_id: string;
  amount: string;
  currency: string;
  fx_to_zar?: string;
  paid_on: string;
};

export type CreatePaymentPayload = CreatePaymentInPayload | CreatePaymentOutPayload;

export function listPayments(): Promise<Payment[]> {
  return apiFetch<Payment[]>("/payments");
}

export type BooksDocumentType = "invoice" | "bill" | "payment" | "journal";

export type BooksEventAction = "created" | "posted" | "voided";

export type BooksEvent = {
  id: string;
  document_type: BooksDocumentType;
  document_id: string;
  action: BooksEventAction;
  actor_user_id: string | null;
  actor_email: string | null;
  note: string | null;
  created_at: string;
};

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

export type JournalStatus = "draft" | "posted" | "voided";

export type JournalDocumentType =
  | "invoice"
  | "credit_note"
  | "bill"
  | "payment"
  | "stock_adjustment"
  | "manual";

export type JournalLine = {
  id: string;
  account_id: string;
  account_code: string;
  account_name: string;
  debit_zar: string;
  credit_zar: string;
};

export type Journal = {
  id: string;
  document_type: JournalDocumentType;
  document_id: string;
  memo: string | null;
  status: JournalStatus;
  source: string | null;
  journal_number: string | null;
  entry_date: string;
  voided_by_id: string | null;
  debit_total_zar: string;
  credit_total_zar: string;
  lines: JournalLine[];
  created_at: string;
};

export type CreateJournalLinePayload = {
  account_id: string;
  debit_zar: string;
  credit_zar: string;
};

export type CreateJournalPayload = {
  entry_date: string;
  memo?: string;
  source?: string;
  status?: "draft" | "posted";
  lines: CreateJournalLinePayload[];
};

export function listJournals(): Promise<Journal[]> {
  return apiFetch<Journal[]>("/journals");
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

export type JournalImportRowError = {
  row: number;
  message: string;
};

export type JournalImportPreviewLine = {
  row: number;
  account_code: string;
  debit_zar: string;
  credit_zar: string;
};

export type JournalImportPreview = {
  lines: JournalImportPreviewLine[];
  errors: JournalImportRowError[];
  balanced: boolean;
  debit_total: string;
  credit_total: string;
  entry_date: string | null;
  narration: string;
};

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

export function formatZarAmount(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return `R ${value}`;
}

export function sumInvoiceLinesExVat(
  lines: { qty: number | ""; unit_ex_vat: string }[],
): number {
  return lines.reduce((sum, line) => {
    if (typeof line.qty !== "number" || line.qty <= 0) {
      return sum;
    }
    const unit = parsePriceInput(line.unit_ex_vat);
    if (unit === null || unit <= 0) {
      return sum;
    }
    return sum + line.qty * unit;
  }, 0);
}

export function computeInvoicePreview(subtotalExVat: number): {
  vat: number;
  totalIncVat: number;
} {
  const vat = roundHalfUp(subtotalExVat * 0.15, 2);
  const totalIncVat = roundHalfUp(subtotalExVat + vat, 2);
  return { vat, totalIncVat };
}

export function formatFxGainLoss(value: string): string {
  const amount = Number(value);
  if (!Number.isFinite(amount) || amount === 0) {
    return "R 0.00";
  }
  const prefix = amount > 0 ? "Gain " : "Loss ";
  return `${prefix}R ${Math.abs(amount).toFixed(2)}`;
}

export type BankImportLine = {
  id: string;
  transaction_date: string;
  description: string;
  reference: string | null;
  amount_zar: string;
  matched_payment_id: string | null;
  matched_journal_id: string | null;
  matched_payment_number: string | null;
  matched_journal_number?: string | null;
  suggested_payment_id: string | null;
  suggested_payment_number: string | null;
  suggested_rule_id?: string | null;
  suggested_rule_pattern?: string | null;
  suggested_account_code?: string | null;
  suggested_account_name?: string | null;
};

export type BankRule = {
  id: string;
  bank_account_id: string;
  pattern: string;
  target_account_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type CreateBankRulePayload = {
  bank_account_id: string;
  pattern: string;
  target_account_id: string;
};

export type UpdateBankRulePayload = {
  pattern?: string;
  target_account_id?: string;
  is_active?: boolean;
};

export type BankImport = {
  id: string;
  filename: string;
  line_count: number;
  account_id: string;
  account_code: string;
  account_name: string;
  lines: BankImportLine[];
  created_at: string;
  updated_at: string;
};

export type BankImportSummary = {
  id: string;
  filename: string;
  line_count: number;
  matched_count: number;
  unmatched_count: number;
  account_id: string;
  account_code: string;
  account_name: string;
  created_at: string;
};

export type BankUnmatchedCount = {
  account_id: string;
  account_code: string;
  account_name: string;
  unmatched_count: number;
};

export type BankMatchTarget = { payment_id: string } | { journal_id: string };

export type AgedBucket = {
  label: string;
  amount_zar: string;
};

export type AgedLine = {
  document_number: string;
  contact_name: string;
  issue_date: string;
  balance_zar: string;
  days_outstanding: number;
  bucket: string;
};

export type AgedReport = {
  as_of: string;
  total_zar: string;
  buckets: AgedBucket[];
  lines: AgedLine[];
};

export type ProfitLossLine = {
  code: string;
  name: string;
  amount_zar: string;
};

export type ProfitLossReport = {
  from_date: string;
  to_date: string;
  income: ProfitLossLine[];
  expenses: ProfitLossLine[];
  total_income_zar: string;
  total_expenses_zar: string;
  net_profit_zar: string;
};

export type BalanceSheetLine = {
  code: string;
  name: string;
  type: string;
  balance_zar: string;
};

export type BalanceSheetReport = {
  as_of: string;
  assets: BalanceSheetLine[];
  liabilities: BalanceSheetLine[];
  equity_zar: string;
  total_assets_zar: string;
  total_liabilities_zar: string;
};

export type Vat201Draft = {
  period_from: string;
  period_to: string;
  vendor_name: string;
  vendor_vat_number: string;
  standard_rated_supplies_ex_vat: string;
  output_tax: string;
  input_tax: string;
  net_vat_payable: string;
  invoice_count: number;
  credit_note_count: number;
  disclaimer: string;
};

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

function reportTodayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function reportMonthStartIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

function requireIsoDate(value: string, fallback: string): string {
  return value.trim() || fallback;
}

export function getAgedAr(asOf: string): Promise<AgedReport> {
  const date = requireIsoDate(asOf, reportTodayIso());
  return apiFetch<AgedReport>(`/reports/aged-ar?as_of=${encodeURIComponent(date)}`);
}

export function getAgedAp(asOf: string): Promise<AgedReport> {
  const date = requireIsoDate(asOf, reportTodayIso());
  return apiFetch<AgedReport>(`/reports/aged-ap?as_of=${encodeURIComponent(date)}`);
}

export function getProfitLoss(fromDate: string, toDate: string): Promise<ProfitLossReport> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, reportTodayIso());
  return apiFetch<ProfitLossReport>(
    `/reports/profit-loss?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
}

export function getBalanceSheet(asOf: string): Promise<BalanceSheetReport> {
  const date = requireIsoDate(asOf, reportTodayIso());
  return apiFetch<BalanceSheetReport>(
    `/reports/balance-sheet?as_of=${encodeURIComponent(date)}`,
  );
}

export function getVat201Draft(fromDate: string, toDate: string): Promise<Vat201Draft> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, reportTodayIso());
  return apiFetch<Vat201Draft>(
    `/reports/vat201?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
}

export async function downloadVat201Csv(fromDate: string, toDate: string): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, reportTodayIso());
  const response = await fetch(
    `/api/v1/reports/vat201/csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    { credentials: "include" },
  );
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `vat201-draft-${from}-to-${to}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export async function downloadVat201Pdf(fromDate: string, toDate: string): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, reportTodayIso());
  const response = await fetch(
    `/api/v1/reports/vat201/pdf?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    { credentials: "include" },
  );
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `vat201-draft-${from}-to-${to}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export type Vat201PeriodStatus = "draft" | "due" | "locked";

export type Vat201Period = {
  id: string;
  period_from: string;
  period_to: string;
  status: Vat201PeriodStatus;
  locked_at: string | null;
  locked_by_user_id: string | null;
  reopen_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type Vat201PeriodEvent = {
  action: string;
  created_at?: string;
  at?: string;
  reason?: string | null;
};

export type Vat201PeriodDetail = Vat201Period & {
  draft: Vat201Draft;
  events?: Vat201PeriodEvent[];
};

export type CreateVat201PeriodPayload = {
  period_from: string;
  period_to: string;
};

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

export function lockVat201Period(id: string): Promise<Vat201PeriodDetail> {
  return apiFetch<Vat201PeriodDetail>(`/vat201/periods/${id}/lock`, { method: "POST" });
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
  const response = await fetch(`/api/v1/vat201/periods/${id}/${kind}`, {
    credentials: "include",
  });
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition");
  const named = disposition?.match(/filename="([^"]+)"/)?.[1];
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = named ?? `vat201-period-${id}.${kind}`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export function downloadVat201PeriodCsv(id: string): Promise<void> {
  return downloadVat201PeriodFile(id, "csv");
}

export function downloadVat201PeriodPdf(id: string): Promise<void> {
  return downloadVat201PeriodFile(id, "pdf");
}

export type StockValuationLine = {
  location_id: string;
  location_name: string;
  sku_id: string;
  our_ref: string;
  name: string;
  on_hand: number;
  unit_cost_zar: string | null;
  value_zar: string;
};

export type StockValuationReport = {
  total_on_hand: number;
  total_value_zar: string;
  lines: StockValuationLine[];
};

export type AgedStockLine = {
  sku_id: string;
  our_ref: string;
  name: string;
  location_id: string;
  location_name: string;
  on_hand: number;
  value_zar: string;
  days: number;
  bucket: string;
};

export type AgedStockBucket = {
  bucket: string;
  label: string;
  qty: number;
  value_zar: string;
  lines: AgedStockLine[];
};

export type AgedStockReport = {
  buckets: AgedStockBucket[];
  total_qty: number;
  total_value_zar: string;
};

export type SalesBySkuLine = {
  sku_id: string;
  our_ref: string;
  name: string;
  qty: number;
  ex_vat_zar: string;
  inc_vat_zar: string;
};

export type SalesBySkuReport = {
  from_date: string;
  to_date: string;
  lines: SalesBySkuLine[];
  total_qty: number;
  total_ex_vat_zar: string;
  total_inc_vat_zar: string;
};

export type SalesVatReport = {
  from_date: string;
  to_date: string;
  invoice_count: number;
  subtotal_ex_vat: string;
  vat_amount: string;
  total_inc_vat: string;
  amount_paid: string;
};

export type TrialBalanceLine = {
  code: string;
  name: string;
  debit_zar: string;
  credit_zar: string;
};

export type TrialBalanceReport = {
  as_of: string;
  lines: TrialBalanceLine[];
  total_debit_zar: string;
  total_credit_zar: string;
};

export type JournalReportLine = {
  account_code: string;
  account_name: string;
  debit_zar: string;
  credit_zar: string;
};

export type JournalReportEntry = {
  entry_date: string;
  journal_number: string | null;
  document_type: JournalDocumentType;
  source: string | null;
  memo: string | null;
  status: JournalStatus;
  lines: JournalReportLine[];
};

export type JournalReport = {
  from_date: string;
  to_date: string;
  source: string | null;
  entries: JournalReportEntry[];
};

export type CashSummaryAccount = {
  code: string;
  name: string;
  cash_in_zar: string;
  cash_out_zar: string;
  net_zar: string;
};

export type CashSummaryReport = {
  from_date: string;
  to_date: string;
  accounts: CashSummaryAccount[];
  total_cash_in_zar: string;
  total_cash_out_zar: string;
  total_net_zar: string;
};

export function getStockValuation(): Promise<StockValuationReport> {
  return apiFetch<StockValuationReport>("/reports/stock-valuation");
}

export function getAgedStock(): Promise<AgedStockReport> {
  return apiFetch<AgedStockReport>("/reports/aged-stock");
}

export function getSalesBySku(fromDate: string, toDate: string): Promise<SalesBySkuReport> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, reportTodayIso());
  return apiFetch<SalesBySkuReport>(
    `/reports/sales-by-sku?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
}

export function getSalesVat(fromDate: string, toDate: string): Promise<SalesVatReport> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, reportTodayIso());
  return apiFetch<SalesVatReport>(
    `/reports/sales-vat?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
}

export type SkuCriticalityLine = {
  sku_id: string;
  our_ref: string;
  name: string;
  category: string | null;
  qty: number;
  value_zar: string;
  share_pct: number;
  cumulative_pct: number;
  abc_class: "A" | "B" | "C";
  hits_50pct_band: boolean;
  is_a: boolean;
};

export type SkuCriticalityCategoryLine = {
  category: string;
  qty: number;
  value_zar: string;
  share_pct: number;
  cumulative_pct: number;
  abc_class: "A" | "B" | "C";
};

export type SkuCriticalityReport = {
  from_date: string;
  to_date: string;
  sku_count_for_50pct: number;
  sku_count_for_80pct: number;
  top_sku_share_pct: number;
  lines: SkuCriticalityLine[];
  categories: SkuCriticalityCategoryLine[];
};

export function getSkuCriticality(fromDate: string, toDate: string): Promise<SkuCriticalityReport> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, reportTodayIso());
  return apiFetch<SkuCriticalityReport>(
    `/reports/sku-criticality?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
}

export type SupplierLeadTimeRow = {
  supplier_id: string;
  supplier_name: string;
  n: number;
  median_days: number;
  median_last_3_days: number;
  median_water_days: number | null;
  p90_days: number | null;
};

export type SkuLeadTimeRow = {
  sku_id: string;
  our_ref: string;
  name: string;
  manual_lead_time_days: number | null;
  n: number;
  median_days: number;
  median_last_3_days: number;
  median_water_days: number | null;
  p90_days: number | null;
};

export type SupplierLeadTimesReport = {
  rows: SupplierLeadTimeRow[];
};

export type SkuLeadTimesReport = {
  rows: SkuLeadTimeRow[];
};

function normalizeLeadTimeRows<T>(
  payload: { rows?: T[]; lines?: T[] } | T[],
): T[] {
  if (Array.isArray(payload)) {
    return payload;
  }
  return payload.rows ?? payload.lines ?? [];
}

export async function getSupplierLeadTimes(): Promise<SupplierLeadTimesReport> {
  const payload = await apiFetch<
    { rows?: SupplierLeadTimeRow[]; lines?: SupplierLeadTimeRow[] } | SupplierLeadTimeRow[]
  >("/reports/supplier-lead-times");
  return { rows: normalizeLeadTimeRows(payload) };
}

export async function getSkuLeadTimes(): Promise<SkuLeadTimesReport> {
  const payload = await apiFetch<
    { rows?: SkuLeadTimeRow[]; lines?: SkuLeadTimeRow[] } | SkuLeadTimeRow[]
  >("/reports/sku-lead-times");
  return { rows: normalizeLeadTimeRows(payload) };
}

export async function downloadStockValuationCsv(): Promise<void> {
  const response = await fetch("/api/v1/reports/stock-valuation/csv", {
    credentials: "include",
  });
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `stock-valuation-${reportTodayIso()}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export async function downloadAgedStockCsv(): Promise<void> {
  const response = await fetch("/api/v1/reports/aged-stock/csv", {
    credentials: "include",
  });
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `aged-stock-${reportTodayIso()}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export async function downloadSalesBySkuCsv(fromDate: string, toDate: string): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, reportTodayIso());
  const response = await fetch(
    `/api/v1/reports/sales-by-sku/csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    { credentials: "include" },
  );
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `sales-by-sku-${from}-to-${to}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export async function downloadSkuCriticalityCsv(fromDate: string, toDate: string): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, reportTodayIso());
  const response = await fetch(
    `/api/v1/reports/sku-criticality/csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    { credentials: "include" },
  );
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `sku-criticality-${from}-to-${to}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export async function downloadSalesVatCsv(fromDate: string, toDate: string): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, reportTodayIso());
  const response = await fetch(
    `/api/v1/reports/sales-vat/csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    { credentials: "include" },
  );
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `sales-vat-${from}-to-${to}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export async function downloadSupplierLeadTimesCsv(): Promise<void> {
  const response = await fetch("/api/v1/reports/supplier-lead-times/csv", {
    credentials: "include",
  });
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `supplier-lead-times-${reportTodayIso()}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export async function downloadSkuLeadTimesCsv(): Promise<void> {
  const response = await fetch("/api/v1/reports/sku-lead-times/csv", {
    credentials: "include",
  });
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `sku-lead-times-${reportTodayIso()}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function journalsReportQuery(fromDate: string, toDate: string, source?: string): string {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, reportTodayIso());
  const params = new URLSearchParams({ from, to });
  const trimmed = source?.trim();
  if (trimmed) {
    params.set("source", trimmed);
  }
  return params.toString();
}

export function getTrialBalance(asOf: string): Promise<TrialBalanceReport> {
  const date = requireIsoDate(asOf, reportTodayIso());
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
  const to = requireIsoDate(toDate, reportTodayIso());
  return apiFetch<CashSummaryReport>(
    `/reports/cash-summary?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
}

export async function downloadTrialBalanceCsv(asOf: string): Promise<void> {
  const date = requireIsoDate(asOf, reportTodayIso());
  const response = await fetch(
    `/api/v1/reports/trial-balance/csv?as_of=${encodeURIComponent(date)}`,
    { credentials: "include" },
  );
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `trial-balance-${date}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export async function downloadJournalsCsv(
  fromDate: string,
  toDate: string,
  source?: string,
): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, reportTodayIso());
  const response = await fetch(`/api/v1/reports/journals/csv?${journalsReportQuery(fromDate, toDate, source)}`, {
    credentials: "include",
  });
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `journals-${from}-to-${to}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export async function downloadCashSummaryCsv(fromDate: string, toDate: string): Promise<void> {
  const from = requireIsoDate(fromDate, reportMonthStartIso());
  const to = requireIsoDate(toDate, reportTodayIso());
  const response = await fetch(
    `/api/v1/reports/cash-summary/csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    { credentials: "include" },
  );
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `cash-summary-${from}-to-${to}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export type HomeAttentionKind = "low_stock" | "stocktake" | "returns" | "layby" | "bank";

export type HomeAttentionItem = {
  kind: HomeAttentionKind;
  title: string;
  detail: string;
  status: string;
  href: string;
};

export type HomeMovementItem = {
  source: string;
  title: string;
  detail: string;
  created_at: string;
};

export type HomeSummary = {
  on_order_qty: number;
  on_order_value_zar: string;
  on_hand_qty: number;
  on_hand_value_zar: string;
  home_currency: string;
  aged_stock_value_zar: string;
  open_laybys_count: number;
  open_laybys_balance_zar: string;
  low_stock_count: number;
  open_returns_count: number;
  needs_attention: HomeAttentionItem[];
  recent_movements: HomeMovementItem[];
};

export type SkuSearchHit = {
  id: string;
  our_ref: string;
  our_barcode: string;
  name: string;
};

export type PurchaseOrderSearchHit = {
  id: string;
  po_number: string;
  status: string;
  supplier_name: string;
};

export type InvoiceSearchHit = {
  id: string;
  invoice_number: string;
  customer_name: string;
};

export type SearchResponse = {
  q: string;
  skus: SkuSearchHit[];
  purchase_orders: PurchaseOrderSearchHit[];
  invoices: InvoiceSearchHit[];
};

export type AppSettings = {
  vat_rate: string;
  vat_percent: string;
  home_currency: string;
  defaults_locked: boolean;
  warning: string | null;
  always_prefer_warehouse: boolean;
  pick_priority: string[];
};

export type UnitCostAuditEntry = {
  id: string;
  sku_id: string;
  location_id: string | null;
  location_name: string | null;
  po_id: string | null;
  old_cost_zar: string | null;
  new_cost_zar: string;
  changed_by_user_id: string;
  changed_by_email: string;
  changed_by_display_name: string | null;
  source: string;
  note: string | null;
  created_at: string;
};

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

export function searchAll(q: string): Promise<SearchResponse> {
  return apiFetch<SearchResponse>(`/search?q=${encodeURIComponent(q)}`);
}

export function getSettings(): Promise<AppSettings> {
  return apiFetch<AppSettings>("/settings").then(withPickSettings);
}

export function updateSettings(payload: {
  vat_rate?: string;
  home_currency?: string;
  always_prefer_warehouse?: boolean;
  pick_priority?: string[];
}): Promise<AppSettings> {
  return apiFetch<AppSettings>("/settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
  }).then(withPickSettings);
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

export type StockReturnReason = "damaged" | "unwanted" | "wrong_item" | "other";

export type StockReturnDisposition = "restock" | "write_off";

export type StockReturnStatus = "draft" | "completed" | "cancelled";

export type StockReturnLine = {
  id: string;
  invoice_line_id: string;
  sku_id: string | null;
  description: string;
  qty: number;
  unit_ex_vat: string;
};

export type StockReturn = {
  id: string;
  return_number: string;
  invoice_id: string;
  invoice_number: string;
  location_id: string;
  location_name: string;
  credit_note_id: string | null;
  reason: StockReturnReason;
  disposition: StockReturnDisposition;
  status: StockReturnStatus;
  notes: string | null;
  lines: StockReturnLine[];
  created_at: string;
  updated_at: string;
};

export type CreateStockReturnLinePayload = {
  invoice_line_id: string;
  sku_id?: string;
  qty: number;
};

export type CreateStockReturnPayload = {
  invoice_id: string;
  location_id: string;
  reason: StockReturnReason;
  disposition: StockReturnDisposition;
  notes?: string;
  lines: CreateStockReturnLinePayload[];
};

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

export function listReturns(): Promise<StockReturn[]> {
  return apiFetch<StockReturn[]>("/returns");
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

export type LaybyStatus = "open" | "ready" | "completed" | "cancelled";

export type LaybyTender = "cash" | "card";

export type LaybyLine = {
  id: string;
  sku_id: string;
  our_ref: string;
  name: string;
  qty: number;
  unit_ex_vat: string;
};

export type LaybyPayment = {
  id: string;
  amount: string;
  tender: LaybyTender;
  paid_on: string;
};

export type Layby = {
  id: string;
  layby_number: string;
  customer_id: string;
  customer_name: string;
  location_id: string;
  location_name: string;
  invoice_id: string | null;
  due_date: string;
  hold_stock: boolean;
  status: LaybyStatus;
  subtotal_ex_vat: string;
  vat_amount: string;
  total_inc_vat: string;
  amount_paid: string;
  balance: string;
  notes: string | null;
  lines: LaybyLine[];
  payments: LaybyPayment[];
  created_at: string;
  updated_at: string;
};

export type CreateLaybyLinePayload = {
  sku_id: string;
  qty: number;
};

export type CreateLaybyPayload = {
  customer_id: string;
  location_id: string;
  due_date: string;
  hold_stock: boolean;
  deposit_amount: string;
  tender: LaybyTender;
  lines: CreateLaybyLinePayload[];
  notes?: string;
};

export type AddLaybyPaymentPayload = {
  amount: string;
  tender: LaybyTender;
};

export function listLaybys(): Promise<Layby[]> {
  return apiFetch<Layby[]>("/laybys");
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

export type CustomerType = "retail" | "trade";

export type CustomerCrm = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  vat_number: string | null;
  billing_address: string | null;
  customer_type: CustomerType;
  price_tier: string;
  open_invoices_count: number;
  open_invoices_zar: string;
  overdue_invoices_count: number;
  overdue_invoices_zar: string;
  active_laybys_count: number;
  active_laybys_zar: string;
  last_purchase_date: string | null;
  credit_limit: string | null;
  on_hold: boolean;
  on_hold_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type CustomerListFilters = {
  overdue?: boolean;
  active_layby?: boolean;
  on_hold?: boolean;
};

export type CreateCustomerPayload = {
  name: string;
  email?: string;
  phone?: string;
  vat_number?: string;
  billing_address?: string;
  customer_type?: CustomerType;
  price_tier?: string;
  credit_limit?: string | null;
  on_hold?: boolean;
  on_hold_reason?: string | null;
};

export type UpdateCustomerPayload = {
  name?: string;
  email?: string;
  phone?: string;
  vat_number?: string;
  billing_address?: string;
  customer_type?: CustomerType;
  price_tier?: string;
  credit_limit?: string | null;
  on_hold?: boolean;
  on_hold_reason?: string | null;
};

export const CUSTOMER_TYPE_LABELS: Record<CustomerType, string> = {
  retail: "Retail",
  trade: "Trade",
};

export function listCustomers(filters?: CustomerListFilters): Promise<CustomerCrm[]> {
  const params = new URLSearchParams();
  if (filters?.overdue) {
    params.set("overdue", "true");
  }
  if (filters?.active_layby) {
    params.set("active_layby", "true");
  }
  if (filters?.on_hold) {
    params.set("on_hold", "true");
  }
  const qs = params.toString();
  return apiFetch<CustomerCrm[]>(qs ? `/customers?${qs}` : "/customers");
}

export function getCustomer(id: string): Promise<CustomerCrm> {
  return apiFetch<CustomerCrm>(`/customers/${id}`);
}

function buildCustomerPayload(
  payload: CreateCustomerPayload | UpdateCustomerPayload,
): CreateCustomerPayload | UpdateCustomerPayload {
  const body: CreateCustomerPayload | UpdateCustomerPayload = {};
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

export type DeliveryStatus = "draft" | "packed" | "delivered" | "cancelled";

export type DeliverySourceType = "invoice" | "layby";

export type DeliveryLine = {
  id: string;
  sku_id: string | null;
  description: string;
  qty: number;
};

export type Delivery = {
  id: string;
  delivery_number: string;
  source_type: DeliverySourceType;
  invoice_id: string | null;
  invoice_number: string | null;
  layby_id: string | null;
  layby_number: string | null;
  customer_name: string;
  location_id: string;
  location_name: string;
  status: DeliveryStatus;
  delivery_date: string | null;
  notes: string | null;
  lines: DeliveryLine[];
  created_at: string;
  updated_at: string;
};

export type CreateDeliveryPayload = {
  source_type: DeliverySourceType;
  invoice_id?: string;
  layby_id?: string;
  location_id: string;
  notes?: string;
};

export type CompleteDeliveryPayload = {
  delivery_date?: string;
};

export const DELIVERY_STATUS_LABELS: Record<DeliveryStatus, string> = {
  draft: "Draft",
  packed: "Packed",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

export function listDeliveries(): Promise<Delivery[]> {
  return apiFetch<Delivery[]>("/deliveries");
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
  if (notes) {
    body.notes = notes;
  }
  return apiFetch<Delivery>("/deliveries", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function packDelivery(id: string): Promise<Delivery> {
  return apiFetch<Delivery>(`/deliveries/${id}/pack`, { method: "POST" });
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
  return apiFetch<Delivery>(`/deliveries/${id}/complete`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function cancelDelivery(id: string): Promise<Delivery> {
  return apiFetch<Delivery>(`/deliveries/${id}/cancel`, { method: "POST" });
}

export function isInvoiceFullyPaid(invoice: Invoice): boolean {
  if (invoice.amount_paid === invoice.total_inc_vat) {
    return true;
  }
  const paid = Number(invoice.amount_paid);
  const total = Number(invoice.total_inc_vat);
  return Number.isFinite(paid) && Number.isFinite(total) && paid === total;
}

export type ReorderRow = {
  sku_id: string;
  our_ref: string;
  name: string;
  reorder_min: number;
  on_hand: number;
  on_order: number;
  suggested_qty: number;
  preferred_supplier_id: string | null;
  preferred_supplier_name: string | null;
  last_landed_cost_zar: string | null;
};

export type CreateReorderDraftPoResponse = {
  purchase_orders: PurchaseOrder[];
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
