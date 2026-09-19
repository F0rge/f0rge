# #719 — Select hosted passwordless customer identity

**Map:** [Wayfinder: Vellano headless storefront replacement](https://github.com/F0rge/f0rge/issues/716)  
**Ticket:** [Select hosted passwordless customer identity](https://github.com/F0rge/f0rge/issues/719)  
**Researched:** 2026-09-19 (Europe/Luxembourg)  
**Constraint:** Storefront must not store customer passwords; authentication must be hosted and passwordless; guest checkout preserved; identity cost must fit inside the **USD 50/month total platform** ceiling (payment transaction fees excluded).

## Resolution

**Use Clerk Hobby (free) as the hosted customer identity plane for V1, with email verification codes and/or email magic links only — passwords disabled — then bridge a verified Clerk session into the commerce engine’s customer Auth identity (a thin custom Medusa Auth Module Provider when Medusa is the engine).** Guest checkout stays on the engine’s guest customer path (`has_account=false`); optional accounts create/link a registered customer for saved addresses and order history. Defer Clerk passkeys (Pro, $25/mo) until the envelope ticket proves spare budget. Do **not** use Medusa’s built-in `emailpass` for storefront customers (it stores password material in the Auth Module). Auth0 Free is the closest runner-up if passkeys-on-free becomes a hard V1 requirement; Supabase Auth Free is rejected for production because Free projects pause after inactivity and Pro ($25) competes with Railway for the same $50 envelope.

---

## Decision criteria (from ticket + map)

| Criterion | What “good” means for Vellano V1 |
| --- | --- |
| Passwordless + no app-held passwords | Magic link / email OTP / passkeys; Storefront and Vellano apps never hash or store customer passwords |
| Guest checkout | Cart → checkout → order without registering |
| Optional account | Post-purchase or deliberate signup → order history + saved addresses |
| Account linking | Guest email ↔ registered identity; social/OAuth optional later |
| Data portability | Export/delete customer identity data for POPIA-style requests |
| Abuse controls | Rate limits, bot/disposable-email controls without burning the $50 envelope |
| SA availability | Service usable by SA shoppers; residency is US/EU for all free hosted options — document transfer basis |
| Next.js + engine | First-class Next.js DX; pluggable into Medusa Auth Module (benchmark engine) |
| Cost | Prefer **$0** identity so Railway/Postgres/Redis/email consume the $50 |

---

## Candidates compared

### 1. Clerk (recommended)

**Sources:** [Clerk Pricing](https://clerk.com/pricing), [Sign-up and sign-in options](https://clerk.com/docs/authentication/configuration/sign-up-sign-in-options), [Next.js quickstart](https://clerk.com/docs/nextjs/getting-started/quickstart), [Data Processing Addendum](https://clerk.com/legal/dpa).

| Dimension | Finding |
| --- | --- |
| Magic links / email OTP | **Hobby:** email verification codes and email verification links (magic links) included. Links expire after 10 minutes; optional same-device/browser requirement. |
| Passkeys | **Pro+ only** in production ($25/mo monthly / $20/mo annual). Available in development without upgrade. |
| Passwords | Can be **disabled** in Dashboard/CLI so new customers never set one — satisfies map “passwordless” and “must not store customer passwords” in our apps (Clerk holds auth factors). |
| Account linking | Automatic account linking on Hobby+. |
| Abuse | Hobby: account lockout/brute-force, bot protection, block email subaddresses, block disposable emails. Allowlist/blocklist and user bans need Pro. |
| Data portability | Full data exports on all plans; DPA with deletion/return within 90 days of agreement end; API for data-subject assistance. |
| Next.js | Official `@clerk/nextjs`, `ClerkProvider`, middleware/`proxy.ts`, prebuilt components. |
| SA / residency | Globally available. DPA: Clerk may store/process data where it or subprocessors maintain facilities; EU–US transfers via Data Privacy Framework / SCCs. **No South Africa data region** on Hobby. Adequate for V1 if privacy notice + transfer basis are documented; not SA-sovereign hosting. |
| Cost vs $50 envelope | **Hobby = $0** up to 50,000 MRUs/app. Pro ($25) would consume half the platform budget — defer unless passkeys or allowlists become mandatory. |
| Engine integration | No first-party Medusa provider. Integrate via Medusa’s documented **custom Auth Module Provider** (`AbstractAuthModuleProvider`) that validates a Clerk session/JWT and creates/links a Medusa `authIdentity` for `customer`, then uses existing Store APIs for addresses/orders. |

**Fit:** Best V1 balance of free passwordless surface, Next.js DX, abuse defaults, and export/DPA posture without spending the envelope.

### 2. Auth0 (runner-up)

**Sources:** [Auth0 Pricing](https://auth0.com/pricing), [Passwordless overview](https://auth0.com/docs/authenticate/passwordless), [Magic Links](https://auth0.com/docs/authenticate/passwordless/authentication-methods/email-magic-link).

| Dimension | Finding |
| --- | --- |
| Passwordless | Free plan includes Passwordless Authentication and **Passkeys**. |
| Magic links | Supported, but **not on Universal Login** — Classic Login only; same-browser requirement (painful on iOS). Email OTP is the safer Free-tier UX. |
| Account linking | **Not on Free** — Essentials+. Passwordless identities are a distinct connection type; duplicates need linking when paid. |
| Abuse | Free: brute-force + suspicious IP throttling. Enhanced attack protection is Professional+. |
| Cost | Free up to **25,000 MAU**. Essentials starts at **$35/mo** for 500 MAU — already most of the $50 platform ceiling. |
| Next.js / engine | Auth0 Next.js SDK exists; Medusa still needs a custom Auth Module Provider. |
| SA / residency | Service available; public cloud regions documented for EU/UK/etc., not SA-local residency on Free. |

**Fit:** Prefer if **passkeys on day one at $0** outweigh Classic Login magic-link friction and missing Free-tier account linking. Otherwise Clerk Hobby is simpler for a Next.js furniture storefront.

### 3. Supabase Auth (not recommended for this envelope)

**Sources:** [Supabase Pricing](https://supabase.com/pricing), [Passwordless email](https://supabase.com/docs/guides/auth/auth-email-passwordless).

| Dimension | Finding |
| --- | --- |
| Magic link / OTP | First-class; Free includes 50,000 MAU. |
| Production Free caveat | Free projects **pause after 1 week of inactivity** — unsuitable as sole production IdP. |
| Pro cost | **$25/mo** base (plus compute credits model) — competes directly with Railway for the $50 total. |
| Stack fit | Pulls a second Postgres/auth stack beside Medusa/Railway; no Medusa-native adapter. |

**Fit:** Reject for V1 unless the commerce engine decision already commits to Supabase as the primary data plane (unlikely given Medusa benchmark).

### 4. Firebase Authentication (backup)

**Sources:** [Email link auth](https://firebase.google.com/docs/auth/web/email-link-auth), [Firebase Pricing](https://firebase.google.com/pricing), [Firebase privacy — Auth US-only](https://firebase.google.com/support/privacy).

| Dimension | Finding |
| --- | --- |
| Email link | Supported; Spark/Blaze include “Other Authentication services”; Identity Platform path: 50K MAUs no-cost then Google Cloud pricing. |
| Residency | **Firebase Authentication processes data exclusively in US data centers** — weaker POPIA narrative than Clerk DPF/SCC packaging. |
| Next.js / Medusa | Works via Firebase JS SDK; custom Medusa Auth provider still required; DX less storefront-oriented than Clerk. |

**Fit:** Viable $0 backup; prefer Clerk for DX and documented DPA/DPF packaging.

### 5. Stytch (out for budget)

**Source:** [Stytch Pricing](https://stytch.com/pricing).

Pay-as-you-go includes a free MAU band, but **customizable brand & login experience is a $99 fixed add-on** — alone exceeds the entire $50 platform ceiling. Not a V1 candidate.

### 6. Medusa engine-native Auth (insufficient alone)

**Sources:** [Auth Module](https://docs.medusajs.com/resources/commerce-modules/auth), [Auth providers](https://docs.medusajs.com/resources/commerce-modules/auth/auth-providers) (Emailpass, Google, GitHub only), [Create Auth Module Provider](https://docs.medusajs.com/resources/references/auth/provider), [Customer accounts / guest](https://docs.medusajs.com/resources/commerce-modules/customer/customer-accounts), [Checkout addresses](https://docs.medusajs.com/resources/storefront-development/checkout/address), [Transfer cart customer](https://docs.medusajs.com/resources/storefront-development/cart/update).

| Dimension | Finding |
| --- | --- |
| Built-in providers | **Emailpass** (password), **Google**, **GitHub**. No first-party magic-link or passkey provider. |
| Password storage | Emailpass register/update flows are designed around password credentials in provider metadata — conflicts with “hosted passwordless” / “must not store customer passwords.” |
| Guest checkout | Guest order creates `Customer` with `has_account=false`. Registering the same email creates a **separate** `has_account=true` record (at most one guest + one registered per email). Cart can be transferred to the logged-in customer after auth (`transferCart` / Change Cart Customer). |
| Saved addresses / orders | Logged-in customer: `POST/GET /store/customers/me/addresses`; cart addresses are a different model — must explicitly save. Order history is authenticated customer orders; guests use order ID lookup. |
| Extension | Custom Auth Module Provider is the supported way to plug Clerk/Auth0/etc. Community options (e.g. Better Auth plugins) exist but are third-party, not Medusa-owned — treat as optional later, not V1 dependency. |

**Fit:** Use Medusa for **commerce customer records, addresses, orders, guest checkout**; use **hosted IdP** for authentication factors. Disable/omit `emailpass` for the `customer` actor via `authMethodsPerActor` once the custom provider is live.

---

## Recommended architecture (engine-agnostic shape, Medusa-shaped)

```text
Storefront (Next.js)
  ├─ Guest path: create cart → set email/addresses → payment → order
  │     (Medusa Customer has_account=false)
  └─ Optional account:
        Clerk (email OTP or magic link, passwords off)
          → verify session
          → Medusa custom Auth provider → customer JWT/session
          → create/link Customer has_account=true
          → transferCart if guest cart exists
          → /store/customers/me/addresses + order history
```

1. **Never** collect a customer password in the Storefront.  
2. **Commerce data** (addresses, orders) lives in the Commerce Engine, keyed by engine customer id; store Clerk `userId` (or Auth0 `sub`) in customer metadata for correlation.  
3. **Guest → account linking:** after passwordless signup with the same email, transfer the active cart; document that historical guest orders are not auto-merged (Medusa creates a new registered customer row) — offer “look up order by id/email” and optional staff merge later.  
4. **Email delivery:** Clerk/Auth0 built-in email is fine for low volume; production deliverability may later use the shop’s SMTP (Vellano already has SMTP settings) via provider custom SMTP — cost stays inside existing ops, not a new SaaS line.  
5. **Abuse:** keep Clerk Hobby bot + disposable-email blocks; rate-limit magic-link requests at the Storefront/BFF edge.  
6. **POPIA:** no free hosted IdP offers SA-only residency. Rely on provider DPA + transparency notice that identity data is processed offshore; keep order/PII operational copies in Railway/Postgres under Vellano control where possible. See [Information Regulator POPIA](https://inforegulator.org.za/popia/) for responsible-party duties (security safeguards, data-subject requests).

---

## Cost envelope (identity slice)

| Option | Identity $/mo at V1 scale (≪ 10k MAU) | Leaves for Railway/etc. inside $50 |
| --- | --- | --- |
| **Clerk Hobby** | **$0** | ~$50 |
| Auth0 Free | $0 | ~$50 |
| Firebase Auth (≤50k MAU) | $0 | ~$50 |
| Clerk Pro (passkeys) | $25 | ~$25 — tight |
| Auth0 Essentials | ≥$35 | ≤$15 — breaks envelope |
| Supabase Pro | $25 | ~$25 — tight + pause risk if Free |
| Stytch branded UI add-on | $99 | **over ceiling** |

Identity should stay on a **$0 free tier** until ticket [Validate the USD 50 monthly deployment envelope](https://github.com/F0rge/f0rge/issues/721) closes with headroom.

---

## Invalidation conditions

Revisit this decision if any of the following become true:

1. **Passkeys are mandatory at V1 launch** and Auth0 Free’s Classic Login constraints are unacceptable — then either Auth0 Free (OTP + passkeys) or Clerk Pro if envelope #721 shows ≥$25 spare.  
2. **Commerce engine is not Medusa** and ships a first-party hosted passwordless adapter that already meets the no-password rule — prefer engine-native over a second IdP.  
3. **POPIA / contractual residency** requires SA-only processing of identity — none of the free hosted options qualify; would force self-hosted auth (e.g. Better Auth in-region) and a map-level scope change.  
4. **Clerk Hobby feature gates** (no production passkeys, no allowlist/blocklist) cause measurable abuse — upgrade to Pro only after envelope proof.  
5. **Clerk pricing or MRU definition changes** so Hobby is no longer free for production storefronts.

---

## Explicit non-choices

- Medusa `emailpass` for storefront customers.  
- Building a custom magic-link system in Next.js/Vellano (reintroduces secret storage and abuse surface).  
- Supabase Auth Free as production IdP (pause policy).  
- Stytch branded UI at $99.  
- Paying Auth0 Essentials ($35+) inside the $50 platform ceiling.

---

## Key sources

1. https://clerk.com/pricing  
2. https://clerk.com/docs/authentication/configuration/sign-up-sign-in-options  
3. https://clerk.com/docs/nextjs/getting-started/quickstart  
4. https://clerk.com/legal/dpa  
5. https://auth0.com/pricing  
6. https://auth0.com/docs/authenticate/passwordless  
7. https://auth0.com/docs/authenticate/passwordless/authentication-methods/email-magic-link  
8. https://supabase.com/pricing  
9. https://supabase.com/docs/guides/auth/auth-email-passwordless  
10. https://firebase.google.com/docs/auth/web/email-link-auth  
11. https://firebase.google.com/pricing  
12. https://firebase.google.com/support/privacy  
13. https://stytch.com/pricing  
14. https://docs.medusajs.com/resources/commerce-modules/auth  
15. https://docs.medusajs.com/resources/commerce-modules/auth/auth-providers  
16. https://docs.medusajs.com/resources/references/auth/provider  
17. https://docs.medusajs.com/resources/commerce-modules/customer/customer-accounts  
18. https://docs.medusajs.com/resources/storefront-development/checkout/address  
19. https://docs.medusajs.com/resources/storefront-development/cart/update  
20. https://inforegulator.org.za/popia/  
21. https://github.com/F0rge/f0rge/issues/716  
22. https://github.com/F0rge/f0rge/issues/719  
