export const REPORT_SECTIONS = ["sales", "stock", "books"] as const;
export type ReportSection = (typeof REPORT_SECTIONS)[number];

/** The thirteen report tabs, in today's order, each in one sidebar section. */
export const REPORT_TABS = [
  { id: "aged-ar", label: "Aged AR", section: "books" },
  { id: "aged-ap", label: "Aged AP", section: "books" },
  { id: "profit-loss", label: "Profit & loss", section: "books" },
  { id: "balance-sheet", label: "Balance sheet", section: "books" },
  { id: "trial-balance", label: "Trial balance", section: "books" },
  { id: "journals", label: "Journals", section: "books" },
  { id: "cash-summary", label: "Cash summary", section: "books" },
  { id: "stock-valuation", label: "Stock valuation", section: "stock" },
  { id: "aged-stock", label: "Aged stock", section: "stock" },
  { id: "sales-by-sku", label: "Sales by SKU", section: "sales" },
  { id: "lead-times", label: "Lead times", section: "stock" },
  { id: "criticality", label: "Criticality", section: "sales" },
  { id: "sales-vat", label: "Sales VAT", section: "sales" },
] as const satisfies readonly { id: string; label: string; section: ReportSection }[];

export type ReportTabId = (typeof REPORT_TABS)[number]["id"];

const SECTION_COPY: Record<ReportSection, { label: string; title: string; description: string }> = {
  sales: { label: "Sales", title: "Sales reports", description: "What sold, which SKUs carry most of the revenue, and the sales VAT for a period." },
  stock: { label: "Stock", title: "Stock reports", description: "What the stock is worth, how long it has sat, and how long suppliers take to deliver." },
  books: { label: "Books", title: "Books reports", description: "Aged receivables and payables, profit and loss, balance sheet, trial balance, journals and cash summary." },
};

export function reportSection(value: string | null | undefined): ReportSection | null {
  return REPORT_SECTIONS.find((section) => section === value) ?? null;
}

/** `?section=` picks one section's tabs; none (or an unknown value) shows all thirteen, so old links keep working. */
export function reportsView(sectionParam: string | null | undefined, tabParam?: string | null) {
  const section = reportSection(sectionParam);
  const tabs = REPORT_TABS.filter((tab) => !section || tab.section === section);
  const selected = Math.max(0, tabs.findIndex((tab) => tab.id === tabParam));
  const copy = section ? SECTION_COPY[section] : null;
  return {
    section,
    sectionLabel: copy?.label ?? null,
    tabs,
    selected,
    title: copy?.title ?? "Reports",
    description: copy?.description
      ?? "Financial and stock reports in ZAR: aged AR and AP, P&L, balance sheet, trial balance, journals, cash summary, stock valuation, aged stock, sales, lead times and criticality.",
  };
}
