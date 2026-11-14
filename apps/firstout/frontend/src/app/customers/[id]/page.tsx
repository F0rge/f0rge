"use client";

import { Button, InlineNotification, Stack, Tag, Tile } from "@carbon/react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { CustomerPortalAccessPanel } from "@/components/customer-portal-access";
import { CustomerCrmBadges } from "@/components/customer-crm-badges";
import { SalesHistoryTable } from "@/components/records/history-tables";
import { PartyRecords } from "@/components/records/party-records";
import { PartyArchiveAction } from "@/components/party-archive-actions";
import {
  CustomerFormFields,
  RepriceDraftsModal,
  customerWritePayload,
  emptyCustomerForm,
  formFromCustomer,
} from "@/components/customer-form-fields";
import {
  canManageCustomerCredit,
  canMutateCustomers,
  formatZarAmount,
  getCustomer,
  listPriceLists,
  repriceCustomerDrafts,
  setCustomerArchived,
  updateCustomer,
  type CreateCustomerPayload,
  type CustomerCrm,
  type PriceList,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatIsoDate } from "@/lib/customer-crm";
import { isCin7GeneratedPriceList } from "@/lib/quote-sku-price";

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="cds--label">{label}</div>
      <p className="cds--type-body-01 firstout-break-text">{value || "—"}</p>
    </div>
  );
}

function priceListLabel(customer: CustomerCrm, priceLists: PriceList[]): string {
  if (!customer.price_list_id) {
    return "—";
  }
  const name =
    priceLists.find((entry) => entry.id === customer.price_list_id)?.name ??
    customer.price_list_id;
  return isCin7GeneratedPriceList(name) ? `${name} · classification sets the price` : name;
}

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateCustomers(user);
  const canEditCredit = canManageCustomerCredit(user);
  const [customer, setCustomer] = useState<CustomerCrm | null>(null);
  const [priceLists, setPriceLists] = useState<PriceList[]>([]);
  const [form, setForm] = useState<CreateCustomerPayload>(emptyCustomerForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [repriceOpen, setRepriceOpen] = useState(false);
  const [repriceBusy, setRepriceBusy] = useState(false);
  const requestId = useRef(0);

  const loadCustomer = useCallback(async () => {
    const request = ++requestId.current;
    setLoading(true);
    setCustomer(null);
    setPriceLists([]);
    setError(null);
    setSuccess(null);
    setRepriceOpen(false);
    setSaving(false);
    setRepriceBusy(false);
    try {
      const [data, lists] = await Promise.all([getCustomer(params.id), listPriceLists()]);
      if (request !== requestId.current) return;
      setCustomer(data);
      setPriceLists(lists);
      setForm(formFromCustomer(data));
    } catch (err) {
      if (request !== requestId.current) return;
      setError(err instanceof Error ? err.message : "Failed to load customer.");
    } finally {
      if (request === requestId.current) setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    if (user && params.id) {
      void loadCustomer();
    }
    return () => { requestId.current += 1; };
  }, [user, params.id, loadCustomer]);

  async function handleSave() {
    if (!customer || customer.id !== params.id || !canMutate) {
      return;
    }
    if (!form.name.trim()) {
      setError("Customer name is required.");
      return;
    }
    setSaving(true);
    const request = requestId.current;
    setError(null);
    setSuccess(null);
    try {
      const previous = customer.price_classification;
      const updated = await updateCustomer(customer.id, customerWritePayload(form, canEditCredit));
      if (request !== requestId.current) return;
      setCustomer(updated);
      setForm(formFromCustomer(updated));
      const drafts = (updated.draft_quote_count ?? 0) + (updated.draft_sales_order_count ?? 0);
      if (previous !== updated.price_classification && drafts > 0) {
        setRepriceOpen(true);
        setSuccess("Classification saved. Confirm whether to reprice drafts.");
      } else {
        setSuccess("Customer updated.");
      }
    } catch (err) {
      if (request !== requestId.current) return;
      setError(err instanceof Error ? err.message : "Failed to update customer.");
    } finally {
      if (request === requestId.current) setSaving(false);
    }
  }

  async function confirmReprice() {
    if (!customer || customer.id !== params.id) {
      return;
    }
    setRepriceBusy(true);
    const request = requestId.current;
    setError(null);
    try {
      const result = await repriceCustomerDrafts(customer.id);
      if (request !== requestId.current) return;
      setRepriceOpen(false);
      setSuccess(
        `Repriced ${result.quotes} draft quotes and ${result.sales_orders} draft sales orders. Issued invoices were left unchanged.`,
      );
    } catch (err) {
      if (request !== requestId.current) return;
      setError(err instanceof Error ? err.message : "Could not reprice drafts.");
    } finally {
      if (request === requestId.current) setRepriceBusy(false);
    }
  }

  if (loading || (customer !== null && customer.id !== params.id)) {
    return <p className="cds--type-body-01">Loading customer…</p>;
  }

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <Button kind="ghost" size="sm" onClick={() => router.push(`/customers${customer?.is_archived ? "?archived=true" : ""}`)}>
            Back to customers
          </Button>
          <h1 className="cds--type-productive-heading-04">{customer?.name ?? "Customer"}</h1>
          {customer?.is_archived ? <Tag type="gray">Archived</Tag> : null}
          {customer ? <CustomerCrmBadges customer={customer} /> : null}
        </div>
        {customer ? (
          <div className="firstout-catalogue-actions">
            {canMutate ? <PartyArchiveAction
              key={customer.id}
              kind="customer"
              name={customer.name}
              archived={customer.is_archived}
              disabled={loading || saving || repriceBusy}
              onConfirm={async () => {
                const request = requestId.current;
                const updated = await setCustomerArchived(customer.id, !customer.is_archived);
                if (request !== requestId.current) return;
                setCustomer(updated);setForm(formFromCustomer(updated));
                setRepriceOpen(false);
                setSuccess(updated.is_archived ? "Customer archived. Account details and history are preserved." : "Customer restored to the active list.");
              }}
            /> : null}
            <Button
              kind="tertiary"
              onClick={() => router.push(`/invoices?customer=${customer.id}`)}
            >
              View invoices
            </Button>
            <Button kind="tertiary" onClick={() => router.push(`/laybys?customer=${customer.id}`)}>
              View laybys
            </Button>
          </div>
        ) : null}
      </div>

      {error ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}

      {success ? (
        <InlineNotification
          kind="success"
          title="Saved"
          subtitle={success}
          onCloseButtonClick={() => setSuccess(null)}
          lowContrast
        />
      ) : null}

      {customer?.is_archived ? <InlineNotification kind="info" title="This customer is archived" subtitle="Contacts, terms and available history are preserved. Restore the account before using it in new transactions." hideCloseButton lowContrast /> : null}

      {loading ? (
        <p className="cds--type-body-01">Loading customer…</p>
      ) : customer ? (
        <>
          <Tile>
            <Stack gap={5}>
              <h2 className="cds--type-productive-heading-03">Account</h2>
              <div className="firstout-detail-grid">
                <DetailRow
                  label="Classification"
                  value={
                    customer.price_classification === "Retail"
                      ? "Retail · incl. VAT"
                      : `${customer.price_classification} · excl. VAT`
                  }
                />
                <DetailRow label="Open invoices" value={formatZarAmount(customer.open_invoices_zar)} />
                <DetailRow
                  label="Overdue"
                  value={
                    customer.overdue_invoices_count > 0
                      ? `${customer.overdue_invoices_count} · ${formatZarAmount(customer.overdue_invoices_zar)}`
                      : "—"
                  }
                />
                <DetailRow
                  label="Active laybys"
                  value={
                    customer.active_laybys_count > 0
                      ? formatZarAmount(customer.active_laybys_zar)
                      : "—"
                  }
                />
                <DetailRow label="Last purchase" value={formatIsoDate(customer.last_purchase_date)} />
                <DetailRow label="Price list" value={priceListLabel(customer, priceLists)} />
                <DetailRow label="Phone" value={customer.phone ?? "—"} />
                <DetailRow label="Email" value={customer.email ?? "—"} />
                <DetailRow label="VAT number" value={customer.vat_number ?? "—"} />
                <DetailRow label="Billing address" value={customer.billing_address ?? "—"} />
                {canEditCredit ? (
                  <DetailRow
                    label="Credit limit"
                    value={customer.credit_limit ? formatZarAmount(customer.credit_limit) : "—"}
                  />
                ) : null}
              </div>
            </Stack>
          </Tile>

          {canMutate && !customer.is_archived && customer.customer_type === "trade" ? (
            <CustomerPortalAccessPanel key={customer.id} customerId={customer.id} defaultEmail={customer.email ?? ""} />
          ) : null}

          {canMutate && !customer.is_archived ? (
            <Tile>
              <Stack gap={5}>
                <h2 className="cds--type-productive-heading-03">Edit profile</h2>
                <CustomerFormFields
                  idPrefix="detail-customer"
                  form={form}
                  onChange={(patch) => setForm((current) => ({ ...current, ...patch }))}
                  showCreditFields={canEditCredit}
                />
                <Button
                  kind="primary"
                  disabled={saving || !form.name.trim()}
                  onClick={() => void handleSave()}
                >
                  Save
                </Button>
              </Stack>
            </Tile>
          ) : null}
          <PartyRecords kind="customers" id={customer.id} />
          <SalesHistoryTable customerId={customer.id} />
        </>
      ) : (
        <InlineNotification
          kind="error"
          title="Not found"
          subtitle="This customer could not be loaded."
          hideCloseButton
          lowContrast
        />
      )}
      <RepriceDraftsModal
        open={repriceOpen}
        quotes={customer?.draft_quote_count ?? 0}
        orders={customer?.draft_sales_order_count ?? 0}
        busy={repriceBusy}
        onConfirm={() => void confirmReprice()}
        onCancel={() => {
          setRepriceOpen(false);
          setSuccess("Classification saved. Draft quotes and orders kept their prices.");
        }}
      />
    </Stack>
  );
}
