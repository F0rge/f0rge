"use client";

import { Button, InlineNotification, PasswordInput, Stack, TextInput, Tile } from "@carbon/react";
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
  createPortalUser,
  formatZarAmount,
  getCustomer,
  listPriceLists,
  updateCustomer,
  type CreateCustomerPayload,
  type CustomerCrm,
  type PriceList,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatIsoDate } from "@/lib/customer-crm";

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="cds--label">{label}</div>
      <p className="cds--type-body-01 firstout-break-text">{value || "—"}</p>
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
  const [priceLists, setPriceLists] = useState<PriceList[]>([]);
  const [form, setForm] = useState<CreateCustomerPayload>(emptyCustomerForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [portalEmail, setPortalEmail] = useState("");
  const [portalPassword, setPortalPassword] = useState("");
  const [portalSaving, setPortalSaving] = useState(false);

  const loadCustomer = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, lists] = await Promise.all([getCustomer(params.id), listPriceLists()]);
      setCustomer(data);
      setPriceLists(lists);
      setForm(formFromCustomer(data));
      setPortalEmail(data.email ?? "");
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

  async function handleCreatePortalUser() {
    if (!customer || !canMutate) {
      return;
    }
    if (!portalEmail.trim() || portalPassword.length < 8) {
      setError("Portal email and a password of at least 8 characters are required.");
      return;
    }
    setPortalSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const created = await createPortalUser(customer.id, {
        email: portalEmail.trim(),
        password: portalPassword,
      });
      setPortalPassword("");
      setSuccess(`Trade portal login created for ${created.email}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create portal login.");
    } finally {
      setPortalSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <Button kind="ghost" size="sm" onClick={() => router.push("/customers")}>
            Back to customers
          </Button>
          <h1 className="cds--type-productive-heading-04">{customer?.name ?? "Customer"}</h1>
          {customer ? <CustomerCrmBadges customer={customer} /> : null}
        </div>
        {customer ? (
          <div className="firstout-catalogue-actions">
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
              <div className="firstout-detail-grid">
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
                <DetailRow
                  label="Price list"
                  value={
                    customer.price_list_id
                      ? (priceLists.find((entry) => entry.id === customer.price_list_id)?.name ??
                        customer.price_list_id)
                      : "—"
                  }
                />
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

          {canMutate && customer.customer_type === "trade" ? (
            <Tile>
              <Stack gap={5}>
                <h2 className="cds--type-productive-heading-03">Trade portal</h2>
                <p className="cds--type-body-01">
                  Creates a login for /trade. Staff still confirm draft orders before stock is held.
                </p>
                <TextInput
                  id="portal-email"
                  labelText="Portal email"
                  value={portalEmail}
                  onChange={(event) => setPortalEmail(event.target.value)}
                />
                <PasswordInput
                  id="portal-password"
                  labelText="Temporary password"
                  value={portalPassword}
                  onChange={(event) => setPortalPassword(event.target.value)}
                />
                <Button
                  kind="secondary"
                  disabled={portalSaving || !portalEmail.trim() || portalPassword.length < 8}
                  onClick={() => void handleCreatePortalUser()}
                >
                  {portalSaving ? "Creating…" : "Create portal login"}
                </Button>
              </Stack>
            </Tile>
          ) : null}

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
