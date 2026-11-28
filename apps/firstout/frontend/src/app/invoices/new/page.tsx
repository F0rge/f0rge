"use client";

import { ErrorNotice } from "@/components/error-notice";
import {
  Button,
  InlineNotification,
  Modal,
  NumberInput,
  RadioButton,
  RadioButtonGroup,
  Stack,
  TextInput,
} from "@carbon/react";
import { Add, TrashCan } from "@carbon/icons-react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { CartEditor, mergeCartBySku, type CartLine } from "@/components/cart-editor";
import { PageLoading } from "@/components/page-loading";
import { PaymentMethodFields } from "@/components/payment-method-fields";
import {
  can,
  canMutateBooks,
  createInvoice,
  formatPriceAmount,
  formatZarAmount,
  parsePriceInput,
  previewInvoicePrices,
  type CreateInvoiceLinePayload,
  type CustomerCrm,
  type PriceList,
  type PaymentMethod,
  type SalesStaffOption,
  type Sku,
  type SalePricePreview,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { quantityRuleRefusal, type QuantityRuleRefusal } from "@/lib/sale-quantity-rule";
import { referenceQueries, useSaleReference } from "@/lib/queries";
import { rememberedColleague } from "@/lib/sales-staff";
import { alignPreviewLines, anyLineBlocked, mayBePriced } from "@/lib/sale-preview";
import { localIsoDate } from "@/lib/dates";

type Loaded = {
  skus: Sku[];
  customers: CustomerCrm[];
  priceLists: PriceList[];
  termsDays: number;
};

/** A line for a service or item that isn't in the catalogue. */
type FreeLine = { key: string; description: string; qty: number; unitExVat: number };

function addDays(iso: string, days: number): string {
  const [year, month, day] = iso.split("-").map(Number);
  return localIsoDate(new Date(year, month - 1, day + days));
}

export default function NewInvoicePage() {
  const { user } = useAuth();
  const reference = useSaleReference();
  const settings = useQuery(referenceQueries.settings);
  const staff = useQuery(referenceQueries.salesStaffOptions);
  const loaded: Loaded | null = reference.data && settings.data
    ? { ...reference.data, termsDays: settings.data.payment_terms_days }
    : null;
  const failure = reference.error ?? settings.error;
  const loadError = failure && !loaded
    ? failure.message || "Could not load the invoice form."
    : null;
  const colleagues = staff.data ?? null;
  const colleaguesError = staff.isError;

  if (loadError) {
    return (
      <Stack gap={5}>
        <h1 className="cds--type-heading-05">Create invoice</h1>
        <InlineNotification kind="error" title="Could not load the invoice form" subtitle={loadError} hideCloseButton lowContrast />
        <div><Button kind="tertiary" href="/invoices">Back to invoices</Button></div>
      </Stack>
    );
  }
  if (!loaded) return <PageLoading label="Loading invoice form…" />;
  if (!canMutateBooks(user)) {
    return (
      <InlineNotification
        kind="warning"
        title="You can't create invoices"
        subtitle="Creating invoices needs the books permission."
        hideCloseButton
        lowContrast
      />
    );
  }
  return (
    <InvoiceForm
      loaded={loaded}
      colleagues={colleagues}
      colleaguesError={colleaguesError}
      canDiscount={can(user, "till.discount")}
    />
  );
}

function InvoiceForm({
  loaded, colleagues, colleaguesError, canDiscount,
}: {
  loaded: Loaded;
  colleagues: SalesStaffOption[] | null;
  colleaguesError: boolean;
  canDiscount: boolean;
}) {
  const router = useRouter();
  const { skus, customers, priceLists } = loaded;
  const [customerId, setCustomerId] = useState("");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [freeLines, setFreeLines] = useState<FreeLine[]>([]);
  const [freeOpen, setFreeOpen] = useState(false);
  const [salesStaffId, setSalesStaffId] = useState(rememberedColleague);
  const [notePrinted, setNotePrinted] = useState("");
  const [noteInternal, setNoteInternal] = useState("");
  const [issueDate, setIssueDate] = useState(localIsoDate);
  const [dueOverride, setDueOverride] = useState("");
  const [paid, setPaid] = useState(false);
  const [method, setMethod] = useState<PaymentMethod>("eft");
  const [reference, setReference] = useState("");
  const [paidOn, setPaidOn] = useState(localIsoDate);
  const [skuId, setSkuId] = useState("");
  const [qty, setQty] = useState<number | "">(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<QuantityRuleRefusal | null>(null);
  const canBreakBatches = can(useAuth().user, "sales.price_override");
  const [pricing, setPricing] = useState<{ key: string; preview?: SalePricePreview; error?: string } | null>(null);
  const [pricingAttempt, setPricingAttempt] = useState(0);

  const selectedCustomer = customers.find((row) => row.id === customerId) ?? null;
  const products = useMemo(
    () => skus.filter((sku) => !sku.is_archived && sku.is_sellable && mayBePriced(sku, selectedCustomer, priceLists)),
    [priceLists, selectedCustomer, skus],
  );
  // SKU lines first, in cart order, so the preview's lines line up with the cart.
  const lines = useMemo<CreateInvoiceLinePayload[]>(() => [
    ...cart.map((line) => ({
      description: line.sku.name,
      sku_id: line.sku.id,
      qty: line.qty,
      discount_percent: String(line.discountPercent),
    })),
    ...freeLines.map((line) => ({
      description: line.description,
      qty: line.qty,
      unit_ex_vat: formatPriceAmount(line.unitExVat),
    })),
  ], [cart, freeLines]);
  const pricingKey = JSON.stringify({ customerId, lines, pricingAttempt });
  const preview = pricing?.key === pricingKey ? pricing.preview : undefined;
  const pricingError = pricing?.key === pricingKey ? pricing.error : undefined;

  useEffect(() => {
    if (!customerId || !lines.length) return;
    const controller = new AbortController();
    previewInvoicePrices({ customer_id: customerId, lines }, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setPricing({ key: pricingKey, preview: result });
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setPricing({ key: pricingKey, error: err instanceof Error ? err.message : "Could not check the invoice prices." });
        }
      });
    return () => controller.abort();
  }, [customerId, lines, pricingKey]);

  const termsDays = selectedCustomer?.payment_terms_days ?? loaded.termsDays;
  const dueDate = dueOverride || addDays(issueDate, termsDays);
  const dueInvalid = dueDate < issueDate;
  const colleagueChosen = !colleagues?.length || colleagues.some((item) => item.id === salesStaffId);
  const missing = [
    !customerId && "a customer",
    !lines.length && "at least one line",
    !colleagueChosen && "a sales colleague",
  ].filter((item): item is string => !!item);
  const valid = !missing.length && !!issueDate && !dueInvalid && (!paid || !!paidOn) && !anyLineBlocked(preview);

  async function create() {
    if (!valid || saving) return;
    setSaving(true);
    setError(null);
    try {
      const created = await createInvoice({
        customer_id: customerId,
        issue_date: issueDate,
        lines,
        note_printed: notePrinted.trim() || null,
        note_internal: noteInternal.trim() || null,
        ...(dueOverride ? { due_date: dueOverride } : {}),
        sales_staff_id: salesStaffId || null,
        payment: paid ? { tender: method, reference: reference.trim() || undefined, paid_on: paidOn } : null,
      });
      router.push(`/invoices/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the invoice.");
      setRefusal(quantityRuleRefusal(err));
      setSaving(false);
    }
  }

  // Free-text lines follow the cart's lines in the request, so their prices follow in the preview.
  const freePrices = alignPreviewLines(lines.map((line) => line.sku_id ?? null), preview).slice(cart.length);
  const total = preview ? formatZarAmount(formatPriceAmount(Number(preview.total_inc_vat))) : null;

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-heading-05">Create invoice</h1>
          <p className="cds--type-body-01">Tax invoices with VAT at the team&apos;s rate.</p>
        </div>
      </div>

      <ErrorNotice error={error} onClose={() => setError(null)} />

      <CartEditor
        mode="invoice"
        title="Invoice lines"
        canBreakBatches={canBreakBatches}
        quantityRefusal={refusal}
        products={products}
        cart={cart}
        onAdd={(sku, quantity) => {
          setCart((current) => mergeCartBySku(current, sku, quantity));
          return true;
        }}
        onUpdateLine={(key, patch) =>
          setCart((current) => current.map((line) => (line.key === key ? { ...line, ...patch } : line)))
        }
        onRemoveLine={(key) => setCart((current) => current.filter((line) => line.key !== key))}
        skuId={skuId}
        onSkuIdChange={setSkuId}
        qty={qty}
        onQtyChange={setQty}
        customers={customers}
        customerId={customerId}
        onCustomerChange={setCustomerId}
        selectedCustomer={selectedCustomer}
        preview={preview}
        pricingError={pricingError}
        onRetryPricing={() => setPricingAttempt((attempt) => attempt + 1)}
        canDiscount={canDiscount}
        colleagues={colleagues}
        colleaguesError={colleaguesError}
        salesStaffId={salesStaffId}
        onSalesStaffChange={setSalesStaffId}
        notePrinted={notePrinted}
        onNotePrintedChange={setNotePrinted}
        noteInternal={noteInternal}
        onNoteInternalChange={setNoteInternal}
        lineCount={lines.length}
        afterLines={
          <Stack gap={4}>
            {freeLines.map((line, index) => (
              <div key={line.key} className="firstout-sale-summary__row">
                <div>
                  <p className="cds--type-heading-compact-01">{line.description}</p>
                  <p className="cds--type-helper-text-01">
                    Free-text line · {line.qty} × {formatZarAmount(formatPriceAmount(line.unitExVat))} excl. VAT
                  </p>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span className="cds--type-body-01">
                    {formatZarAmount(freePrices[index]?.inc_vat ?? null)}
                  </span>
                  <Button
                    kind="ghost"
                    size="sm"
                    hasIconOnly
                    renderIcon={TrashCan}
                    iconDescription={`Remove ${line.description}`}
                    onClick={() => setFreeLines((current) => current.filter((item) => item.key !== line.key))}
                  />
                </div>
              </div>
            ))}
            <div>
              <Button kind="ghost" size="sm" renderIcon={Add} onClick={() => setFreeOpen(true)}>
                Add free-text line
              </Button>
            </div>
          </Stack>
        }
      >
        <TextInput
          id="invoice-issue-date"
          labelText="Issue date"
          type="date"
          value={issueDate}
          onChange={(event) => setIssueDate(event.target.value)}
          invalid={!issueDate}
          invalidText="Choose the issue date."
        />
        <TextInput
          id="invoice-due-date"
          labelText="Due date"
          type="date"
          value={dueDate}
          onChange={(event) => setDueOverride(event.target.value)}
          invalid={dueInvalid}
          invalidText="The due date can't be before the issue date."
          helperText={
            dueOverride
              ? "Set by hand."
              : selectedCustomer?.payment_terms_days != null
                ? `${termsDays}-day terms for ${selectedCustomer.name}.`
                : `${termsDays}-day default terms.`
          }
        />
        <RadioButtonGroup
          legendText="Payment"
          name="invoice-payment"
          orientation="vertical"
          valueSelected={paid ? "paid" : "account"}
          onChange={(value) => setPaid(value === "paid")}
        >
          <RadioButton
            id="invoice-payment-account"
            value="account"
            labelText="On account (unpaid): goes on the customer's statement; record payments later"
          />
          <RadioButton
            id="invoice-payment-paid"
            value="paid"
            labelText={total ? `Already paid: records a payment of ${total}` : "Already paid: records a payment of the total"}
          />
        </RadioButtonGroup>
        {paid ? (
          <Stack gap={5}>
            <PaymentMethodFields
              idPrefix="invoice-new-payment"
              method={method}
              reference={reference}
              onMethodChange={setMethod}
              onReferenceChange={setReference}
            />
            <TextInput
              id="invoice-paid-on"
              labelText="Paid on"
              type="date"
              value={paidOn}
              onChange={(event) => setPaidOn(event.target.value)}
              invalid={!paidOn}
              invalidText="Choose the payment date."
            />
          </Stack>
        ) : null}
        {missing.length ? (
          <p className="cds--type-helper-text-01">
            To create the invoice, add {missing.join(", ").replace(/, ([^,]*)$/, " and $1")}.
          </p>
        ) : null}
        <div className="firstout-catalogue-actions">
          <Button kind="secondary" href="/invoices">Cancel</Button>
          <Button disabled={!valid || saving} onClick={() => void create()}>
            {saving ? "Creating…" : "Create invoice"}
          </Button>
        </div>
      </CartEditor>

      {freeOpen ? (
        <FreeLineModal
          onClose={() => setFreeOpen(false)}
          onAdd={(line) => {
            setFreeLines((current) => [...current, line]);
            setFreeOpen(false);
          }}
        />
      ) : null}
    </Stack>
  );
}

function FreeLineModal({ onAdd, onClose }: { onAdd: (line: FreeLine) => void; onClose: () => void }) {
  const [description, setDescription] = useState("");
  const [qty, setQty] = useState<number | "">(1);
  const [unit, setUnit] = useState("");
  const unitValue = parsePriceInput(unit);
  const qtyValid = typeof qty === "number" && Number.isInteger(qty) && qty >= 1;
  const unitInvalid = unit.trim() !== "" && (unitValue === null || unitValue <= 0);
  const ok = !!description.trim() && qtyValid && unitValue !== null && unitValue > 0;
  return (
    <Modal
      open
      size="sm"
      modalLabel="Invoice lines"
      modalHeading="Add free-text line"
      primaryButtonText="Add line"
      secondaryButtonText="Cancel"
      primaryButtonDisabled={!ok}
      onRequestClose={onClose}
      onRequestSubmit={() => {
        if (!ok || unitValue === null || typeof qty !== "number") return;
        onAdd({ key: crypto.randomUUID(), description: description.trim(), qty, unitExVat: unitValue });
      }}
    >
      <Stack gap={5}>
        <TextInput
          id="free-line-description"
          labelText="Description"
          helperText="For services or items that aren't in the catalogue."
          maxLength={512}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          data-modal-primary-focus
        />
        <NumberInput
          id="free-line-qty"
          label="Qty"
          min={1}
          step={1}
          value={qty}
          invalid={!qtyValid}
          invalidText="Enter a whole number of 1 or more."
          onChange={(_, { value }) => setQty(value === "" ? "" : Number(value))}
        />
        <TextInput
          id="free-line-unit"
          labelText="Unit ex VAT"
          inputMode="decimal"
          value={unit}
          onChange={(event) => setUnit(event.target.value)}
          invalid={unitInvalid}
          invalidText="Enter an amount above zero."
        />
      </Stack>
    </Modal>
  );
}
