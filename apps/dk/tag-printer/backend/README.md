# dk tag printer backend

CI sends changed files on the Coolify manual GitHub webhook (`commits[].added`, `modified`, `removed`) so the `apps/dk/tag-printer/backend/**` watch path matches.

The backend deploy is signed with the GitHub Actions secret `COOLIFY_WEBHOOK_DASKASAS_BACKEND`. That must match this app's manual GitHub webhook secret in Coolify. Sibling apps that answer `Invalid signature` do not fail the job.
