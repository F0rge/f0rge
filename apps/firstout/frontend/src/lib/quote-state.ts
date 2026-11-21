import type { Quote, QuoteState } from "./api";
import { localIsoDate, statementDueDate } from "./till-statement";

export const QUOTE_VALID_DAYS = 14;

export const QUOTE_STATES: readonly {
  value: QuoteState;
  label: string;
  tag: "blue" | "gray" | "green" | "purple" | "red";
}[] = [
  { value: "open", label: "Open", tag: "blue" },
  { value: "expired", label: "Expired", tag: "gray" },
  { value: "converted", label: "Converted", tag: "green" },
  { value: "accepted", label: "Accepted", tag: "purple" },
  { value: "cancelled", label: "Cancelled", tag: "red" },
];

export function quoteStateInfo(state: QuoteState) {
  return QUOTE_STATES.find((item) => item.value === state) ?? QUOTE_STATES[0];
}

/** The list's state for one quote: open quotes past their date read as expired. */
export function quoteState(
  quote: Pick<Quote, "status" | "valid_until">,
  today: string = localIsoDate(),
): QuoteState {
  if (quote.status === "draft" || quote.status === "sent" || quote.status === "expired") {
    return quote.status === "expired" || (quote.valid_until !== null && quote.valid_until < today)
      ? "expired"
      : "open";
  }
  return quote.status;
}

/** Editing, deleting and "Open in till" are for open (and expired) quotes only. */
export function isQuoteOpen(quote: Pick<Quote, "status">): boolean {
  return quote.status === "draft" || quote.status === "sent" || quote.status === "expired";
}

export function defaultValidUntil(today: string = localIsoDate()): string {
  return statementDueDate(today, QUOTE_VALID_DAYS, undefined);
}
