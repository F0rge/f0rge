import type {
  CreatePurchaseOrderPayload,
  Proforma,
  Sku,
  Supplier,
} from "@/lib/api";
import type { SupplierCodeLine } from "@/lib/po-supplier-code";

export type OrderLine = SupplierCodeLine & {
  description: string;
  notes: string;
  qty: number | "";
  factory_unit_amount: string;
};
export type OrderDraft = {
  supplier_id: string;
  proforma_id: string;
  supplier_ref: string;
  notes: string;
  submit_for_approval: boolean;
  lines: OrderLine[];
};
export type FormErrors = Record<string, string>;
export const MAX_ORDER_QUANTITY = 9_999_999_999;
export type ComposerChoices = {
  suppliers: Pick<Supplier, "id" | "is_archived" | "default_currency">[];
  proformas: Pick<Proforma, "id" | "supplier_id" | "is_archived">[];
  skus: Pick<Sku, "id" | "is_archived">[];
};
export const lineFieldId = (line: OrderLine, field: string) =>
  `po-line-${field}-${line.key}`;
export function newOrderLine(): OrderLine {
  return {
    key: crypto.randomUUID(),
    sku_id: "",
    supplier_code: "",
    supplierCodeTouched: false,
    description: "",
    notes: "",
    qty: 1,
    factory_unit_amount: "",
  };
}
export function newOrderDraft(): OrderDraft {
  return {
    supplier_id: "",
    proforma_id: "",
    supplier_ref: "",
    notes: "",
    submit_for_approval: false,
    lines: [newOrderLine()],
  };
}
/**
 * A new order for one SKU (`/purchase-orders?new=1&prefill_sku=<id>`): its preferred supplier when
 * that supplier can still be ordered from, otherwise the supplier is left to the user.
 */
export function prefilledOrderDraft(
  sku: Pick<Sku, "id" | "preferred_supplier_id">,
  suppliers: readonly Pick<Supplier, "id" | "is_archived">[],
): OrderDraft {
  const draft = newOrderDraft();
  const supplier = suppliers.find((item) => item.id === sku.preferred_supplier_id && !item.is_archived);
  return { ...draft, supplier_id: supplier?.id ?? "", lines: [{ ...draft.lines[0], sku_id: sku.id }] };
}
export function isPositiveDecimal(value: string): boolean {
  return /^\d+(?:\.\d+)?$/.test(value.trim()) && /[1-9]/.test(value);
}
function factoryPrecisionError(value: string): string | undefined {
  const [whole, fraction = ""] = value.trim().split(".");
  if (fraction.length > 4)
    return "Use at most 4 decimal places for a factory amount.";
  if (whole.replace(/^0+/, "").length > 14)
    return "Use at most 14 digits before the decimal point.";
}
export function validateOrderDraft(
  draft: OrderDraft,
  choices: ComposerChoices,
  includeLines = true,
): FormErrors {
  const errors: FormErrors = {};
  if (
    !choices.suppliers.some(
      (supplier) => supplier.id === draft.supplier_id && !supplier.is_archived,
    )
  )
    errors["po-supplier"] = "Choose an active supplier.";
  if (draft.supplier_ref.trim().length > 128)
    errors["po-supplier-ref"] = "Use 128 characters or fewer.";
  if (
    draft.proforma_id &&
    !choices.proformas.some(
      (proforma) =>
        proforma.id === draft.proforma_id &&
        proforma.supplier_id === draft.supplier_id &&
        !proforma.is_archived,
    )
  )
    errors["po-proforma"] =
      "Choose an active proforma belonging to this supplier.";
  if (!includeLines) return errors;
  if (!draft.lines.length)
    errors["po-lines-heading"] = "Add at least one order line.";
  const selected = new Set<string>();
  for (const line of draft.lines) {
    if (
      line.sku_id &&
      !choices.skus.some((sku) => sku.id === line.sku_id && !sku.is_archived)
    )
      errors[lineFieldId(line, "sku")] =
        "Choose an active SKU, or clear it and describe the item.";
    if (line.sku_id && selected.has(line.sku_id))
      errors[lineFieldId(line, "sku")] =
        "This SKU is already on the order. Increase its quantity instead.";
    if (line.sku_id) selected.add(line.sku_id);
    if (!line.sku_id && !line.description.trim())
      errors[lineFieldId(line, "description")] =
        "Choose a SKU or enter an item description.";
    if (line.description.trim().length > 512)
      errors[lineFieldId(line, "description")] = "Use 512 characters or fewer.";
    if (line.supplier_code.trim().length > 128)
      errors[lineFieldId(line, "code")] = "Use 128 characters or fewer.";
    if (line.supplierCodeLookup)
      errors[lineFieldId(line, "code")] =
        line.supplierCodeLookup.status === "loading"
          ? "Wait for the supplier code lookup to finish."
          : "Retry the supplier code lookup or enter a code yourself.";
    if (
      typeof line.qty !== "number" ||
      !Number.isSafeInteger(line.qty) ||
      line.qty < 1 ||
      line.qty > MAX_ORDER_QUANTITY
    )
      errors[lineFieldId(line, "qty")] =
        "Enter a whole number from 1 to 9,999,999,999.";
    if (!isPositiveDecimal(line.factory_unit_amount))
      errors[lineFieldId(line, "factory")] =
        "Enter a factory unit amount greater than zero.";
    else {
      const precisionError = factoryPrecisionError(line.factory_unit_amount);
      if (precisionError) errors[lineFieldId(line, "factory")] = precisionError;
    }
  }
  return errors;
}
export function orderRequiresApproval(draft: OrderDraft): boolean {
  return draft.submit_for_approval || draft.lines.some((line) => !line.sku_id);
}
export function createOrderPayload(
  draft: OrderDraft,
): CreatePurchaseOrderPayload {
  return {
    supplier_id: draft.supplier_id,
    proforma_id: draft.proforma_id || undefined,
    supplier_ref: draft.supplier_ref.trim() || null,
    notes: draft.notes.trim() || null,
    submit_for_approval: draft.submit_for_approval,
    lines: draft.lines.map((line) => {
      if (
        typeof line.qty !== "number" ||
        !Number.isSafeInteger(line.qty) ||
        line.qty < 1 ||
        line.qty > MAX_ORDER_QUANTITY ||
        !isPositiveDecimal(line.factory_unit_amount) ||
        factoryPrecisionError(line.factory_unit_amount)
      )
        throw new Error(
          "Check the quantities and factory unit amounts before creating this order.",
        );
      return {
        sku_id: line.sku_id || null,
        supplier_code: line.supplier_code.trim() || null,
        description: line.description.trim() || null,
        notes: line.notes.trim() || null,
        qty: line.qty,
        factory_unit_amount: line.factory_unit_amount.trim(),
      };
    }),
  };
}
/** Sum factory decimal strings exactly; no retail VAT or floating-point arithmetic. */
export function factoryTotal(
  lines: { qty: number | ""; factory_unit_amount: string | null }[],
): string | null {
  if (
    !lines.length ||
    lines.some(
      (line) =>
        typeof line.qty !== "number" ||
        !Number.isSafeInteger(line.qty) ||
        line.qty < 1 ||
        !line.factory_unit_amount ||
        !isPositiveDecimal(line.factory_unit_amount),
    )
  )
    return null;
  const scale = Math.max(
    ...lines.map(
      (line) => (line.factory_unit_amount!.trim().split(".")[1] || "").length,
    ),
  );
  let sum = BigInt(0);
  for (const line of lines) {
    const [whole, fraction = ""] = line.factory_unit_amount!.trim().split(".");
    sum += BigInt(whole + fraction.padEnd(scale, "0")) * BigInt(line.qty);
  }
  const digits = sum.toString().padStart(scale + 1, "0");
  return scale ? `${digits.slice(0, -scale)}.${digits.slice(-scale)}` : digits;
}
export function formatFactoryAmount(
  value: string | null,
  currency: string | null,
): string {
  if (value === null) return "—";
  if (!currency) return "Currency unavailable";
  const [whole, fraction = ""] = value.split(".");
  const decimals = fraction.replace(/0+$/, "").padEnd(2, "0");
  return `${currency === "ZAR" ? "R" : currency} ${whole.replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0")}.${decimals}`;
}
