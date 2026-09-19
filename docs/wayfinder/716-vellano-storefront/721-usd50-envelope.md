# 721 — Validate the USD 50 monthly deployment envelope

**Parent:** [#716 Wayfinder: Vellano headless storefront replacement](https://github.com/F0rge/f0rge/issues/716)  
**Issue:** [#721 Validate the USD 50 monthly deployment envelope](https://github.com/F0rge/f0rge/issues/721)  
**Researched:** 2026-09-19 (Europe/Luxembourg, UTC+2)  
**Primary sources only** (vendor pricing pages, official deployment docs, closed map decisions).

## Question

Can the chosen architecture run reliably on Railway with all recurring platform and software subscriptions below USD 50/month, excluding payment transaction fees? Produce a concrete service topology and low/expected/high monthly estimate covering compute, Postgres, Redis if required, object storage and image delivery, hosted identity, transactional email, storefront analytics, monitoring, backups, and traffic assumptions. Identify the first scaling threshold that would breach the ceiling.

## Envelope scope (locked from #716 and closed tickets)

| In the USD 50 platform envelope | Out of envelope |
| --- | --- |
| New storefront + commerce stack (Medusa + DTC Next.js + supporting SaaS) | **Peach / Payfast payment transaction fees** (#718) |
| Railway (or Medusa Cloud) recurring infra for that stack | **Existing Vellano ops Railway project** — treat as already paid separately; map budget is for the storefront architecture (#716) |
| Clerk, PostHog, transactional email, monitoring, backups, object/image delivery for the store | Bob Go / carrier label fees if later adopted (Bob Go PAYG has R0/month; usage not a platform subscription) |
| Domains / TLS that are part of hosting plans | One-time domain registration (amortise outside monthly platform view) |

**Locked choices feeding this ticket:**

- Commerce: Medusa v2 — prefer Medusa Cloud Develop (~USD 29/mo) **or** lean Railway self-host (#717).
- Storefront: Medusa DTC Starter (Next.js) on Railway (preferred for budget control) (#722 / #716).
- Identity: Clerk Hobby USD 0 (#719).
- Payments: Peach Hosted Checkout V2 (fees out of budget) (#718).
- Delivery: Medusa pick-up + fixed shipping; no Bob Go monthly (#718).
- Analytics: PostHog Cloud EU; expected USD 0/mo with USD 5 hard cap if billing enabled (#728).
- Boundary: Medusa owns DTC commerce; Vellano behind Ops API `/v1` (#724).

## Resolution

**Yes — with a lean Railway-first topology under V1 South African furniture traffic, expected recurring platform cost is about USD 32–45/month (low ≈ USD 22–30; high ≈ USD 45–50 before breach), excluding payment fees and existing Vellano Railway spend.**

Reliability at that price assumes right-sized always-on memory, `shared` worker mode only as a temporary V1 compromise if needed, free-tier SaaS for identity/analytics/email/monitoring, Cloudflare R2 (+ optional Images Free) for media, and scripted Postgres dumps to R2 instead of paid backup SaaS. Medusa Cloud Develop (~USD 29) is a viable predictability alternative for the commerce backend, but pairing it with a separate Railway storefront still fits; upgrading Cloud to Launch (from USD 99) or upsizing Railway to a comfortable 2 GB server + dedicated worker + ≥1 GB Postgres is the first clear ceiling breach.

## Chosen service topology (Railway-first)

Prefer a **dedicated Railway project** for the storefront commerce stack (not the existing Vellano ops project), Hobby plan.

```
Internet
  │
  ├─ Cloudflare (DNS / cache optional) ──► R2 bucket (product images; free egress)
  │                                         └─ optional Images Free transforms (5k unique/mo)
  │
  ├─ storefront (Next.js DTC Starter)     Railway service
  │      │ Clerk (Hobby) — passwordless OTP / magic links
  │      │ PostHog Cloud EU — browser events
  │      ▼
  ├─ medusa-server (MEDUSA_WORKER_MODE=server|shared)
  │      │ Peach webhooks (fees out of envelope)
  │      │ Resend (or Medusa notification provider) — order/account email
  │      │ PostHog — server-authoritative commerce events
  │      ▼
  ├─ medusa-worker (optional; MEDUSA_WORKER_MODE=worker)   ← add when jobs contend with API
  ├─ PostgreSQL (+ volume ≤5 GB on Hobby)
  └─ Redis (sessions, event bus, workflow engine, locking, cache)

UptimeRobot Free (or Better Stack Free) → HTTPS checks on storefront + /health
Nightly: pg_dump → gzip → R2 (lifecycle retention)
```

**Why Redis is required:** Medusa’s general production deploy guide requires Postgres **and** Redis, and recommends separate server + worker instances with ≥2 GB RAM for an optimal experience ([General Medusa Application Deployment Guide](https://docs.medusajs.com/learn/deployment/general)). V1 may start with `MEDUSA_WORKER_MODE=shared` on one Medusa service to hold cost, then split worker when background jobs affect request latency.

**SaaS pinned at USD 0 for V1:**

| Concern | Choice | Plan / limit relevant to V1 |
| --- | --- | --- |
| Identity | Clerk Hobby | USD 0; 50k MRU/app; email OTP + magic links; passkeys need Pro USD 25 (#719 deferral) ([clerk.com/pricing](https://clerk.com/pricing)) |
| Analytics | PostHog Cloud EU | USD 0 within free allowances (1M events, 5k recordings, …); set USD 5 billing cap if a card is added (#728) ([posthog.com/pricing](https://posthog.com/pricing)) |
| Transactional email | Resend Free | 3,000 emails/mo, 100/day hard cap ([resend.com/pricing](https://resend.com/pricing)); Medusa Notification Module Provider |
| Object storage + image delivery | Cloudflare R2 Standard free tier + Images Free transforms | 10 GB-mo storage, 1M Class A / 10M Class B ops, free egress; 5k unique transforms/mo ([R2 pricing](https://developers.cloudflare.com/r2/pricing/); [Images pricing](https://developers.cloudflare.com/images/pricing/)) |
| Monitoring | UptimeRobot Free | 50 monitors, 5-minute interval ([uptimerobot.com/pricing](https://uptimerobot.com/pricing/)); Better Stack Free (10 monitors) is an alternative |
| Backups | Scripted `pg_dump` → R2 | No separate SaaS line; Hobby volume max **5 GB** ([Railway plans](https://docs.railway.com/reference/pricing/plans)) |

**Payments / delivery:** Per #718, Peach Hosted Checkout V2 on Growth is treated as **no Growth monthly platform fee** (transaction fees out of envelope); Bob Go stays off until rates/labels are needed (PAYG R0/month). Neither enters the USD 50 subscription sum.

## Railway rate card used for estimates

From [railway.com/pricing](https://railway.com/pricing) and [docs.railway.com/reference/pricing/plans](https://docs.railway.com/reference/pricing/plans) (retrieved 2026-09-19):

| Resource | ≈ Monthly constant |
| --- | --- |
| Memory | USD 10 / GB-month |
| CPU | USD 20 / vCPU-month |
| Volumes | USD 0.15 / GB-month |
| Egress | USD 0.05 / GB |
| Object storage (Railway) | USD 0.015 / GB-month (prefer R2 free tier instead) |
| Hobby subscription | USD 5 / mo including USD 5 usage credit (bill ≈ max(subscription, usage) per Railway’s Hobby examples) |
| Hobby volume size cap | **5 GB** per volume |
| Pro subscription | USD 20 / mo including USD 20 usage (needed if volume >5 GB or team seats) |

Billing is per-second for compute/memory/volumes; always-on services dominate the bill.

## Traffic assumptions (V1 SA furniture DTC)

| Scenario | Sessions / mo | Orders / mo | Notes |
| --- | --- | --- | --- |
| **Low** | ~1–3k | ~10–40 | Soft launch / showroom-led traffic |
| **Expected** | ~5–15k | ~40–150 | Steady domestic DTC + collection |
| **High (still ≤ USD 50)** | ~20–40k | ~150–300 | Peak promo month; still single-region Railway |

Egress and CPU scale with catalogue image weight and PDP concurrency; furniture pages are image-heavy — keep originals on R2 with Cloudflare cache so Railway egress stays small.

## Monthly cost estimates (Railway-first topology)

Figures are **recurring platform + software subscriptions only**. Peach fees, carrier labels, and the existing Vellano Railway project are excluded.

### Line-item model (always-on memory is the main driver)

| Line item | Low | Expected | High (under ceiling) |
| --- | --- | --- | --- |
| Medusa API (`shared` or slim server) | 0.75–1.0 GB → **USD 8–10** | 1.0–1.5 GB → **USD 10–15** | 1.5 GB server → **USD 15** |
| Medusa worker | USD 0 (shared) | 0–0.5 GB → **USD 0–5** | 0.5 GB dedicated → **USD 5** |
| PostgreSQL | 0.5 GB + 1–2 GB vol → **USD 5–6** | 0.5–1.0 GB + 2–4 GB vol → **USD 6–12** | 1.0 GB + 5 GB vol → **USD 11–13** |
| Redis | 0.25 GB → **USD 2.5** | 0.25–0.5 GB → **USD 2.5–5** | 0.5 GB → **USD 5** |
| Next.js storefront | 0.5 GB → **USD 5** | 0.5–0.75 GB → **USD 5–8** | 0.75–1.0 GB → **USD 8–10** |
| Fractional CPU (all services) | **USD 2–4** | **USD 4–8** | **USD 8–12** |
| Railway egress | 5–15 GB → **USD 0.3–0.8** | 20–60 GB → **USD 1–3** | 80–150 GB → **USD 4–8** |
| R2 + Images Free | **USD 0** | **USD 0** (stay in free tier) | **USD 0–3** if Images Paid transforms needed |
| Clerk Hobby | **USD 0** | **USD 0** | **USD 0** (≪ 50k MRU) |
| PostHog Cloud EU | **USD 0** | **USD 0** | **USD 0–5** (hard cap) |
| Resend Free | **USD 0** | **USD 0** | **USD 0** if ≤100 emails/day; else Resend Pro **USD 20** breaches headroom |
| UptimeRobot Free | **USD 0** | **USD 0** | **USD 0** |
| Backups (dump→R2) | **USD 0** | **USD 0** | **USD 0** |
| **Railway usage subtotal** | **≈ USD 23–28** | **≈ USD 32–45** | **≈ USD 48–55** |
| **Envelope total (excl. Peach / Vellano)** | **≈ USD 23–30** | **≈ USD 32–45** | **≈ USD 48–50** (trim RAM/egress) / **breach if >50** |

**Expected operating point to target in capacity planning:** ~1 GB Medusa (shared or thin server), 0.5 GB Postgres + ≤4 GB volume, 0.25–0.5 GB Redis, 0.5 GB storefront, R2 for media → **~USD 35–42/mo**.

### Comfortable production shape (breaches)

Medusa’s ≥2 GB RAM guidance + dedicated worker + 1 GB Postgres + 0.5 GB Redis + 0.75 GB storefront ≈ **2+0.5+1+0.5+0.75 = 4.75 GB RAM ≈ USD 47.50** before CPU and egress — **already at/over the ceiling** once CPU/egress are added. That is why V1 must deliberately right-size below the “optimal” doc floor and watch metrics.

## Alternative topology: Medusa Cloud Develop + Railway storefront

| Line item | Monthly |
| --- | --- |
| Medusa Cloud **Develop** (listed as “Hobby” at USD 29 on the examples page; backend/admin; Cloud emails/cache; storefront hosting available) | **From USD 29** ([medusajs.com/pricing](https://medusajs.com/pricing); [examples](https://medusajs.com/pricing/examples/)) |
| Railway Hobby — DTC Next.js only (if not using Cloud storefront hosting) | **≈ USD 5–12** usage |
| Clerk / PostHog / R2 / UptimeRobot | **USD 0** |
| **Total** | **≈ USD 34–41** |

**Caveats (primary sources):**

- Develop / Hobby Cloud is positioned for development or **low order volumes**; vendor examples cite brief deploy downtime, single point of failure, and slower responses as traffic grows — “not recommended for scaling” ([Medusa Cloud price example](https://medusajs.com/pricing/examples/)).
- **Automatic backups, autoscaling, Redis-backed KV, custom storefront domains** appear on **Launch (from USD 99)** — which **alone exceeds** the USD 50 ceiling ([medusajs.com/pricing](https://medusajs.com/pricing)).
- Develop includes limited compute hours (marketing table: 600 hrs/mo, capped per environment) and usage overages (“Flex Usage”) billed next cycle ([Cloud billing](https://docs.medusajs.com/cloud/billing)). Set a Flex budget alert.

**When to prefer Cloud Develop:** want vendor-tuned Medusa infra and still leave ~USD 10–20 for a Railway storefront + free SaaS. **When to prefer full Railway:** map preference for Railway budget control and avoiding Cloud’s Develop reliability caveats / Launch jump.

## First scaling thresholds that breach USD 50

Ordered by likelihood for this map:

1. **Railway memory floor for “comfortable” Medusa** — Moving to the documented ≥2 GB Medusa process **plus** a dedicated worker **plus** ≥1 GB Postgres pushes always-on RAM toward ~USD 50+ before CPU/egress. **Trigger:** sustained API p95 degradation or job backlog on shared/1 GB sizing. **Mitigation within ceiling:** keep shared worker longer, trim storefront RAM, push all media off Railway egress to R2/CDN — until metrics force the upsizing.
2. **Medusa Cloud Launch upgrade (from USD 99)** — Needed for vendor autoscaling, automatic backups, Redis-backed KV, and production hardening called out above Develop. **Trigger:** Develop downtime/SPOF or Flex overages become unacceptable. **Effect:** immediate hard breach; would require raising the platform ceiling or dropping other paid lines.
3. **Railway Hobby 5 GB volume cap → Pro (USD 20 floor) + larger disk** — Postgres + dump retention on a single Hobby volume tops out at 5 GB. **Trigger:** catalogue assets mistakenly on volume, or DB growth / backup retention on-volume. **Mitigation:** never store product binaries on the Postgres volume; keep dumps and images on R2; only then consider Pro if DB itself needs >5 GB.
4. **Clerk Pro (USD 25/mo) for passkeys** — Deferred in #719. **Trigger:** passkeys mandated. **Effect:** USD 25 + Railway expected USD 35 ≈ **USD 60** (or USD 25 + Cloud Develop USD 29 + storefront ≈ **USD 59+**).
5. **Resend Pro (USD 20/mo)** — Free plan hard-caps **100 emails/day**. **Trigger:** burst order + account email >100/day. **Effect:** USD 20 on top of Railway expected ≈ **USD 52–65**.
6. **PostHog paid usage without a hard cap** — Free tier is large for V1; #728 already requires a **USD 5** billing limit if a card is added. Uncapped viral traffic is a theoretical breach, not the first one.

**Earliest practical breach for a successful V1:** the **Railway memory/worker upsizing** in (1), or a policy decision to buy **Cloud Launch** (2). Passkeys (4) and email burst (5) are product/ops choices that also break the ceiling.

## Reliability notes under the ceiling

| Risk | Mitigation that stays ≤ USD 50 |
| --- | --- |
| Medusa <2 GB RAM | Load-test PDP/cart/checkout; autoscale replicas only if Hobby replica limits and budget allow; prefer fixing N+1 / cache via Redis |
| No managed automatic backups on Railway Hobby / Cloud Develop | Nightly `pg_dump` → R2; test restore quarterly; do **not** rely on Launch backups without raising budget |
| Single-region SPOF | Accept for V1; document RTO/RPO in later ops tickets (#716 “not yet specified”) |
| Image-heavy egress | R2 + Cloudflare cache; avoid proxying binaries through Next.js |
| Deploy downtime (Cloud Develop) | Prefer Railway rolling deploys for storefront; schedule Medusa deploys off-peak if on Cloud |
| Mixing Vellano + storefront on one Railway bill | Keep **separate project**; do not “borrow” Vellano headroom into this envelope |

## Invalidation / revisit triggers

Re-open this envelope if any of the following become true:

1. Measured Railway invoice for the production-shaped stack exceeds USD 50 for two consecutive billing cycles at Expected traffic.  
2. Product requires Clerk passkeys, Cloud Launch features, or Resend >100 emails/day before traffic justifies a higher ceiling.  
3. Postgres needs >5 GB on Railway without moving to an external free/cheap Postgres that stays inside the sum.  
4. Map changes to put **Vellano Railway** costs inside the same USD 50 (would almost certainly fail).  
5. Medusa Cloud Develop Flex Usage or reliability proves unfit and Launch is the only supported path.

## Sources

| Claim area | URL |
| --- | --- |
| Parent map #716 (USD 50, Railway preference, decisions) | https://github.com/F0rge/f0rge/issues/716 |
| This issue #721 | https://github.com/F0rge/f0rge/issues/721 |
| #717 Medusa v2; Cloud Develop ~USD 29 or lean Railway | https://github.com/F0rge/f0rge/issues/717 |
| #718 Peach; pick-up + fixed shipping; Bob Go later | https://github.com/F0rge/f0rge/issues/718 |
| #719 Clerk Hobby USD 0; defer Pro passkeys | https://github.com/F0rge/f0rge/issues/719 |
| #722 Medusa DTC Starter | https://github.com/F0rge/f0rge/issues/722 |
| #724 Commerce / Vellano Ops API boundary | https://github.com/F0rge/f0rge/issues/724 |
| #728 PostHog Cloud EU; expected USD 0; USD 5 cap | https://github.com/F0rge/f0rge/issues/728 |
| Railway public pricing | https://railway.com/pricing |
| Railway plans / Hobby volume / included usage examples | https://docs.railway.com/reference/pricing/plans |
| Medusa Cloud pricing (Develop from USD 29; Launch from USD 99) | https://medusajs.com/pricing |
| Medusa Cloud Develop/Hobby reliability caveats | https://medusajs.com/pricing/examples/ |
| Medusa Cloud billing / Flex Usage | https://docs.medusajs.com/cloud/billing |
| Medusa deploy: Postgres, Redis, server+worker, ≥2 GB | https://docs.medusajs.com/learn/deployment/general |
| Clerk Hobby / Pro pricing | https://clerk.com/pricing |
| PostHog free allowances | https://posthog.com/pricing |
| Resend Free / Pro | https://resend.com/pricing |
| Cloudflare R2 free tier + rates | https://developers.cloudflare.com/r2/pricing/ |
| Cloudflare Images Free transforms | https://developers.cloudflare.com/images/pricing/ |
| UptimeRobot Free (50 monitors, 5 min) | https://uptimerobot.com/pricing/ |
