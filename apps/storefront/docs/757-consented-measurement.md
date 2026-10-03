# Consented browsing measurement (#757)

Optional analytics stays off until a visitor accepts it. The browser adapter
posts allowlisted events to PostHog Cloud EU (`https://eu.i.posthog.com`) with a
public test project token. Persistence, autocapture, session replay and cookies
are unused. Reject and withdraw stop capture, abort in-flight requests, and
invalidate in-memory attribution. Necessary operational records (orders, bag,
accounts) do not depend on this adapter.

## Events

Allowed names: `storefront_page_viewed`, `storefront_product_impressed`,
`storefront_product_selected`, `storefront_product_viewed`,
`storefront_product_media_selected`, `storefront_product_variant_selected`,
`storefront_search_results_viewed`, `storefront_product_attention_summary`.

Payloads never include raw search text, email, tokens, private notes, or
unfiltered URLs and referrers. Campaign values are sanitized; referrers are
host-only.

Product active time uses a viewport-sized sticky measurement region (`50dvh`,
`100dvh` on small screens). Time accrues only when that region is at least 50%
visible (or covers 50% of the viewport on long pages), the document is focused
and visible, and the visitor has interacted within 30 seconds. Leave summaries
are sent once.

## Reports

Initial reports (also implemented by `consentedBrowsingReports`):

- Acquisition: accepted page views grouped by `page_key`, `utm_source` and
  `utm_campaign` with `event_count`
- Product: impressions and selections grouped by `surface` and `product_id` with
  `event_count`; attention grouped by `product_id` with summed `active_seconds`
- Search: result counts grouped by `availability`, `sort_order` and
  `query_present` (summed `result_count`)

Every report is scoped to `consented_visitors`. Labels must state that consented
visitors are not a census, and denominators stay on that same consent scope.

## Live walkthrough (local test sink)

Verified 2026-10-03 with Playwright Chromium against `http://localhost:3004`, the
synthetic Medusa fixture on `:9011`, and `NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN=phc_test_fixture`.
Playwright intercepted `https://eu.i.posthog.com/i/v0/e/`; no production PostHog
project was used.

- Rejected session: consent banner reject, then shop browse — zero capture requests.
- Later accept: `storefront_page_viewed` and `storefront_search_results_viewed` with
  sanitized `utm_source`/`utm_campaign`/`referrer_host` only. Search text, email,
  tokens and referrer paths were absent from payloads and headers had no cookie/referer.
- Withdraw: further navigations sent nothing; no PostHog cookies or distinct-id keys
  remained in storage.
- Product attention (390×844): 5s focused + 60s hidden + 5s focused → one summary
  with `active_seconds: 10`. Duplicate leave summaries were not sent.
- Shop impressions and reports: consented events built acquisition/product/search
  reports labeled “Consented visitors are not a census.”
- Capture endpoint returning 500 still allowed shop and product browsing.

`npm test`, `npm run typecheck`, and `npm run lint` in `apps/storefront/web` passed
(4 existing `<img>` warnings). `STOREFRONT_ANALYTICS_E2E=true npx playwright test e2e/analytics.spec.ts` — 5 passed.

## Test sink

Use `NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN=phc_test_fixture` with Playwright
intercepting `https://eu.i.posthog.com/i/v0/e/`. Do not point the storefront at a
production PostHog project for this work. Analytics HTTP failures must not block
shop or product browsing.
