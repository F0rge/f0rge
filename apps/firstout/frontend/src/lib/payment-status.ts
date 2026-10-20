export type SettlementStatus = "unpaid" | "partially_paid" | "paid";

export function settlementStatusLabel(status: SettlementStatus): string {
  switch (status) {
    case "unpaid":
      return "Unpaid";
    case "partially_paid":
      return "Partially paid";
    case "paid":
      return "Paid";
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
  }
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
