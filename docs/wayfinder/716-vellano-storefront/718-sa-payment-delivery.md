# #718 Select South African payment and delivery services

**Map:** [Wayfinder: Vellano headless storefront replacement](https://github.com/F0rge/f0rge/issues/716)  
**Ticket:** [Select South African payment and delivery services](https://github.com/F0rge/f0rge/issues/718)  
**Researched:** 2026-09-19 (Europe/Luxembourg)  
**Constraint:** USD 50/month platform budget excludes payment transaction fees; Medusa is the likely commerce engine; showroom collection is required; V1 is South Africa / ZAR only.

## Resolution

**V1 payment:** Peach Payments **Growth** (Hosted Checkout V2) as the primary gateway; **Payfast** Aggregation as the fallback if Peach onboarding/sandbox access is slow or Growth eligibility fails.  
**V1 delivery:** Medusa **pick-up** fulfillment set for showroom/warehouse collection, plus a **minimal fixed/rule-based** shipping option (metro / rest-of-RSA flat or simple zone table) fulfilled manually—no courier aggregator subscription in V1. **Bob Go** Pay-as-you-go (R0/month platform fee) is the integration fallback when live carrier rates and labels become necessary.

---

## Payment providers compared

Candidates evaluated against primary sources: **Peach Payments**, **Payfast** (Network), **Yoco** Checkout API, and **Ozow** (pay-by-bank specialist, complementary only).

### Comparison matrix

| Criterion | Peach Payments (Growth) | Payfast Aggregation | Yoco Checkout API (Core) | Ozow One API |
| --- | --- | --- | --- | --- |
| **Payment methods (SA consumer)** | Local/int'l cards (3DS), Pay by Bank, Capitec Pay, Apple/Google/Samsung Pay, Payflex, Mobicred, Scan to Pay, others | Cards, Instant EFT, Capitec Pay, Apple/Google/Samsung Pay, SnapScan, Zapper, Mobicred, Payflex, MoreTyme, MukuruPay, Scode, store cards, etc. (18+) | Visa/Mastercard debit & credit, Apple Pay, Google Pay; ZAR only | Pay-by-bank / Instant EFT family (redirect hosted page) |
| **Settlement** | Free automated **next business day** daily settlements (Growth FAQ) | Available balance after **48-hour withholding**; payout fee **R8.70** ex VAT; Immediate Payout **0.8%** (min R14) | Up to **2 business days** to bank; Standard/Weekly payout free on Core | Settlements API available; timing merchant-specific (not a full card gateway) |
| **Refunds** | Checkout webhooks include `RF` / refund state changes; Growth lists Refunds | Dashboard full/partial refunds; Refunds API; **R2.00** ex VAT per refund | `POST /checkouts/{id}/refund`; `202 Accepted` then `refund.succeeded` webhook; **live keys only** | One API refunds scope |
| **Webhook reliability** | HMAC-SHA256 signing; known IP range; **retry up to 30 days** with exponential backoff | ITN: return HTTP 200 or retry immediately → 10 min → exponential; signature + validate endpoint; documented IP ranges | Checkout webhooks (`payment.succeeded`, refund events); register via API | Svix-signed webhooks; replay endpoint; idempotency required |
| **Medusa / API fit** | Hosted Checkout V2 (OAuth JWT + JSON); Medusa `AbstractPaymentProvider` + `/hooks/payment/...`; unofficial Medusa v2 Peach provider exists as reference | Redirect form + ITN (or Onsite beta / REST APIs); no official Medusa plugin—custom provider | Hosted Checkout API (`payments.yoco.com`); Bearer secret key; custom Medusa provider | One API OAuth; custom provider; **not** a sole V1 gateway (narrow methods) |
| **Sandbox quality** | Dedicated sandbox dashboard + `testsecure.peachpayments.com`; Postman + sample projects; access via Peach onboarding | Self-serve **sandbox.payfast.co.za**; ITN once; wallet simulation (not full method UI); public test merchant credentials documented | Test keys immediate (no domain verify); test cards in Yoco App; test txns excluded from live sales reports | Staging hosts; staging credentials on request; production payin tests move real money |
| **Recurring fixed cost** | Growth: **no setup, no monthly** (Enterprise may add fees; tokenisation listed R200/mo on fees page) | Aggregation: **no monthly / no setup** | Core: **R0/month**; Plus R249 / Pro R499 (incl VAT) | No public fixed monthly required for payins (verify at signup) |
| **Transaction fees (ex VAT, published)** | Local cards 3DS: **2.95% + R1.50**; Pay by Bank / Capitec Pay: **1.50% + R1.50**; Apple/Google/Samsung Pay: **2.95% + R1.50**; Payflex higher | Cards / wallets: **3.2% + R2**; Instant EFT / Capitec Pay: **2.0%** (min R2); BNPL higher | Online local debit/credit (Core &lt;R50k): **2.95% + R2**; +15% VAT on fees | Nedbank Direct EFT etc. published on Ozow pricing pages (pay-by-bank focused) |
| **Operational support** | Growth: 365-day phone & email; Enterprise adds dedicated AM | support@payfast.help / 021 300 4455; docs + managed plugins support limits | In-app chat; Core standard support; Priority on paid plans | support@ozow.com; Hub docs |

Sources for fee/settlement cells: [Peach fees](https://www.peachpayments.com/fees/), [Payfast fees](https://payfast.io/fees), [Payfast merchant FAQ (payout / 48h)](https://payfast.io/faq/merchant-faqs/), [Yoco plans & fees](https://support.yoco.help/en/articles/270145-all-about-yoco-plans-and-fees), [Yoco online store settlement](https://support.yoco.help/en/articles/109553-how-to-integrate-yoco-with-your-online-store).

### Peach Payments (recommended primary)

**Why it wins for V1**

1. **Lower published card and pay-by-bank fees** than Payfast Aggregation on the Growth schedule (2.95%+R1.50 vs 3.2%+R2 cards; 1.5%+R1.50 vs 2% Instant EFT-class), which matters for furniture AOV while still sitting outside the USD 50 platform budget ([Peach fees](https://www.peachpayments.com/fees/), [Payfast fees](https://payfast.io/fees)).
2. **Modern Hosted Checkout V2** (OAuth token → `POST /v2/checkout` → redirect) maps cleanly onto Medusa’s payment-provider pattern (`initiatePayment` returns redirect URL; `getWebhookActionAndData` drives authorize/capture) ([Peach Hosted Checkout V2](https://developer.peachpayments.com/docs/v2-checkout-hosted), [Medusa payment provider](https://docs.medusajs.com/resources/references/payment/provider)).
3. **Webhook reliability** is explicitly strong: HMAC signing headers, known IPs, and **30-day exponential retry** until HTTP 200 ([Peach Checkout webhooks](https://developer.peachpayments.com/docs/checkout-webhooks)).
4. **Free next-business-day settlements** with no payout flat fee on the Growth narrative ([Peach fees FAQ](https://www.peachpayments.com/fees/)).
5. **Zero Growth monthly fee**, compatible with the platform budget ([Peach fees FAQ](https://www.peachpayments.com/fees/)).
6. Community **Medusa v2 Peach provider** ([Max-Bissolati/medusa-payment-peach-payments](https://github.com/Max-Bissolati/medusa-payment-peach-payments)) is unofficial but demonstrates a production-shaped Checkout V2 + webhook + refund path—useful as implementation reference, not as a hard dependency.

**Caveats**

- Sandbox/live credentials come through Peach onboarding / Dashboard Connect; sandbox is first-class once account access exists ([Peach sandbox docs](https://developer.peachpayments.com/docs/dashboard-sandbox)).
- Hosted Checkout links must not be unfurled (WhatsApp preview burns the one-load) ([Peach Hosted Checkout V2](https://developer.peachpayments.com/docs/v2-checkout-hosted)).
- Enterprise / tokenisation add-ons can introduce monthly fees (R300 account / R200 tokenisation on the published fees table)—avoid for V1 guest checkout ([Peach fees](https://www.peachpayments.com/fees/)).

### Payfast (recommended fallback)

**Strengths**

- Broadest SA method catalogue (Instant EFT, Capitec Pay, wallets, BNPL, cash-adjacent) ([Payfast fees](https://payfast.io/fees), [custom integration payment_method codes](https://developers.payfast.co.za/docs)).
- **No monthly fee** on Aggregation ([Payfast fees](https://payfast.io/fees)).
- Mature, self-serve **sandbox** with documented test merchant credentials, ITN viewer, and validate endpoint ([Payfast docs – Testing and tools](https://developers.payfast.co.za/docs)).
- ITN is the source of truth: signature, amount check, server validate, HTTP 200 ack with retries ([Payfast Step 4 confirmations](https://developers.payfast.co.za/docs)).
- Dashboard + Refunds API for full/partial refunds; R2 refund fee ([Payfast merchant FAQ](https://payfast.io/faq/merchant-faqs/), [Payfast fees](https://payfast.io/fees)).

**Weaknesses vs Peach for this storefront**

- Higher published card and Instant EFT rates.
- Settlement is wallet + **48h withhold** then payout (**R8.70**/payout), not automatic next-day bank deposit ([Payfast merchant FAQ](https://payfast.io/faq/merchant-faqs/)).
- Integration model is older (signed HTML form redirect + ITN); Onsite is beta. Custom Medusa provider is still straightforward but less JSON-native than Peach V2.
- Sandbox does **not** simulate real card/EFT UIs (wallet-only), so method-specific UX must be validated carefully in live/low-value tests ([Payfast Sandbox limitations](https://developers.payfast.co.za/docs)).

### Yoco (not primary for V1)

- Strong **Checkout API**, webhooks, and Core **R0** plan ([Yoco Checkout API](https://support.yoco.help/en/articles/739322-yoco-checkout-api), [Yoco fees](https://support.yoco.help/en/articles/270145-all-about-yoco-plans-and-fees)).
- Online Core card rate **2.95% + R2** is close to Peach on cards but **weaker Instant EFT / Capitec Pay positioning** for SA furniture shoppers; Gateway docs emphasise cards + Apple/Google Pay ([Yoco online store](https://support.yoco.help/en/articles/109553-how-to-integrate-yoco-with-your-online-store)).
- **No subscriptions/recurring** on Gateway (fine for V1 guest checkout) ([Yoco online store](https://support.yoco.help/en/articles/109553-how-to-integrate-yoco-with-your-online-store)).
- Refunds via Checkout API require **live** keys; async via webhook ([Yoco refunding guide](https://yoco.docs.buildwithfern.com/guides/online-payments/refunding-a-payment.md)).
- Domain verification gates live keys ([Yoco testing](https://yoco.docs.buildwithfern.com/docs/checkout-api/testing.md)).
- Keep as a future option if showroom POS unification with Yoco hardware becomes a priority; not the best sole online gateway for V1 method coverage.

### Ozow (complementary only)

- Excellent **pay-by-bank** API (One API, Svix webhooks, staging) ([Ozow Hub](https://hub.ozow.com/api-reference.md)).
- Peach and Payfast already include Instant EFT / Pay by Bank / Capitec Pay in one hosted checkout—adding Ozow as a second provider increases Medusa surface area without unlocking unique V1 methods. Revisit only if Peach/Payfast bank success rates disappoint.

### Medusa integration notes (all gateways)

- Implement a custom Payment Module Provider extending `AbstractPaymentProvider`; expose redirect URL from `initiatePayment`; treat browser return as non-authoritative; complete via `getWebhookActionAndData` on Medusa’s `/hooks/payment/{identifier}_{id}` route ([Medusa create payment provider](https://docs.medusajs.com/resources/references/payment/provider), [webhook events](https://docs.medusajs.com/resources/commerce-modules/payment/webhook-events)).
- Prefer **capture-on-authorize** (or immediate debit `DB`) for physical goods prepaid V1 unless pre-auth stock hold is required later.
- Store provider payment/checkout IDs in session `data` and merchant reference = Medusa payment session / cart id for recon.

---

## Delivery options compared

Furniture is bulky and often out-of-gauge for economy parcel networks. V1 should optimise for **operational simplicity and zero platform fee**, not multi-courier rate shopping.

### Options

| Approach | Fixed cost | Customer experience | Ops | Medusa fit | Fit for V1 furniture |
| --- | --- | --- | --- | --- | --- |
| **A. Showroom / warehouse collection** | R0 platform | Required; free or fixed booking fee | Staff hand-over; order marked fulfilled on collection | Native fulfillment set `type: "pick-up"` + service zone ([Medusa fulfillment concepts](https://docs.medusajs.com/resources/commerce-modules/fulfillment/concepts)) | **Required** |
| **B. Minimal fixed / rule-based shipping** | R0 (config only) | Flat fee by metro vs national, weight/volume band, or cart threshold | Manual booking with preferred carrier; tracking pasted into order notes / email | Flat or calculated shipping options on a `shipping` fulfillment set; optional custom fulfillment provider that no-ops label creation | **Recommended V1 ship path** |
| **C. Bob Go aggregator** | **R0/month** Pay-as-you-go; paid plans R249–R1 999 ex VAT for discounts/features | Live multi-courier rates at checkout; labels; tracking; Bob Box lockers | Portal + open API; sandbox available | Custom fulfillment provider calling Bob Go rates/orders/shipments APIs ([Bob Go pricing](https://www.bobgo.co.za/pricing), [apps & API](https://www.bobgo.co.za/apps-integrations)) | **Fallback when live rates needed** |
| **D. Shiplogic / The Courier Guy** | Account-based courier charges; sandbox free but rates demonstrative | ECO/OVN/STD/SDX + lockers via Shiplogic API | Webhooks configured in portal (not via API); door-to-door parcels | Custom fulfillment provider to `api.shiplogic.com` ([TCG WooCommerce / API notes](https://wordpress.org/plugins/the-courier-guy/), [Locker API PDF](https://thecourierguy.co.za/wp-content/uploads/2025/08/The-Courier-Guy-Locker-API-docs.pdf)) | Better for parcel SKUs than large furniture; optional later |

### Recommended V1 delivery combination

1. **Pick-up (showroom/collection point)** — Medusa `pick-up` fulfillment set, geo-restricted to the showroom’s service zone, price R0 (or a small hold fee if desired). Required by map Notes.
2. **Domestic delivery — fixed/rule-based** — e.g. “Johannesburg metro”, “Cape Town metro”, “Rest of South Africa” with static ZAR prices (and optional free-shipping threshold). Fulfillment remains **manual**: ops books a furniture-capable carrier offline; storefront only collects address + fee.
3. **Do not** subscribe to Bob Go paid plans or wire Shiplogic in V1 unless catalogue weight/size proves parcel-compatible; both add integration and exception-handling cost while fixed rates keep the USD 50 budget intact.

### Delivery fallback

When checkout needs **live quotes / labels / tracking webhooks**:

- Prefer **Bob Go Pay-as-you-go (R0 pm)** first—multi-courier rates without a subscription, sandbox for integration, open API for Medusa ([Bob Go pricing](https://www.bobgo.co.za/pricing), [Bob Go apps & API](https://www.bobgo.co.za/apps-integrations)).
- Use **Shiplogic / The Courier Guy** if the merchant already has a TCG account or needs TCG lockers specifically; remember webhooks are portal-configured and furniture may still need a specialist last-mile ([Nevuto TCG notes citing Shiplogic](https://help.nevuto.com/the-courier-guy)).

---

## Recommended V1 combination and fallback

| Layer | Primary | Fallback |
| --- | --- | --- |
| **Payments** | Peach Payments Growth — Hosted Checkout V2, Medusa custom payment provider, ITN/webhook-driven capture | Payfast Aggregation — redirect + ITN Medusa provider if Peach onboarding blocks launch |
| **Delivery** | Medusa pick-up (showroom) + fixed/rule-based domestic shipping options; manual carrier booking | Bob Go Pay-as-you-go for live rates/labels; Shiplogic/TCG only if parcel/locker flows dominate |

**Out of V1 (payment):** Ozow as second gateway; Yoco as sole online gateway; Peach Enterprise / tokenisation monthly add-ons; BNPL enablement unless conversion data demands it.  
**Out of V1 (delivery):** Paid Bob Go plans; automatic multi-carrier checkout; white-glove furniture API unless a dedicated carrier contract appears later.

---

## Key sources

### Payments

- [Peach Payments fees](https://www.peachpayments.com/fees/)
- [Peach Hosted Checkout V2](https://developer.peachpayments.com/docs/v2-checkout-hosted)
- [Peach Checkout webhooks](https://developer.peachpayments.com/docs/checkout-webhooks)
- [Peach Dashboard sandbox](https://developer.peachpayments.com/docs/dashboard-sandbox)
- [Payfast fees](https://payfast.io/fees)
- [Payfast developer documentation (custom integration, ITN, sandbox)](https://developers.payfast.co.za/docs)
- [Payfast merchant FAQs (payout, refunds, 48h)](https://payfast.io/faq/merchant-faqs/)
- [Yoco plans and fees](https://support.yoco.help/en/articles/270145-all-about-yoco-plans-and-fees)
- [Yoco Checkout API](https://support.yoco.help/en/articles/739322-yoco-checkout-api)
- [Yoco refunding a payment](https://yoco.docs.buildwithfern.com/guides/online-payments/refunding-a-payment.md)
- [Yoco online store / settlement / no recurring](https://support.yoco.help/en/articles/109553-how-to-integrate-yoco-with-your-online-store)
- [Ozow API reference](https://hub.ozow.com/api-reference.md)
- [Medusa Payment Module Provider](https://docs.medusajs.com/resources/references/payment/provider)
- [Unofficial Medusa Peach provider (reference only)](https://github.com/Max-Bissolati/medusa-payment-peach-payments)

### Delivery

- [Medusa fulfillment concepts (shipping vs pick-up)](https://docs.medusajs.com/resources/commerce-modules/fulfillment/concepts)
- [Bob Go pricing](https://www.bobgo.co.za/pricing)
- [Bob Go apps & open API](https://www.bobgo.co.za/apps-integrations)
- [The Courier Guy WooCommerce / ShipLogic notes](https://wordpress.org/plugins/the-courier-guy/)
- [The Courier Guy Locker API (Shiplogic)](https://thecourierguy.co.za/wp-content/uploads/2025/08/The-Courier-Guy-Locker-API-docs.pdf)

