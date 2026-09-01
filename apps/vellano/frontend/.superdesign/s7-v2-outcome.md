# S7 V2 home hub — Superdesign outcome

- **Canvas used:** yes (HTML already fetched; no extra Superdesign credits).
- **Draft:** `2d67462c-32c2-4baf-90c8-bdef3893e5bd` — "Vellano Home Dashboard".
- **Team project:** https://superdesign.dev/teams/cb0bbbcd-2f7f-4810-9426-2fbdd5577264/projects/21ee8b12-d1ca-40c6-9b91-312aeb11a9f7
- **Saved HTML:** `.superdesign/v2-home.html`.
- **Implementation:** `/` home hub (IBM Carbon). Six KPI tiles (on order, on hand, aged stock &gt;180d, open laybys count+balance, low-stock SKUs with `cds--text-error` when &gt;0, returns open). Two-column tables: needs attention (kind-mapped ghost actions → `router.push(href)`), recent movements (`en-ZA` datetime). `HomeSummary` extended in `api.ts` for `GET /home`.
- **Deferred from canvas:** HTML SideNav/header shell (app layout). Tailwind mock styling. Coloured movement-type tags (plain source text). Layby action label "Review" in mock → spec uses **View**.
