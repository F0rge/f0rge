"use client";

import { InlineNotification, Modal, Stack, TextInput } from "@carbon/react";
import { useState } from "react";

import { PaymentMethodFields } from "@/components/payment-method-fields";
import { createPayment, type BillListItem, type Payment, type PaymentMethod } from "@/lib/api";
import { partialPaymentError } from "@/lib/payment-status";
import { localIsoDate } from "@/lib/till-statement";

/** Record a payment out against one approved bill, from the bills list or a bill page. */
export function BillPaymentModal({
  bill,
  onClose,
  onRecorded,
}: {
  bill: BillListItem;
  onClose: () => void;
  onRecorded: (payment: Payment) => void;
}) {
  const foreign = bill.currency !== "ZAR";
  const [amount, setAmount] = useState(bill.balance_foreign);
  const [fx, setFx] = useState(bill.fx_to_zar);
  const [paidOn, setPaidOn] = useState(localIsoDate());
  const [method, setMethod] = useState<PaymentMethod>("eft");
  const [reference, setReference] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const invalid = partialPaymentError({
      amount,
      balance: bill.balance_foreign,
      documentNumber: bill.bill_number,
      currency: bill.currency,
    });
    if (invalid) {
      setError(invalid);
      return;
    }
    if (foreign && !(Number(fx) > 0)) {
      setError("Enter the rate your bank used.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      onRecorded(
        await createPayment({
          direction: "out",
          bill_id: bill.id,
          amount: amount.trim(),
          currency: bill.currency,
          fx_to_zar: foreign ? fx.trim() : undefined,
          paid_on: paidOn,
          tender: method,
          reference: reference.trim() || undefined,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record payment.");
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      modalLabel={bill.bill_number}
      modalHeading="Record payment"
      primaryButtonText={saving ? "Recording…" : "Record payment"}
      secondaryButtonText="Cancel"
      primaryButtonDisabled={saving || !amount.trim() || !paidOn}
      onRequestClose={() => {
        if (!saving) onClose();
      }}
      onRequestSubmit={() => void submit()}
    >
      <Stack gap={5}>
        {error ? (
          <InlineNotification kind="error" title="Could not record" subtitle={error} hideCloseButton lowContrast />
        ) : null}
        <TextInput
          id="bill-payment-amount"
          labelText={`Amount (${bill.currency})`}
          helperText={`Any amount up to the ${bill.currency} ${bill.balance_foreign} still owing. A smaller amount leaves the bill partially paid.`}
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
        {foreign ? (
          <TextInput
            id="bill-payment-fx"
            labelText={`FX rate, ${bill.currency} to ZAR`}
            helperText="The rate your bank used; it may differ from the bill's rate."
            value={fx}
            onChange={(event) => setFx(event.target.value)}
          />
        ) : null}
        <TextInput
          id="bill-payment-date"
          labelText="Paid on"
          type="date"
          value={paidOn}
          onChange={(event) => setPaidOn(event.target.value)}
        />
        <PaymentMethodFields
          idPrefix="bill-payment"
          method={method}
          reference={reference}
          onMethodChange={setMethod}
          onReferenceChange={setReference}
        />
      </Stack>
    </Modal>
  );
}
