export function niaInvoiceHref(invoiceId: string): string {
  return `/invoices/${encodeURIComponent(invoiceId)}`;
}
