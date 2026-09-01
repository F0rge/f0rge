# S8 V2 catalogue — Superdesign outcome

- **Canvas used:** yes (HTML already fetched; no extra Superdesign credits).
- **Draft:** `85c3d7eb-f0b5-44fc-85f3-5223dd62f364` — "Vellano Catalogue".
- **Team project:** https://superdesign.dev/teams/cb0bbbcd-2f7f-4810-9426-2fbdd5577264/projects/21ee8b12-d1ca-40c6-9b91-312aeb11a9f7
- **Saved HTML:** `.superdesign/v2-catalogue.html`.
- **Implementation:** `/catalogue` (IBM Carbon). Toolbar: SKU search, category chips (All + unique categories), Print labels. DataTable: checkbox selection, SKU/product name, category, Cost (ZAR) from inventory, Retail/Trade inc-VAT, Our barcode, actions (print + edit prices). Create modal optional category. `Sku.category` + `listSkus({ category })` in api.ts. Print opens new window with name, our_ref, barcode monospace; no selection → currently filtered rows.
- **Deferred from canvas:** HTML SideNav (app shell). Tailwind mock styling. Export CSV button. Pagination footer.
