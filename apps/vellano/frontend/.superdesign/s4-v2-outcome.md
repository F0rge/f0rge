# S4 V2 CSV import — Superdesign outcome

- **Canvas used:** yes (HTML already fetched; no extra Superdesign credits).
- **Draft:** `7dc0776c-8ae6-4f9c-803d-2dad50346c36` — "Vellano - Import CSV".
- **Team project:** https://superdesign.dev/teams/cb0bbbcd-2f7f-4810-9426-2fbdd5577264/projects/21ee8b12-d1ca-40c6-9b91-312aeb11a9f7
- **Saved HTML:** `.superdesign/v2-csv-import.html`.
- **Implementation:** `/import` (IBM Carbon). Two `FileUploaderDropContainer` zones (inventory required, SOH optional), client template downloads, Preview & Column Mapping tables (CSV header → field Select + sample), validation errors table, Re-preview + Start Import (`preview.ok`). Mutate via `canMutateCatalogue` (owner|buyer).
- **Deferred from canvas:** HTML SideNav (app shell). Cin7-branded subtitle. ComboBox. Cancel button (no draft to discard).
