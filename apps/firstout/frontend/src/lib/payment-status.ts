import type { BillStatus, InvoiceStatus } from "./api";

export type SettlementStatus = "unpaid" | "partially_paid" | "paid" | "unknown";

export function settlementStatusLabel(status: SettlementStatus): string {
  switch (status) {
    case "unpaid":
      return "Unpaid";
    case "partially_paid":
      return "Partially paid";
    case "paid":
      return "Paid";
    case "unknown":
      return "Not imported";
  }
}

export function settlementTagType(status: SettlementStatus): "gray" | "blue" | "green" {
  switch (status) {
    case "unpaid":
      return "gray";
    case "partially_paid":
      return "blue";
    case "paid":
      return "green";
    case "unknown":
      return "gray";
  }
}

/** Invoice status tag: an unpaid invoice issued on account reads "On statement"; past due, "Overdue". */
export function invoiceStatusTag(invoice: {
  payment_status: SettlementStatus;
  on_account: boolean;
  is_archive: boolean;
  status?: InvoiceStatus;
}): { label: string; type: "gray" | "blue" | "green" | "purple" | "red" } {
  if (invoice.status === "overdue") {
    return { label: "Overdue", type: "red" };
  }
  const status = invoice.is_archive ? "unknown" : invoice.payment_status;
  if (status === "unpaid" && invoice.on_account) {
    return { label: "On statement", type: "purple" };
  }
  return { label: settlementStatusLabel(status), type: settlementTagType(status) };
}

function moneyToCents(value: string): number | null {
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(value.trim());
  if (!match) {
    return null;
  }
  const whole = Number(match[1]);
  const frac = (match[2] ?? "").padEnd(2, "0");
  return whole * 100 + Number(frac);
}

function formatCents(cents: number, currency: string): string {
  const negative = cents < 0;
  const abs = Math.abs(cents);
  const whole = Math.floor(abs / 100).toLocaleString("en-US");
  const frac = String(abs % 100).padStart(2, "0");
  const shown = `${negative ? "-" : ""}${whole}.${frac}`;
  if (currency.toUpperCase() === "ZAR") {
    return `R ${shown}`;
  }
  return `${currency.toUpperCase()} ${shown}`;
}

export function partialPaymentError(input: {
  amount: string;
  balance: string;
  documentNumber: string;
  currency?: string;
}): string | null {
  const currency = input.currency ?? "ZAR";
  const trimmed = input.amount.trim();
  if (!trimmed) {
    return "Enter a payment amount.";
  }
  if (trimmed.startsWith("-")) {
    return "Payment amount must be more than zero.";
  }
  const amount = moneyToCents(trimmed);
  if (amount === null) {
    return "Payment amount must be in cents.";
  }
  if (amount <= 0) {
    return "Payment amount must be more than zero.";
  }
  const balance = moneyToCents(input.balance);
  if (balance === null) {
    return "Payment amount must be in cents.";
  }
  if (amount > balance) {
    return `Payment is more than the ${formatCents(balance, currency)} still owing on ${input.documentNumber}.`;
  }
  return null;
}

export const BILL_STATUS: Record<
  BillStatus,
  { label: string; tag: "gray" | "purple" | "blue" | "teal" | "red" | "green" }
> = {
  draft: { label: "Draft", tag: "gray" },
  awaiting_approval: { label: "Awaiting approval", tag: "purple" },
  unpaid: { label: "Unpaid", tag: "blue" },
  partially_paid: { label: "Partially paid", tag: "teal" },
  overdue: { label: "Overdue", tag: "red" },
  paid: { label: "Paid", tag: "green" },
  unknown: { label: "Not imported", tag: "gray" },
};
