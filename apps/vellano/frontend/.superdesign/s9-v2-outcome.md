# S9 V2 till — Superdesign outcome

- **Canvas used:** yes (HTML already saved; no Superdesign CLI).
- **Draft:** `3b26c41b-a7bd-4a1a-91b2-4605848cd20d` — "Till".
- **Saved HTML:** `.superdesign/v2-till.html`.
- **Implementation:** `/till` (IBM Carbon). Header actions → `/returns`, `/laybys`. Add-product tile (showroom, SKU, qty) appends cart lines with discount %. Cart table: inc-VAT unit price, discount NumberInput 0–100, line total, remove. Sale summary: subtotal, line discounts, VAT via `computeInvoicePreview` on discounted ex subtotal, total. Tender Select cash/card/deposit; **Complete Sale** posts `{ tender }`. Tax invoice tile after sale; Process Return deep-links `?invoice=`.
- **Deferred from canvas:** SideNav shell, customer search, amount tendered / change, EFT tender, browse catalogue search.
