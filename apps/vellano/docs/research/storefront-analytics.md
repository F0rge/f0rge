# Storefront analytics and measurement decision

**Status:** Accepted for V1  
**Research date:** 2026-09-19  
**Related issue:** [#728](https://github.com/F0rge/f0rge/issues/728)

## Decision

Use **PostHog Cloud in the EU region** as the V1 Storefront analytics platform.
Instrument the Next.js Storefront for browsing and interaction events, and use
Medusa for authoritative commerce outcomes such as successful payment, completed
order, and refund. Put both behind a small typed analytics interface owned by the
Storefront application so the provider can be replaced without changing commerce
workflows.

Start on PostHog's free plan. At the time of this decision it includes one million
product analytics events and 5,000 session recordings per month, one project, and
one year of data retention. The free plan stops ingestion at the limits rather
than producing an unexpected charge. If a card is added later, set a **USD 5/month
hard billing limit** for analytics and alert at 70% and 90% of each allowance.
PostHog currently prices usage above the free tier at USD 0.00005 per analytics
event and USD 0.005 per recording. Pricing must be checked again during
implementation. [PostHog pricing](https://posthog.com/pricing)

Do not self-host PostHog for V1. Its breadth would add operational and database
cost to the Railway footprint without improving the customer experience. Cloud
keeps analytics outside the Storefront's USD 50/month application budget in the
expected launch range.

## Why this option

| Option | Fit for Vellano | Cost at launch | Decision |
|---|---|---:|---|
| PostHog Cloud EU | Product and web analytics, funnels, paths, heatmaps, replay, client/server SDKs, and a native Medusa provider | Expected USD 0 | **Choose** |
| Umami Cloud or self-hosted | Privacy-focused analytics, custom events, funnels, replay, performance, and API; cloud has a free hobby tier | USD 0 or Railway resources | Strong fallback if a simpler platform or self-hosting becomes more important |
| Plausible Business | Clear EU-hosted analytics with custom properties, revenue attribution, funnels, and journeys | USD 19/month at 10k pageviews | Too much of the total budget for less product-analysis depth |
| Google Analytics 4 | Mature ecommerce event model and advertising integrations | USD 0 before BigQuery usage | Defer until Google Ads or Merchant Center creates a concrete need; it duplicates collection and does not replace replay or heatmaps |

PostHog has documented Next.js browser and server SDK support, custom event
capture, replay, and client/server identity linking. Medusa has an Analytics
Module from v2.8.3 with a maintained PostHog provider and custom-provider seam.
Together those remove most custom transport work while preserving the
application-owned event contract.

Sources:

- [PostHog Next.js integration](https://posthog.com/docs/libraries/next-js)
- [Medusa Analytics Module](https://docs.medusajs.com/resources/infrastructure-modules/analytics)
- [Umami capabilities](https://docs.umami.is/docs/about) and [Cloud FAQ](https://docs.umami.is/docs/cloud/faq)
- [Plausible plans and features](https://plausible.io/)
- [GA4 ecommerce events](https://developers.google.com/analytics/devguides/collection/ga4/ecommerce)

## Integration boundary

The Storefront owns an application-facing interface such as:

```ts
type Analytics = {
  capture<E extends StorefrontEvent>(event: E): void
  identify(customerId: string): void
  reset(): void
}
```

The concrete browser adapter sends approved events to PostHog. UI components
call domain helpers such as `trackProductViewed` rather than importing the
PostHog SDK directly. This keeps names, required properties, privacy rules, and
provider replacement in one place.

Medusa emits server-authoritative events through its Analytics Module only after
the corresponding business transition succeeds. The exact trigger for
`order_completed`, `payment_failed`, and `order_refunded` must follow the order
lifecycle decision in [#727](https://github.com/F0rge/f0rge/issues/727); a browser
thank-you page is not proof that payment or order creation succeeded.

Use the same random analytics distinct ID across the browser, Storefront server,
and Medusa request. PostHog documents tracing headers for linking browser and
server activity. Restrict those headers to the Storefront's own API host. Save the
anonymous ID on the Medusa cart/order metadata needed for attribution, without
making analytics part of order fulfillment or the operational record.

## Identity model

- Before sign-in, PostHog assigns a random anonymous distinct ID.
- After Clerk authentication, identify the visitor with the stable Clerk subject
  or a stable internal customer ID. Never use email, phone number, or display name
  as the analytics ID.
- On sign-out, call `reset()` so a later user of the same browser does not inherit
  the previous customer's history.
- Guest checkout stays anonymous. Carry its random analytics ID through cart and
  order metadata so a server-side completion event can join the same journey.
- Do not add names, email addresses, telephone numbers, street addresses, payment
  details, passwords, customer notes, or free text as event properties.

These choices follow PostHog's documented guidance to use a stable authentication
ID and reset identity on logout. [PostHog identity guidance](https://posthog.com/docs/libraries/next-js#identifying-users)

## Event contract

Event names use `snake_case`. Every event includes `schema_version`,
`environment`, anonymous or authenticated `distinct_id`, session ID, UTC
timestamp, current path, referrer class, and available UTM values. Prices and
revenue are integer minor units with `currency: "ZAR"`.

Do not use unrestricted DOM autocapture as the source of business metrics.
Automatic capture is limited to page views, page leave, performance, dead clicks,
and an explicit element allowlist. Product, cart, checkout, and purchase metrics
come from semantic events.

| Event | Source | Required business properties |
|---|---|---|
| `product_list_viewed` | Browser | `list_id`, `category_id?`, `item_count` |
| `product_selected` | Browser | `product_id`, `variant_id?`, `list_id`, `position` |
| `product_viewed` | Browser | `product_id`, `variant_id?`, `category_id?`, `price_minor` |
| `product_view_ended` | Browser | `product_id`, `variant_id?`, `active_ms`, `gallery_interactions` |
| `product_media_interacted` | Browser | `product_id`, `media_type`, `action`, `position?` |
| `variant_selected` | Browser | `product_id`, `variant_id` |
| `search_performed` | Browser | `result_count`, `query_length`, `filter_count`; no raw query |
| `filter_applied` | Browser | `filter_type`, `value_id` |
| `cart_item_added` | Browser | `product_id`, `variant_id`, `quantity`, `value_minor` |
| `cart_item_removed` | Browser | `product_id`, `variant_id`, `quantity`, `value_minor` |
| `cart_viewed` | Browser | `item_count`, `value_minor` |
| `checkout_started` | Browser | `cart_id`, `item_count`, `value_minor`, `checkout_type` |
| `checkout_step_completed` | Browser | `cart_id`, `step`, `checkout_type` |
| `shipping_method_selected` | Browser | `cart_id`, `method_id` |
| `account_created` | Browser/server | `method: "passwordless"` |
| `account_signed_in` | Browser/server | `method: "passwordless"` |
| `payment_failed` | Medusa | `analytics_order_id`, `provider`, `reason_family`; no provider payload |
| `order_completed` | Medusa | `analytics_order_id`, `value_minor`, `item_count`, product/variant IDs, `customer_type` |
| `order_refunded` | Medusa | `analytics_order_id`, `refund_minor`, product/variant IDs |

`checkout_type` is `guest` or `account`; `customer_type` is `new`, `returning`,
or `guest`. Use opaque order and cart analytics identifiers rather than public
order numbers when possible.

### Product engagement time

`product_view_ended.active_ms` measures active attention, not elapsed time with a
tab open:

1. Start when the product detail content is at least 50% visible and the document
   is both visible and focused.
2. Pause when the tab is hidden, loses focus, the product leaves the viewport, or
   no pointer, keyboard, touch, or scroll activity occurs for 30 seconds.
3. Resume on renewed qualifying activity.
4. Emit once on route change or page leave using a transport that survives
   navigation.

This definition answers “how long did someone look at this item” consistently and
avoids inflated durations from abandoned tabs.

## Consent, minimisation, and replay

POPIA regulates the processing of personal information and cross-border flows.
The implementation therefore needs a documented purpose, limited collection,
appropriate safeguards, a processor agreement, and a privacy review before
launch. This decision is an engineering baseline, not a substitute for that
review. [South African Government POPIA overview](https://www.gov.za/documents/protection-personal-information-act)

Apply these V1 rules:

- Create the PostHog project in its **EU (Frankfurt)** region.
- Start opted out of persistent analytics. Enable it only after the visitor's
  analytics choice is known. If cookieless collection after rejection is desired,
  approve that separately in the privacy review; PostHog supports cookieless
  operation, but the SDK setting alone does not decide Vellano's lawful basis.
- Keep all text and input masking enabled for replay. Mark dynamic customer data
  as no-capture and add an automated check that common personal-data property
  names cannot be sent.
- Record at most 10% of eligible sessions. Permit replay on catalogue, search,
  product, and cart pages. Stop recording on authentication, account, checkout,
  hosted payment, and order-confirmation routes.
- Do not capture console output, request or response bodies, uploaded files, raw
  search text, or third-party payment frames.
- Disable GeoIP enrichment and IP retention unless a later, documented reporting
  need justifies them.
- Use the free plan's one-year analytics retention initially. Review the setting
  before launch and annually. Use PostHog's person deletion API for verified
  deletion requests; its documentation notes that plan retention cannot simply
  be shortened as a deletion mechanism.
- Put production and non-production events in distinct projects when the plan
  permits it; until then, disable developer-local capture and use an
  `environment` property plus saved production filters.

PostHog documents opt-in defaults, cookieless operation, page-view/page-leave
capture, dead clicks, heatmaps, and text masking in its
[JavaScript configuration](https://posthog.com/docs/libraries/js/config). Inputs
are masked by default and all text can be masked before replay data is sent; see
[session replay privacy controls](https://posthog.com/docs/session-replay/privacy).
Its [data controls](https://posthog.com/docs/privacy/data-storage) include person
and event deletion paths. Security and processor documents are available through
the [PostHog Trust Center](https://trust.posthog.com/).

## Dashboards and launch questions

Create these saved dashboards before public launch:

1. **Store health:** visitors, sessions, orders, conversion rate, revenue, average
   order value, revenue per session, and new/returning/guest mix.
2. **Acquisition:** referrer and UTM source through product view, checkout, and
   order completion.
3. **Product performance:** unique viewers, median and 75th-percentile active
   viewing time, media interactions, variant selection, add-to-cart rate,
   conversion, revenue, and stock availability by product.
4. **Purchase funnel:** product list → product → cart → checkout → shipping →
   payment → completed order, sliced by device, source, and guest/account flow.
5. **Search and merchandising:** searches, no-result rate, filters, list click
   through rate, and conversion after search. Raw search text remains excluded.
6. **Friction and quality:** dead clicks, repeated clicks, JavaScript errors, slow
   web vitals, and links to eligible masked replays.
7. **Accounts:** account creation and sign-in rates plus guest versus authenticated
   conversion.

The first release is complete only when each dashboard can be exercised through a
live-server walkthrough and the same test order appears once in the browser
funnel and once as the server-authoritative completion event.

## Cost guardrails

The expected launch cost is USD 0/month. A conservative envelope shows why:

- At 20 captured analytics events per session, 50,000 monthly sessions consume
  the one-million-event free allowance.
- With 10% replay sampling, 50,000 eligible sessions consume the 5,000-recording
  allowance.
- One million additional analytics events would currently cost USD 50, while
  1,000 additional recordings would cost USD 5. This makes event-volume control
  more important than replay overage.

Use a property allowlist and event-volume dashboard, and remove noisy events
before raising the USD 5 cap. Analytics spending counts toward the Storefront's
platform budget even though the expected line item is zero.

## Revisit triggers

Re-evaluate the provider when any of these becomes true:

- Google Ads or Merchant Center attribution becomes a launch dependency.
- The free tier is exceeded for two consecutive months after noisy-event cleanup.
- Legal review rejects the EU cloud processing arrangement or requires local
  hosting.
- The team cannot obtain trustworthy funnels or product-level engagement from the
  agreed event contract.
- Operating a self-hosted analytics service becomes cheaper after accounting for
  engineering time, database storage, backups, upgrades, and incident response.

If a change is required, keep the semantic event schema and replace the adapter.
Umami is the preferred first alternative; GA4 can be added as a narrow marketing
destination without making it the Storefront's source for product analytics.
