# B3 accountant reports — Superdesign outcome

- **Canvas used:** no.
- **Credits:** `insufficient_credits` this session (billing gate). Did not call the Superdesign CLI.
- **Implementation:** IBM Carbon tabs on existing `/reports` after Balance sheet: Trial balance, Journals, Cash summary. JSON + CSV. Journals optional source TextInput (omit blank; never `""`). Dates via existing `asOf` / `fromDate` / `toDate` + `requireIsoDate`. No `@f0rge/ui`.
