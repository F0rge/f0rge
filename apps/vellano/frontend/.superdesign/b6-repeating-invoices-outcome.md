# B6 repeating invoices — Superdesign outcome

- **Canvas used:** no.
- **Credits:** `insufficient_credits` this session (billing gate). Did not call the Superdesign CLI.
- **Implementation:** IBM Carbon `/repeating-invoices` cloned from invoices list. DataTable of schedules, Create modal (customer, day of month 1–28, next date, invoice-style lines), Run now → `POST /repeating-invoices/{id}/run` (creates `INV-`, no email). Mutate via `canMutateBooks`. No `@f0rge/ui`.
