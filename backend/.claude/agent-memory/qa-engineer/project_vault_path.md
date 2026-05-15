---
name: Vault path varies by env
description: backend/.env can override the default vault path; check before grepping rendered markdown
type: project
---

`CLAUDE.md` documents the vault as `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Brain/`, but `backend/.env` can override `VAULT_PATH`. On Leo's dev machine the actual configured path is:

```
/Users/leo/Library/Mobile Documents/iCloud~md~obsidian/Documents/Health-Research
```

Daily files: `<VAULT_PATH>/Daily/Health-Logs/YYYY-MM-DD.md`.

**Why:** spent time grepping the wrong vault directory and getting empty results during the meal_time/alcohol QA gate.

**How to apply:** before any "verify vault rendered output" check, `grep VAULT_PATH backend/.env` to get the live path. Compose the full file path from that, not from `CLAUDE.md`.
