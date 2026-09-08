# B4 VAT201 periods — Superdesign outcome

- **Canvas used:** no.
- **Credits:** `insufficient_credits` this session (billing gate). Did not call the Superdesign CLI.
- **Implementation:** IBM Carbon `/vat201` DataTable of periods + native date TextInputs to create a bi-monthly range. Select loads `GET /vat201/periods/{id}` draft (live or locked snapshot). Lock (`canMutateBooks`), owner-only reopen modal with reason. CSV/PDF by period id. Old `GET /reports/vat201` helpers kept. No `@f0rge/ui`.
