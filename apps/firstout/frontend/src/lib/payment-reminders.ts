export function reminderOffsetLabel(offsetDays: number): string {
  if (offsetDays === 0) {
    return "On the due date";
  }
  const days = Math.abs(offsetDays);
  const unit = days === 1 ? "day" : "days";
  if (offsetDays < 0) {
    return `${days} ${unit} before the due date`;
  }
  return `${days} ${unit} overdue`;
}

export const REMINDER_PLACEHOLDER_HELP =
  "Placeholders: {customer_name} {invoice_number} {amount_owing} {due_date} {days_overdue} {invoice_pdf}";
