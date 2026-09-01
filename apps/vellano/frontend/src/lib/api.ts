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
  wholesale_ex_vat: string | null;
  wholesale_inc_vat: string | null;
  retail_ex_vat: string | null;
  retail_inc_vat: string | null;
  created_at: string;
  updated_at: string;
};

export type UpdateSkuPricePayload = {
  wholesale_ex_vat?: string | number | null;
  wholesale_inc_vat?: string | number | null;
  retail_ex_vat?: string | number | null;
  retail_inc_vat?: string | number | null;
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

export function updateSku(id: string, payload: UpdateSkuPricePayload): Promise<Sku> {
  return apiFetch<Sku>(`/skus/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
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

export function canTransfer(role: UserRole | undefined): boolean {
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

export type TransferPayload = {
  from_location_id: string;
  to_location_id: string;
  sku_id: string;
  qty: number;
};

export type TransferResult = {
  sku_id: string;
  our_ref: string;
  name: string;
  qty: number;
  from_location: {
    location_id: string;
    location_name: string;
    on_hand: number;
    unit_cost_zar: string | null;
  };
  to_location: {
    location_id: string;
    location_name: string;
    on_hand: number;
    unit_cost_zar: string | null;
  };
};

export function createTransfer(payload: TransferPayload): Promise<TransferResult> {
  return apiFetch<TransferResult>("/transfers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function canMutateBooks(role: UserRole | undefined): boolean {
  return role === "owner" || role === "books";
}

export type AccountType = "asset" | "liability" | "income" | "expense";

export type Account = {
  id: string;
  code: string;
  name: string;
  type: AccountType;
  is_system: boolean;
  is_archived: boolean;
  balance_zar: string;
  created_at: string;
  updated_at: string;
};

export type CreateAccountPayload = {
  code: string;
  name: string;
  type: AccountType;
};

export type UpdateAccountPayload = {
  name?: string;
  is_archived?: boolean;
};

export const ACCOUNT_TYPES: { value: AccountType; label: string }[] = [
  { value: "asset", label: "Asset" },
  { value: "liability", label: "Liability" },
  { value: "income", label: "Income" },
  { value: "expense", label: "Expense" },
];

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

export function createPayment(payload: CreatePaymentPayload): Promise<Payment> {
  return apiFetch<Payment>("/payments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
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
  matched_payment_number: string | null;
  suggested_payment_id: string | null;
  suggested_payment_number: string | null;
};

export type BankImport = {
  id: string;
  filename: string;
  line_count: number;
  lines: BankImportLine[];
  created_at: string;
  updated_at: string;
};

export type BankImportSummary = {
  id: string;
  filename: string;
  line_count: number;
  matched_count: number;
  created_at: string;
};

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

export async function uploadBankImport(file: File): Promise<BankImport> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch("/api/v1/bank-imports", {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<BankImport>;
}

export function matchBankLine(
  importId: string,
  lineId: string,
  paymentId: string,
): Promise<BankImportLine> {
  return apiFetch<BankImportLine>(`/bank-imports/${importId}/lines/${lineId}/match`, {
    method: "POST",
    body: JSON.stringify({ payment_id: paymentId }),
  });
}

export function getAgedAr(asOf: string): Promise<AgedReport> {
  return apiFetch<AgedReport>(`/reports/aged-ar?as_of=${encodeURIComponent(asOf)}`);
}

export function getAgedAp(asOf: string): Promise<AgedReport> {
  return apiFetch<AgedReport>(`/reports/aged-ap?as_of=${encodeURIComponent(asOf)}`);
}

export function getProfitLoss(fromDate: string, toDate: string): Promise<ProfitLossReport> {
  return apiFetch<ProfitLossReport>(
    `/reports/profit-loss?from=${encodeURIComponent(fromDate)}&to=${encodeURIComponent(toDate)}`,
  );
}

export function getBalanceSheet(asOf: string): Promise<BalanceSheetReport> {
  return apiFetch<BalanceSheetReport>(
    `/reports/balance-sheet?as_of=${encodeURIComponent(asOf)}`,
  );
}

export function getVat201Draft(fromDate: string, toDate: string): Promise<Vat201Draft> {
  return apiFetch<Vat201Draft>(
    `/reports/vat201?from=${encodeURIComponent(fromDate)}&to=${encodeURIComponent(toDate)}`,
  );
}

export async function downloadVat201Csv(fromDate: string, toDate: string): Promise<void> {
  const response = await fetch(
    `/api/v1/reports/vat201/csv?from=${encodeURIComponent(fromDate)}&to=${encodeURIComponent(toDate)}`,
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
  anchor.download = `vat201-draft-${fromDate}-to-${toDate}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export async function downloadVat201Pdf(fromDate: string, toDate: string): Promise<void> {
  const response = await fetch(
    `/api/v1/reports/vat201/pdf?from=${encodeURIComponent(fromDate)}&to=${encodeURIComponent(toDate)}`,
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
  anchor.download = `vat201-draft-${fromDate}-to-${toDate}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
