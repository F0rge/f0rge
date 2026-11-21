/** The one layout tax invoices, quotes, credit notes and receipts print with. */

export type DocumentKind = "invoice" | "quote" | "credit_note" | "receipt";
export type DocumentSectionKey = "parties" | "lines" | "totals" | "notes" | "payments" | "bank" | "terms";

export type DocumentWording = { title: string; number_label: string; terms: string };

export type DocumentTemplate = {
  logo_position: "left" | "centre" | "right";
  logo_height: number;
  accent_colour: string;
  font: "sans" | "serif" | "mono";
  density: "comfortable" | "compact";
  table_header: "band" | "lines" | "solid";
  sections: { key: DocumentSectionKey; visible: boolean }[];
  columns: { sku_ref: boolean; discount: boolean; line_vat: boolean };
  wording: Record<DocumentKind, DocumentWording>;
  footer: string;
  show_trading_name: boolean;
  paid_stamp: boolean;
};

export type DocumentTemplateResponse = {
  template: DocumentTemplate;
  defaults: DocumentTemplate;
  is_default: boolean;
};

export const DOCUMENT_KINDS: { value: DocumentKind; label: string }[] = [
  { value: "invoice", label: "Tax invoice" },
  { value: "quote", label: "Quote" },
  { value: "credit_note", label: "Credit note" },
  { value: "receipt", label: "Payment receipt" },
];

export const SECTION_LABELS: Record<DocumentSectionKey, string> = {
  parties: "Seller and buyer",
  lines: "Line items",
  totals: "Totals",
  notes: "Printed note",
  payments: "Payments and balance",
  bank: "Banking details",
  terms: "Terms",
};

export const HEX_COLOUR = /^#[0-9a-f]{6}$/i;

/** Why the draft cannot be saved or previewed, or null when it can. */
export function templateProblem(template: DocumentTemplate): string | null {
  if (!HEX_COLOUR.test(template.accent_colour)) return "Enter a colour like #0f62fe.";
  for (const { value, label } of DOCUMENT_KINDS) {
    const wording = template.wording[value];
    if (!wording.title.trim() || !wording.number_label.trim()) {
      return `${label} needs a title and a number label.`;
    }
  }
  return null;
}

export function moveSection(template: DocumentTemplate, index: number, step: -1 | 1): DocumentTemplate {
  const sections = [...template.sections];
  const target = index + step;
  if (target < 0 || target >= sections.length) return template;
  [sections[index], sections[target]] = [sections[target], sections[index]];
  return { ...template, sections };
}
