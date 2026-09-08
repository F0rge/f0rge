import { formatZarAmount, type CustomerCrm } from "@/lib/api";

export const CUSTOMER_ON_HOLD_MESSAGE = "Customer is on hold";
export const CUSTOMER_CREDIT_LIMIT_MESSAGE = "Customer exceeds credit limit";

export function isCreditBlockMessage(message: string): boolean {
  return message === CUSTOMER_ON_HOLD_MESSAGE || message === CUSTOMER_CREDIT_LIMIT_MESSAGE;
}

export function formatIsoDate(iso: string | null | undefined): string {
  if (!iso) {
    return "—";
  }
  return new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("en-ZA");
}

export function overdueBadgeLabel(customer: CustomerCrm): string {
  return `${customer.overdue_invoices_count} · ${formatZarAmount(customer.overdue_invoices_zar)}`;
}

export function laybyActiveBadgeLabel(customer: CustomerCrm): string {
  return `${customer.active_laybys_count} · ${formatZarAmount(customer.active_laybys_zar)}`;
}

export function matchesCustomerQuery(
  customerId: string,
  customerName: string,
  query: string,
): boolean {
  const trimmed = query.trim();
  if (!trimmed) {
    return true;
  }
  return customerId === trimmed || customerName.toLowerCase() === trimmed.toLowerCase();
}
