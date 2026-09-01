# B0 journals — Superdesign outcome

- **Canvas used:** no. Superdesign auth works (`fetch-design-nodes` on project `21ee8b12-…`).
- **Credits:** `execute-flow-pages` from V2 home draft `2d67462c-…` failed with `insufficient_credits` (`upgrade_url` billing gate). Did not retry.
- **Implementation:** IBM Carbon cloned from `/invoices` + UIShell (`Notebook` icon, `BOOKS_NAV_ITEMS`). List DataTable + create Modal (date, narration, status Draft/Posted default Posted, account/debit/credit lines, running totals). View lines in a passive Modal. Post/Void on the list; void confirm is a small danger Modal. Mutate via `canMutateBooks` (owner|books).
