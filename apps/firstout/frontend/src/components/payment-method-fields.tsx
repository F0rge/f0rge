"use client";

import { Select, SelectItem, TextInput } from "@carbon/react";

import type { Payment, PaymentMethod } from "@/lib/api";

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod | "deposit", string> = {
  eft: "EFT",
  card: "Card",
  cash: "Cash",
  other: "Other",
  deposit: "Deposit",
};

const METHODS: readonly PaymentMethod[] = ["eft", "card", "cash", "other"];

export function paymentMethodLabel(tender: Payment["tender"]): string {
  return tender ? PAYMENT_METHOD_LABELS[tender] : "—";
}

/** Method and bank reference, shared by every Record payment modal. */
export function PaymentMethodFields({
  idPrefix,
  method,
  reference,
  onMethodChange,
  onReferenceChange,
}: {
  idPrefix: string;
  method: PaymentMethod;
  reference: string;
  onMethodChange: (method: PaymentMethod) => void;
  onReferenceChange: (reference: string) => void;
}) {
  return (
    <>
      <Select
        id={`${idPrefix}-method`}
        labelText="Method"
        value={method}
        onChange={(event) => onMethodChange(event.target.value as PaymentMethod)}
      >
        {METHODS.map((value) => (
          <SelectItem key={value} value={value} text={PAYMENT_METHOD_LABELS[value]} />
        ))}
      </Select>
      <TextInput
        id={`${idPrefix}-reference`}
        labelText="Reference (optional)"
        helperText="As it appears on the bank statement."
        maxLength={200}
        value={reference}
        onChange={(event) => onReferenceChange(event.target.value)}
      />
    </>
  );
}
