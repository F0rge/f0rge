export type UserRole = "owner" | "buyer" | "warehouse" | "till" | "books";

export type Team = {
  id: string;
  name: string;
};

export type AuthUser = {
  id: string;
  email: string;
  role: UserRole;
  team: Team;
  display_name: string | null;
};

export type User = {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_disabled: boolean;
  team_id: string;
  team: Team;
};

export type LoginResponse = {
  email: string;
};

export type CreateUserPayload = {
  email: string;
  password: string;
  role: UserRole;
  display_name?: string;
};

export type UpdateUserPayload = {
  email?: string;
  password?: string;
  role?: UserRole;
  display_name?: string;
  is_disabled?: boolean;
};

export type UpdateProfilePayload = {
  email?: string;
  display_name?: string;
  password?: string;
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

export function updateProfile(payload: UpdateProfilePayload): Promise<AuthUser> {
  return apiFetch<AuthUser>("/profile", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export const USER_ROLES: { value: UserRole; label: string }[] = [
  { value: "owner", label: "Owner" },
  { value: "buyer", label: "Buyer" },
  { value: "warehouse", label: "Warehouse" },
  { value: "till", label: "Till" },
  { value: "books", label: "Books" },
];

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

export function canMutateCatalogue(role: UserRole | undefined): boolean {
  return role === "owner" || role === "buyer";
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
  supplier_ref: string | null;
  photo_storage_key: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateSkuPayload = {
  our_ref: string;
  our_barcode: string;
  name: string;
  design: string;
  fabric: string;
  supplier_ref?: string;
};

export function listSkus(): Promise<Sku[]> {
  return apiFetch<Sku[]>("/skus");
}

export function createSku(payload: CreateSkuPayload): Promise<Sku> {
  return apiFetch<Sku>("/skus", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function uploadSkuPhoto(id: string, photo: File): Promise<Sku> {
  const formData = new FormData();
  formData.append("photo", photo);
  return apiUpload<Sku>(`/skus/${id}/photo`, formData);
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
  }[];
};

export const PO_STATUS_LABELS: Record<PurchaseOrderStatus, string> = {
  open: "Open",
  on_water: "On water",
  landed: "Landed",
  received: "Received",
};

export function canRaisePo(role: UserRole | undefined): boolean {
  return role === "owner" || role === "buyer";
}

export function canReceive(role: UserRole | undefined): boolean {
  return role === "owner" || role === "warehouse";
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
}): Promise<void> {
  return apiFetch<void>("/receive", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listInventory(): Promise<InventorySku[]> {
  return apiFetch<InventorySku[]>("/inventory");
}
