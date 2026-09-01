# S5 V2 returns / RMA — Superdesign outcome

- **Canvas used:** yes (HTML already fetched; no extra Superdesign credits).
- **Draft:** `de9a5ce8-d75a-4c9f-bd57-2f3caa81b55e` — "Vellano - Returns / RMA".
- **Team project:** https://superdesign.dev/teams/cb0bbbcd-2f7f-4810-9426-2fbdd5577264/projects/21ee8b12-d1ca-40c6-9b91-312aeb11a9f7
- **Saved HTML:** `.superdesign/v2-returns.html`.
- **Implementation:** `/returns` (IBM Carbon). DataTable + New Return modal (invoice, location, reason, disposition, line qty NumberInputs). Mutate via `canMutateReturns` (owner|warehouse|till). Draft status shown as **Pending inspection**; Process/Cancel on draft rows; View CN → `/credit-notes`. `?invoice=<uuid>` opens modal with invoice preselected. Books invoices without `sku_id` force write-off and disable Restock SelectItem.
- **Deferred from canvas:** HTML SideNav (app shell). Tailwind mock styling. Separate return detail page.
