import { Modal, NumberInput, Select, SelectItem, Stack, TextArea, TextInput, Toggle } from "@carbon/react";
import { useEffect, useState } from "react";

import {
  PRICE_CLASSIFICATIONS,
  listPriceLists,
  type CreateCustomerPayload,
  type CustomerCrm,
  type PriceClassification,
  type PriceList,
} from "@/lib/api";

export const emptyCustomerForm: CreateCustomerPayload = {
  name: "",
  customer_type: "retail",
  price_classification: "Retail",
  price_tier: "standard",
  email: "",
  phone: "",
  vat_number: "",
  billing_address: "",
  credit_limit: "",
  on_hold: false,
  on_hold_reason: "",
  payment_terms_days: undefined,
  price_list_id: "",
  payment_reminders_opt_out: false,
};

export function formFromCustomer(customer: CustomerCrm): CreateCustomerPayload {
  return {
    name: customer.name,
    customer_type: customer.customer_type,
    price_classification: customer.price_classification ?? "Retail",
    price_tier: customer.price_tier,
    email: customer.email ?? "",
    phone: customer.phone ?? "",
    vat_number: customer.vat_number ?? "",
    billing_address: customer.billing_address ?? "",
    credit_limit: customer.credit_limit ?? "",
    on_hold: customer.on_hold,
    on_hold_reason: customer.on_hold_reason ?? "",
    payment_terms_days: customer.payment_terms_days ?? undefined,
    price_list_id: customer.price_list_id ?? "",
    payment_reminders_opt_out: customer.payment_reminders_opt_out ?? false,
  };
}

export function customerWritePayload(
  form: CreateCustomerPayload,
  includeCredit: boolean,
): CreateCustomerPayload {
  const classification = form.price_classification ?? "Retail";
  const payload: CreateCustomerPayload = {
    name: form.name.trim(),
    customer_type: classification === "Retail" ? "retail" : "trade",
    price_classification: classification,
    price_tier: form.price_tier?.trim() || "standard",
    email: form.email,
    phone: form.phone,
    vat_number: form.vat_number,
    billing_address: form.billing_address,
  };
  if (includeCredit) {
    const limit = form.credit_limit?.trim();
    if (limit) {
      payload.credit_limit = limit;
    }
    payload.on_hold = form.on_hold ?? false;
    payload.on_hold_reason = form.on_hold_reason;
  }
  if (form.payment_terms_days != null && form.payment_terms_days !== undefined) {
    payload.payment_terms_days = form.payment_terms_days;
  } else {
    payload.payment_terms_days = null;
  }
  const listId = form.price_list_id?.trim?.() ?? form.price_list_id;
  payload.price_list_id = listId ? listId : null;
  payload.payment_reminders_opt_out = form.payment_reminders_opt_out ?? false;
  return payload;
}

export function RepriceDraftsModal({
  open,
  quotes,
  orders,
  busy,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  quotes: number;
  orders: number;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const quoteLabel = quotes === 1 ? "1 draft quote" : `${quotes} draft quotes`;
  const orderLabel = orders === 1 ? "1 draft sales order" : `${orders} draft sales orders`;
  return (
    <Modal
      open={open}
      modalHeading="Reprice draft documents?"
      primaryButtonText={busy ? "Repricing…" : "Reprice drafts"}
      secondaryButtonText="Keep current prices"
      primaryButtonDisabled={busy}
      onRequestSubmit={onConfirm}
      onRequestClose={onCancel}
    >
      <p>
        This customer has {quoteLabel} and {orderLabel}. Reprice them to the new classification?
        Issued invoices will not change.
      </p>
    </Modal>
  );
}

export function CustomerFormFields({
  idPrefix,
  form,
  onChange,
  disabled,
  showCreditFields,
}: {
  idPrefix: string;
  form: CreateCustomerPayload;
  onChange: (patch: Partial<CreateCustomerPayload>) => void;
  disabled?: boolean;
  showCreditFields?: boolean;
}) {
  const [priceLists, setPriceLists] = useState<PriceList[]>([]);

  useEffect(() => {
    let cancelled = false;
    void listPriceLists()
      .then((lists) => {
        if (!cancelled) {
          setPriceLists(lists);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPriceLists([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const creditLimitValue =
    form.credit_limit === "" || form.credit_limit == null ? "" : Number(form.credit_limit);
  const paymentTermsValue =
    form.payment_terms_days == null ? "" : Number(form.payment_terms_days);

  return (
    <Stack gap={5}>
      <TextInput
        id={`${idPrefix}-name`}
        labelText="Name"
        value={form.name}
        onChange={(event) => onChange({ name: event.target.value })}
        required
        disabled={disabled}
      />
      <Select
        id={`${idPrefix}-classification`}
        labelText="Price classification"
        helperText="Retail prices are shown including VAT. Stockist, Wholesale, and Decorator prices are excluding VAT. A price list overrides the classification."
        value={form.price_classification ?? "Retail"}
        onChange={(event) =>
          onChange({ price_classification: event.target.value as PriceClassification })
        }
        disabled={disabled}
      >
        {PRICE_CLASSIFICATIONS.map((classification) => (
          <SelectItem
            key={classification}
            value={classification}
            text={
              classification === "Retail"
                ? "Retail (incl. VAT)"
                : `${classification} (excl. VAT)`
            }
          />
        ))}
      </Select>
      <Select
        id={`${idPrefix}-price-list`}
        labelText="Price list"
        helperText="When a list has this SKU, that price is used instead of the classification."
        value={form.price_list_id ?? ""}
        onChange={(event) => onChange({ price_list_id: event.target.value })}
        disabled={disabled}
      >
        <SelectItem value="" text="None" />
        {priceLists.map((entry) => (
          <SelectItem key={entry.id} value={entry.id} text={entry.name} />
        ))}
      </Select>
      <NumberInput
        id={`${idPrefix}-payment-terms`}
        label="Payment terms (days)"
        helperText="Leave empty to use the company default."
        min={0}
        max={365}
        step={1}
        allowEmpty
        value={Number.isFinite(paymentTermsValue) ? paymentTermsValue : ""}
        onChange={(_, { value }) =>
          onChange({
            payment_terms_days: value === "" ? undefined : Number(value),
          })
        }
        disabled={disabled}
      />
      <Toggle
        id={`${idPrefix}-reminders`}
        labelText="Payment reminders"
        labelA="Opted out"
        labelB="On"
        toggled={!form.payment_reminders_opt_out}
        onToggle={(checked) => onChange({ payment_reminders_opt_out: !checked })}
        disabled={disabled}
      />
      <TextInput
        id={`${idPrefix}-email`}
        labelText="Email"
        type="email"
        value={form.email ?? ""}
        onChange={(event) => onChange({ email: event.target.value })}
        disabled={disabled}
      />
      <TextInput
        id={`${idPrefix}-phone`}
        labelText="Phone"
        value={form.phone ?? ""}
        onChange={(event) => onChange({ phone: event.target.value })}
        disabled={disabled}
      />
      <TextInput
        id={`${idPrefix}-vat`}
        labelText="VAT number"
        value={form.vat_number ?? ""}
        onChange={(event) => onChange({ vat_number: event.target.value })}
        disabled={disabled}
      />
      <TextArea
        id={`${idPrefix}-billing`}
        labelText="Billing address"
        value={form.billing_address ?? ""}
        onChange={(event) => onChange({ billing_address: event.target.value })}
        disabled={disabled}
      />
      {showCreditFields ? (
        <>
          <NumberInput
            id={`${idPrefix}-credit-limit`}
            label="Credit limit (ZAR)"
            min={0}
            step={1}
            allowEmpty
            value={Number.isFinite(creditLimitValue) ? creditLimitValue : ""}
            onChange={(_, { value }) =>
              onChange({ credit_limit: value === "" ? "" : String(value) })
            }
            disabled={disabled}
          />
          <Toggle
            id={`${idPrefix}-on-hold`}
            labelText="On hold"
            labelA="Off"
            labelB="On"
            toggled={form.on_hold ?? false}
            onToggle={(checked) => onChange({ on_hold: checked })}
            disabled={disabled}
          />
          <TextInput
            id={`${idPrefix}-on-hold-reason`}
            labelText="On hold reason"
            value={form.on_hold_reason ?? ""}
            onChange={(event) => onChange({ on_hold_reason: event.target.value })}
            disabled={disabled}
          />
        </>
      ) : null}
    </Stack>
  );
}
