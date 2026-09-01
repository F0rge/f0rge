"use client";

import { Button, InlineNotification, Stack, Tile } from "@carbon/react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { CustomerCrmBadges } from "@/components/customer-crm-badges";
import {
  CustomerFormFields,
  customerWritePayload,
  emptyCustomerForm,
  formFromCustomer,
} from "@/components/customer-form-fields";
import {
  canManageCustomerCredit,
  canMutateCustomers,
  formatZarAmount,
  getCustomer,
  updateCustomer,
  type CreateCustomerPayload,
  type CustomerCrm,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatIsoDate } from "@/lib/customer-crm";

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="cds--label">{label}</div>
      <p className="cds--type-body-01">{value || "—"}</p>
    </div>
  );
}

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateCustomers(user);
  const canEditCredit = canManageCustomerCredit(user);
  const [customer, setCustomer] = useState<CustomerCrm | null>(null);
  const [form, setForm] = useState<CreateCustomerPayload>(emptyCustomerForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadCustomer = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCustomer(params.id);
      setCustomer(data);
      setForm(formFromCustomer(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customer.");
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    if (user && params.id) {
      void loadCustomer();
    }
  }, [user, params.id, loadCustomer]);

  async function handleSave() {
    if (!customer || !canMutate) {
      return;
    }
    if (!form.name.trim()) {
      setError("Customer name is required.");
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await updateCustomer(customer.id, customerWritePayload(form, canEditCredit));
      setCustomer(updated);
      setForm(formFromCustomer(updated));
      setSuccess("Customer updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update customer.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <div className="vellano-page-header">
        <div>
          <Button kind="ghost" size="sm" onClick={() => router.push("/customers")}>
            Back to customers
          </Button>
          <h1 className="cds--type-productive-heading-04">{customer?.name ?? "Customer"}</h1>
          {customer ? <CustomerCrmBadges customer={customer} /> : null}
        </div>
        {customer ? (
          <div className="vellano-catalogue-actions">
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

      {loading ? (
        <p className="cds--type-body-01">Loading customer…</p>
      ) : customer ? (
        <>
          <Tile>
            <Stack gap={5}>
              <h2 className="cds--type-productive-heading-03">Account</h2>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(12rem, 1fr))",
                  gap: "1rem",
                }}
              >
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

          {canMutate ? (
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
    </Stack>
  );
}
