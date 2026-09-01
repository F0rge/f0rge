# S10 V2 customers CRM — Superdesign outcome

- **Canvas used:** yes (HTML already saved; no Superdesign CLI).
- **Draft:** `cc5ffaf0-b29e-4e81-9923-db9b813e318c` — "Customers CRM".
- **Saved HTML:** `.superdesign/v2-customers.html`.
- **Implementation:** `/customers` (IBM Carbon). Title **Customers CRM**; subtitle from canvas. Toolbar: **New customer** (`canMutateCustomers` = owner|books|till). Client-side filter chips — type (All / Retail / Trade) and balance (Any / Has open invoices / Has active laybys) combined with AND plus name/email/ID search. DataTable: Customer, Type & Tier (Tag + tier), Contact, Open Invoices (`formatZarAmount` + overdue count), Active Laybys (amount + count). New customer modal: name, type, price tier (default `standard`), email, phone, VAT, billing address; POST omits blanks.
- **Deferred from canvas:** SideNav shell, Export CSV, row edit/detail modal, pagination, header search.
