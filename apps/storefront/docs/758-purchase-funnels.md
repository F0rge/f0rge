# Purchase funnels (#758)

Consented commerce events extend the browsing measurement from
`docs/757-consented-measurement.md`. Optional capture still starts only after
accept, and reject or withdraw still stops it. PostHog Cloud EU project
`292683` ingests at `https://eu.i.posthog.com`. The storefront uses a public
ingestion token. It does not use a personal PostHog API key.

## Events

Browser commerce events use the same allowlist sanitizer as browsing events.
Integer `value_minor` is ZAR cents. Server outcomes are not accepted from the
browser:

- `storefront_order_completed` and `storefront_order_refunded` are planned from
  the verified confirmation payload. When that payload has a stable opaque
  order id, cart confirmation and email confirmation share it and the same
  insert id. Each succeeded refund id is a hash of a stable refund field, not
  the list index, and the raw provider token is not copied into the event. A
  refresh sends the same id and is dropped. Pending refunds are not revenue
  events.
- `storefront_checkout_step_completed` with step `payment` is emitted only
  after payment is confirmed. Preparing checkout records fulfillment, not
  payment.
- `storefront_payment_failed` is planned from the payment route for declined,
  cancelled, and unknown results. A successful checkout does not emit a second
  purchase from that route.

The confirmation and payment responses are returned even when ingestion fails.
A missing analytics id header means consent was not accepted, so the server
sends nothing. Logout calls `resetIdentity()` before the customer session ends.
Sign-in links the anonymous id to the opaque `cus_` id and never uses email.

Payloads drop raw search text, email, tokens, addresses, card data, notes, and
unfiltered URLs. Capture sets `$geoip_disable` and does not send an IP field.
Project-level GeoIP enrichment and IP retention still have to be turned off in
PostHog. That switch is not available from this repo.

## Dashboards

`consentedCommerceDashboards` defines seven saved dashboards: store health,
acquisition, product performance, purchase funnel, search and merchandising,
friction and quality, and accounts. Every dashboard is scoped to
`consented_visitors`. Consented visitors are not a census, and denominators
use that same scope. Revenue and refunds come only from server-confirmed
order and refund events. A checkout total is not revenue. Acquisition joins a
guest campaign to a later order through the anonymous id captured at sign-in.

## Retention, deletion, and cost

Checked against PostHog's pricing and events retention docs
on 2026-10-03:

- Free-plan analytics events are retained for one year. Paid plans keep events
  for seven years. Retention cannot be shortened to delete data.
- Use PostHog person deletion and batch export in project `292683` for requests
  involving personal information. The storefront does not call those APIs.
- Browser events are tagged `production` on the two public HTTPS DasKasas
  origins and `test` elsewhere. Server outcomes default to `test` outside the
  DasKasas production storefront Railway service, unless explicitly configured.
  `NEXT_PUBLIC_STOREFRONT_ANALYTICS_ENV=test` forces test tagging for server outcomes.
- Product detail and successful add-to-bag events carry the public
  `product_title` alongside the stable `product_id`. The product interest
  dashboard groups by ID and shows the most recent reported title.
- The free allowance is 1,000,000 analytics events a month. Above that, the
  free plan drops data. If billing is enabled, set the
  analytics product billing limit to USD 5 so ingestion stops. Alerts at 70%
  and 90% are not a cap. USD 5 sits inside the USD 50 platform budget. A human
  has to set the limit in PostHog billing settings.

## Live walkthrough still unmet

A human still has to click through project `292683` and a running DasKasas:

1. In PostHog, turn off GeoIP enrichment and IP retention. Set the analytics
   billing limit to USD 5, and add alerts at 70% and 90%. Confirm event
   retention is one year and leave session recording off.
2. Put that project's public token in `NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN`
   without committing it.
3. Accept analytics as a guest. Open the shop, a product, the bag, and
   checkout. Choose delivery, complete a test payment, open confirmation, and
   refresh it. Confirm one purchase event.
4. Sign in with the passwordless account. Confirm the anonymous id links to
   the opaque customer id and the payload has no email.
5. Refund the test order and refresh confirmation. Confirm one refund event
   per succeeded refund.
6. Reject analytics in a new session and browse through checkout. Confirm no
   optional capture.
7. Accept, then withdraw from privacy settings, and continue. Confirm capture
   stops.
8. Sign out and confirm the next event uses a new anonymous id.
9. Save the seven dashboard definitions from `consentedCommerceDashboards` in
   PostHog. Confirm revenue tiles use server order and refund events.
10. Block `https://eu.i.posthog.com` and complete checkout. Confirm the order
    still succeeds.
