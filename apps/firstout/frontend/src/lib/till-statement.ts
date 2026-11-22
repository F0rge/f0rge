import { localIsoDate } from "./dates";

/** Default due date for a statement sale: issue date + customer terms, else team terms. */
export function statementDueDate(
  issueDate: string,
  customerTermsDays: number | null | undefined,
  teamTermsDays: number | undefined,
): string {
  const days = customerTermsDays ?? teamTermsDays ?? 30;
  const [year, month, day] = issueDate.split("-").map(Number);
  return localIsoDate(new Date(year, month - 1, day + days));
}
