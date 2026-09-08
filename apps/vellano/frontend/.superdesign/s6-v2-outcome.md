# S6 V2 laybys — Superdesign outcome

- **Canvas used:** yes (HTML already fetched; no extra Superdesign credits).
- **Draft:** `4cac3240-cf43-45d6-9fdd-d9d067a4d35e` — "Vellano Laybys".
- **Team project:** https://superdesign.dev/teams/cb0bbbcd-2f7f-4810-9426-2fbdd5577264/projects/21ee8b12-d1ca-40c6-9b91-312aeb11a9f7
- **Saved HTML:** `.superdesign/v2-laybys.html`.
- **Implementation:** `/laybys` (IBM Carbon). DataTable + New layby modal (customer, SKU lines, 3/6 month duration → `due_date`, hold-stock checkbox, showroom vs all locations, deposit + tender). Manage modal: payment history, record payment, Complete when `ready`, Cancel when `open|ready`. Mutate via `canMutateLaybys` (owner|till). Status: open → Active/Overdue (local date), ready → Ready for collection.
- **Deferred from canvas:** HTML SideNav (app shell). Tailwind mock styling. Monthly installment footer. Print receipt button.
