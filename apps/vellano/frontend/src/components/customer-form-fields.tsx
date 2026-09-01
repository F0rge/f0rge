import { NumberInput, Select, SelectItem, Stack, TextArea, TextInput, Toggle } from "@carbon/react";

import type { CreateCustomerPayload, CustomerCrm, CustomerType } from "@/lib/api";

export const emptyCustomerForm: CreateCustomerPayload = {
  name: "",
  customer_type: "retail",
  price_tier: "standard",
  email: "",
  phone: "",
  vat_number: "",
  billing_address: "",
  credit_limit: "",
  on_hold: false,
  on_hold_reason: "",
};

export function formFromCustomer(customer: CustomerCrm): CreateCustomerPayload {
  return {
    name: customer.name,
    customer_type: customer.customer_type,
    price_tier: customer.price_tier,
    email: customer.email ?? "",
    phone: customer.phone ?? "",
    vat_number: customer.vat_number ?? "",
    billing_address: customer.billing_address ?? "",
    credit_limit: customer.credit_limit ?? "",
    on_hold: customer.on_hold,
    on_hold_reason: customer.on_hold_reason ?? "",
  };
}

export function customerWritePayload(
  form: CreateCustomerPayload,
  includeCredit: boolean,
): CreateCustomerPayload {
  const payload: CreateCustomerPayload = {
    name: form.name.trim(),
    customer_type: form.customer_type ?? "retail",
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
  return payload;
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
  const creditLimitValue =
    form.credit_limit === "" || form.credit_limit == null ? "" : Number(form.credit_limit);

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
        id={`${idPrefix}-type`}
        labelText="Customer type"
        value={form.customer_type ?? "retail"}
        onChange={(event) => onChange({ customer_type: event.target.value as CustomerType })}
        disabled={disabled}
      >
        <SelectItem value="retail" text="Retail" />
        <SelectItem value="trade" text="Trade" />
      </Select>
      <TextInput
        id={`${idPrefix}-tier`}
        labelText="Price tier"
        value={form.price_tier ?? "standard"}
        onChange={(event) => onChange({ price_tier: event.target.value })}
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
