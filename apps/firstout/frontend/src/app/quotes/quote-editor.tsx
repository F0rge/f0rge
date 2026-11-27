"use client";

import { Button, InlineNotification, Modal, Stack, Tag, TextInput } from "@carbon/react";
import { Copy, Download, Purchase, TrashCan, View } from "@carbon/icons-react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { CartEditor, mergeCartBySku, type CartLine } from "@/components/cart-editor";
import { PageLoading } from "@/components/page-loading";
import {
  ApiError,
  can,
  canMutateQuotes,
  canUseTill,
  createQuote,
  deleteQuote,
  downloadQuotePdf,
  duplicateQuote,
  formatZarAmount,
  getQuote,
  getSku,
  previewQuotePdf,
  previewQuotePrices,
  replaceQuote,
  type CreateQuotePayload,
  type CustomerCrm,
  type PriceList,
  type Quote,
  type SalesStaffOption,
  type Sku,
  type SalePricePreview,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { quantityRuleRefusal, type QuantityRuleRefusal } from "@/lib/sale-quantity-rule";
import { referenceQueries, useSaleReference } from "@/lib/queries";
import { anyLineBlocked, mayBePriced } from "@/lib/sale-preview";
import { defaultValidUntil, isQuoteOpen, quoteState, quoteStateInfo } from "@/lib/quote-state";
import { rememberedColleague } from "@/lib/sales-staff";

const WALK_IN_CUSTOMER_NAME = "Walk-in customer";

type Loaded = {
  skus: Sku[];
  customers: CustomerCrm[];
  priceLists: PriceList[];
  quote: Quote | null;
};

/** New quote (no id) or an existing one: the till's cart in quote mode. */
export function QuoteEditor({ id }: { id?: string }) {
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateQuotes(user);
  const reference = useSaleReference();
  const client = useQueryClient();
  // A saved new quote becomes an edit of that quote before the route changes.
  const [quoteId, setQuoteId] = useState(id);
  const quoteQuery = useQuery({
    queryKey: ["quotes", quoteId],
    queryFn: () => getQuote(quoteId!),
    enabled: Boolean(quoteId),
    // The form seeds once from this quote; never seed it from a copy cached by an earlier visit.
    gcTime: 0,
  });
  const staff = useQuery(referenceQueries.salesStaffOptions);
  const quote = quoteQuery.data ?? null;
  const loaded: Loaded | null = reference.data && (!quoteId || quote) ? { ...reference.data, quote } : null;
  const failure = reference.error ?? quoteQuery.error;
  const loadError = failure && !loaded ? failure.message || "Could not load the quote." : null;
  const colleagues = staff.data ?? null;
  const colleaguesError = staff.isError;

  if (loadError) {
    return (
      <Stack gap={5}>
        <h1 className="cds--type-heading-05">{id ? "Quote" : "New quote"}</h1>
        <InlineNotification kind="error" title="Could not load the quote" subtitle={loadError} hideCloseButton lowContrast />
        <div><Button kind="tertiary" href="/quotes">Back to quotes</Button></div>
      </Stack>
    );
  }
  if (!loaded) return <PageLoading label="Loading quote…" />;
  return (
    <QuoteForm
      // A saved new quote becomes an edit of that quote.
      key={loaded.quote?.id ?? "new"}
      loaded={loaded}
      colleagues={colleagues}
      colleaguesError={colleaguesError}
      canMutate={canMutate}
      canSell={canUseTill(user)}
      canDiscount={can(user, "till.discount")}
      onSaved={(quote) => {
        client.setQueryData(["quotes", quote.id], quote);
        setQuoteId(quote.id);
        if (!id) router.replace(`/quotes/${quote.id}`);
      }}
    />
  );
}

function QuoteForm({
  loaded, colleagues, colleaguesError, canMutate, canSell, canDiscount, onSaved,
}: {
  loaded: Loaded;
  colleagues: SalesStaffOption[] | null;
  colleaguesError: boolean;
  canMutate: boolean;
  canSell: boolean;
  canDiscount: boolean;
  onSaved: (quote: Quote) => void;
}) {
  const router = useRouter();
  const { skus, customers, priceLists, quote } = loaded;
  const editable = canMutate && (!quote || isQuoteOpen(quote));
  const walkIn = customers.find((row) => row.name === WALK_IN_CUSTOMER_NAME);
  const [customerId, setCustomerId] = useState(quote?.customer_id ?? walkIn?.id ?? "");
  const [cart, setCart] = useState<CartLine[]>(() => (quote?.lines ?? []).flatMap((line) => {
    const sku = skus.find((item) => item.id === line.sku_id);
    return sku ? [{ key: line.id, sku, qty: line.qty, discountPercent: Number(line.discount_percent) }] : [];
  }));
  const [salesStaffId, setSalesStaffId] = useState(quote ? quote.sales_staff_id ?? "" : rememberedColleague());
  const [notePrinted, setNotePrinted] = useState(quote?.notes ?? "");
  const [noteInternal, setNoteInternal] = useState(quote?.internal_note ?? "");
  const [validUntil, setValidUntil] = useState(quote ? quote.valid_until ?? "" : defaultValidUntil());
  const [skuId, setSkuId] = useState("");
  const [qty, setQty] = useState<number | "">(1);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<QuantityRuleRefusal | null>(null);
  const canBreakBatches = can(useAuth().user, "sales.price_override");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [pricing, setPricing] = useState<{ key: string; preview?: SalePricePreview; error?: string } | null>(null);
  const [pricingAttempt, setPricingAttempt] = useState(0);
  const missingLines = (quote?.lines ?? []).filter((line) => !skus.some((sku) => sku.id === line.sku_id));

  // Lines on an archived SKU are not in the catalogue list; fetch them once.
  useEffect(() => {
    if (!missingLines.length) return;
    let live = true;
    Promise.all(missingLines.map((line) => getSku(line.sku_id))).then((found) => {
      if (!live) return;
      setCart((current) => [
        ...current,
        ...missingLines.flatMap((line, index) => current.some((row) => row.key === line.id) ? [] : [{
          key: line.id, sku: found[index], qty: line.qty, discountPercent: Number(line.discount_percent),
        }]),
      ]);
    }).catch(() => { if (live) setError("A product on this quote could not be loaded."); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per loaded quote
  }, [quote?.id]);

  const selectedCustomer = customers.find((row) => row.id === customerId) ?? null;
  const products = useMemo(
    () => skus.filter((sku) => !sku.is_archived && sku.is_sellable && mayBePriced(sku, selectedCustomer, priceLists)),
    [priceLists, selectedCustomer, skus],
  );
  const lines = useMemo(() => cart.map((line) => ({
    sku_id: line.sku.id, qty: line.qty, discount_percent: line.discountPercent,
  })), [cart]);
  const pricingKey = JSON.stringify({ customerId, lines, pricingAttempt });
  const preview = pricing?.key === pricingKey ? pricing.preview : undefined;
  const pricingError = pricing?.key === pricingKey ? pricing.error : undefined;

  useEffect(() => {
    if (!customerId || !lines.length) return;
    const controller = new AbortController();
    previewQuotePrices(
      { customer_id: customerId, lines, ...(quote ? { quote_id: quote.id } : {}) },
      controller.signal,
    ).then((result) => {
      if (!controller.signal.aborted) setPricing({ key: pricingKey, preview: result });
    }).catch((err: unknown) => {
      if (!controller.signal.aborted) {
        setPricing({ key: pricingKey, error: err instanceof Error ? err.message : "Could not check the quote prices." });
      }
    });
    return () => controller.abort();
  }, [customerId, lines, pricingKey, quote]);

  const change = <T,>(setter: (value: T) => void) => (value: T) => {
    setter(value);
    setDirty(true);
  };
  const colleagueChosen = !colleagues?.length || colleagues.some((item) => item.id === salesStaffId);
  const valid = editable && !!customerId && cart.length > 0 && colleagueChosen && !!validUntil &&
    !anyLineBlocked(preview);

  function payload(): CreateQuotePayload {
    return {
      customer_id: customerId,
      lines: lines.map((line) => ({ ...line, discount_percent: String(line.discount_percent) })),
      notes: notePrinted.trim() || null,
      internal_note: noteInternal.trim() || null,
      valid_until: validUntil || null,
      sales_staff_id: salesStaffId || null,
    };
  }

  async function save(): Promise<Quote | null> {
    if (!valid || saving) return null;
    setSaving(true);
    setError(null);
    try {
      const saved = quote ? await replaceQuote(quote.id, payload()) : await createQuote(payload());
      setDirty(false);
      onSaved(saved);
      return saved;
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : "Could not save the quote.");
      setRefusal(quantityRuleRefusal(err));
      return null;
    } finally {
      setSaving(false);
    }
  }

  /** Saved changes first, so the PDF and the till see what is on screen. */
  async function withSaved(action: (saved: Quote) => Promise<void> | void) {
    const saved = dirty || !quote ? await save() : quote;
    if (!saved) return;
    try {
      await action(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  async function remove() {
    if (!quote) return;
    setDeleteOpen(false);
    try {
      await deleteQuote(quote.id);
      router.push("/quotes");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete the quote.");
    }
  }

  async function duplicate() {
    if (!quote) return;
    try {
      const copy = await duplicateQuote(quote.id);
      router.push(`/quotes/${copy.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not duplicate the quote.");
    }
  }

  const state = quote ? quoteStateInfo(quoteState(quote)) : null;
  const title = quote ? quote.quote_number : "New quote";

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-heading-05">
            {title}{" "}
            {state && <Tag type={state.tag}>{state.label}</Tag>}
            {dirty && <Tag type="warm-gray">Unsaved changes</Tag>}
          </h1>
          <p className="cds--type-body-01">
            {quote ? `${quote.customer_name} · issued ${quote.issue_date}` : "Build the quote like a till sale."}
          </p>
        </div>
        <div className="firstout-catalogue-actions">
          {quote && editable && (
            <Button kind="danger--ghost" renderIcon={TrashCan} disabled={saving} onClick={() => setDeleteOpen(true)}>
              Delete
            </Button>
          )}
          {quote && !editable && canMutate && (
            <Button kind="tertiary" renderIcon={Copy} onClick={() => void duplicate()}>Duplicate</Button>
          )}
          {quote && (
            <Button kind="ghost" renderIcon={View} disabled={saving || (dirty && !valid)}
              onClick={() => void withSaved((saved) => previewQuotePdf(saved.id, saved.quote_number))}>
              Preview
            </Button>
          )}
          {quote && (
            <Button kind="ghost" renderIcon={Download} disabled={saving || (dirty && !valid)}
              onClick={() => void withSaved((saved) => downloadQuotePdf(saved.id, saved.quote_number))}>
              Download PDF
            </Button>
          )}
          {editable && canSell && (
            <Button kind="secondary" renderIcon={Purchase} disabled={saving || !valid}
              onClick={() => void withSaved((saved) => router.push(`/till?quote=${saved.id}`))}>
              Open in till
            </Button>
          )}
          {editable && (
            <Button disabled={saving || !valid || (!!quote && !dirty)} onClick={() => void save()}>
              {saving ? "Saving…" : "Save quote"}
            </Button>
          )}
        </div>
      </div>

      {error && (
        <InlineNotification kind="error" title="Error" subtitle={error} onCloseButtonClick={() => setError(null)} lowContrast />
      )}

      {quote && !isQuoteOpen(quote) ? (
        <Stack gap={5}>
          <InlineNotification
            kind="info"
            lowContrast
            hideCloseButton
            title={quote.status === "converted" ? "Converted to an invoice." : `This quote is ${quote.status}.`}
            subtitle="It can't be edited or deleted. Duplicate it to quote again."
          />
          {quote.converted_invoice_id && (
            <div>
              <Button kind="tertiary" href={`/invoices/${quote.converted_invoice_id}`}>
                Open {quote.converted_invoice_number ?? "invoice"}
              </Button>
            </div>
          )}
          <QuoteSummary quote={quote} />
        </Stack>
      ) : (
        <fieldset disabled={!editable} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
          <CartEditor
            mode="quote"
            title="Quote lines"
            canBreakBatches={canBreakBatches}
            quantityRefusal={refusal}
            products={products}
            cart={cart}
            addDisabled={!editable}
            onAdd={(sku, quantity) => {
              if (!editable) return false;
              setCart((current) => mergeCartBySku(current, sku, quantity));
              setDirty(true);
              return true;
            }}
            onUpdateLine={(key, patch) => {
              setCart((current) => current.map((line) => line.key === key ? { ...line, ...patch } : line));
              setDirty(true);
            }}
            onRemoveLine={(key) => {
              setCart((current) => current.filter((line) => line.key !== key));
              setDirty(true);
            }}
            skuId={skuId}
            onSkuIdChange={setSkuId}
            qty={qty}
            onQtyChange={setQty}
            customers={customers}
            customerId={customerId}
            onCustomerChange={change(setCustomerId)}
            selectedCustomer={selectedCustomer}
            preview={preview}
            pricingError={pricingError}
            onRetryPricing={() => setPricingAttempt((attempt) => attempt + 1)}
            canDiscount={canDiscount}
            colleagues={colleagues}
            colleaguesError={colleaguesError}
            salesStaffId={salesStaffId}
            onSalesStaffChange={change(setSalesStaffId)}
            notePrinted={notePrinted}
            onNotePrintedChange={change(setNotePrinted)}
            noteInternal={noteInternal}
            onNoteInternalChange={change(setNoteInternal)}
          >
            <TextInput
              id="quote-valid-until"
              labelText="Valid until"
              type="date"
              value={validUntil}
              onChange={(event) => change(setValidUntil)(event.target.value)}
              invalid={!validUntil}
              invalidText="Choose the last day this quote is valid."
              helperText="Usually 14 days from the issue date."
            />
            {editable && !valid && (
              <p className="cds--type-helper-text-01">
                Add a product{colleagues?.length ? " and choose a sales colleague" : ""} to save the quote.
              </p>
            )}
          </CartEditor>
        </fieldset>
      )}

      <Modal
        open={deleteOpen}
        danger
        modalHeading={`Delete ${quote?.quote_number ?? "quote"}?`}
        primaryButtonText="Delete"
        secondaryButtonText="Cancel"
        onRequestClose={() => setDeleteOpen(false)}
        onRequestSubmit={() => void remove()}
      >
        <p>This can&apos;t be undone. Converted quotes are never deleted.</p>
      </Modal>
    </Stack>
  );
}

/** A converted quote, read-only. */
function QuoteSummary({ quote }: { quote: Quote }) {
  return (
    <dl className="firstout-sale-summary">
      <div className="firstout-sale-summary__row">
        <dt>Customer</dt>
        <dd>{quote.customer_name}</dd>
      </div>
      {quote.lines.map((line) => (
        <div className="firstout-sale-summary__row" key={line.id}>
          <dt>{line.qty} × {line.description} ({line.our_ref})</dt>
          <dd>{Number(line.discount_percent) > 0 ? `${line.discount_percent}% off` : ""}</dd>
        </div>
      ))}
      {quote.notes && (
        <div className="firstout-sale-summary__row">
          <dt>Note on quote</dt>
          <dd>{quote.notes}</dd>
        </div>
      )}
      {quote.internal_note && (
        <div className="firstout-sale-summary__row">
          <dt>Internal note</dt>
          <dd>{quote.internal_note}</dd>
        </div>
      )}
      <div className="firstout-sale-summary__row firstout-sale-summary__row--total">
        <dt>Total incl. VAT</dt>
        <dd>{formatZarAmount(quote.total_inc_vat)}</dd>
      </div>
    </dl>
  );
}
