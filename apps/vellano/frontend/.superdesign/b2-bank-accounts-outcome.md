# B2 bank accounts — Superdesign outcome

- **Canvas used:** no.
- **Credits:** `insufficient_credits` this session (billing gate). Did not call the Superdesign CLI.
- **Implementation:** IBM Carbon on `/bank-reconciliation`. Account Select (`is_bank`), unmatched-count tags, per-account unmatched queue + import filter, match Modal (payment XOR posted journal). No `@f0rge/ui`. Home left on `GET /home` total.
