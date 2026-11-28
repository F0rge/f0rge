export const REPORT_SECTIONS = ["sales", "stock", "books"] as const;
export type ReportSection = (typeof REPORT_SECTIONS)[number];

/** The thirteen report tabs, in today's order, each in one sidebar section, with the date control it reads (none for stock). */
export const REPORT_TABS = [
  { id: "aged-ar", label: "Aged AR", section: "books", dates: "as_of" },
  { id: "aged-ap", label: "Aged AP", section: "books", dates: "as_of" },
  { id: "profit-loss", label: "Profit & loss", section: "books", dates: "range" },
  { id: "balance-sheet", label: "Balance sheet", section: "books", dates: "as_of" },
  { id: "trial-balance", label: "Trial balance", section: "books", dates: "as_of" },
  { id: "journals", label: "Journals", section: "books", dates: "range" },
  { id: "cash-summary", label: "Cash summary", section: "books", dates: "range" },
  { id: "stock-valuation", label: "Stock valuation", section: "stock", dates: null },
  { id: "aged-stock", label: "Aged stock", section: "stock", dates: null },
  { id: "sales-by-sku", label: "Sales by SKU", section: "sales", dates: "range" },
  { id: "lead-times", label: "Lead times", section: "stock", dates: null },
  { id: "criticality", label: "Criticality", section: "sales", dates: "range" },
  { id: "sales-vat", label: "Sales VAT", section: "sales", dates: "range" },
] as const satisfies readonly { id: string; label: string; section: ReportSection; dates: "as_of" | "range" | null }[];

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
  const using = (dates: "as_of" | "range") => tabs.filter((tab) => tab.dates === dates).map((tab) => tab.label);
  const list = (labels: string[]) => (labels.length ? ` (${labels.join(", ")})` : "");
  return {
    section,
    sectionLabel: copy?.label ?? null,
    tabs,
    selected,
    title: copy?.title ?? "Reports",
    /** Date controls for the reports on screen only, labelled with those reports; null hides the control. */
    asOfLabel: using("as_of").length ? `As of${list(using("as_of"))}` : null,
    rangeLabels: using("range").length ? { from: `From${list(using("range"))}`, to: `To${list(using("range"))}` } : null,
    /** Which tabs to fetch: only the visible section's (all thirteen without a section). */
    shows: (id: ReportTabId) => tabs.some((tab) => tab.id === id),
    description: copy?.description
      ?? "Financial and stock reports in ZAR: aged AR and AP, P&L, balance sheet, trial balance, journals, cash summary, stock valuation, aged stock, sales, lead times and criticality.",
  };
}
