# Follow-ups (Leo)

## Cloudflare rate limiting

The tag-printer API (`tags-api.leo-figueiredo.com`) has no automated rate-limit
rule in this repo. Configure a Cloudflare WAF/rate-limit rule for
`POST /api/upload-csv` and `POST /api/generate-pdf` if abuse becomes an issue.

Suggested starting point: 30 requests / minute / IP on `/api/*`.
