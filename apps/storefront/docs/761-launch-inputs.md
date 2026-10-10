# Launch input pack — validation report

Issue #761 asks the launch owner for the real catalogue and operating details. This
repository does not contain that pack. `assessLaunchPack` in
`apps/storefront/commerce/src/launch-pack.ts` is the check engineering runs before
anyone loads a pack. It does not invent stock, prices, policies, or provider access.

No owner pack was supplied on 2026-10-05. Assessing the absent pack returns
`ready: false` with these outstanding checks:

| Section | Code | What is still missing |
| --- | --- | --- |
| Business identity | `business_identity_unconfirmed` | Legal entity, trading name, contact address, VAT position, dedicated support mailbox, named daily reconciliation and support operator, escalation availability, and a recorded owner confirmation. The software name Firstout is not that identity. |
| Catalogue | `catalogue_not_approved` | An owner-approved set of 30–80 sellable variants. Each needs a durable SKU, product group, option combination, VAT-inclusive ZAR price, dimensions, material, care, useful copy, at least three licensed photos of that finish, and an explicit wrong-finish review. |
| Availability and fulfilment | `availability_unconfirmed` | Finite physical stock or a finite, unexpired made-to-order allowance with a confirmed lead-time range; Gauteng zones and VAT-inclusive rates; collection location and instructions; recorded approval of the single mixed-cart promise (slowest line, no split shipment). |
| Policies and skin | `policies_unreviewed` | Reviewed delivery, cancellation/returns/refund, and privacy content; Information Officer and PAIA baseline; cancellation text that distinguishes standard made-to-order from bespoke goods; one final Collector D skin. |
| Provisioning | `provisioning_incomplete` | A checklist for Clerk, Peach, email, PostHog, Railway, and the temporary hostname. Each entry identifies whether access is authorized, whether test and live are separated, and what onboarding remains. No secret values and no customer export. |

The ten Collector D skins remain alternatives. None is selected for launch:
Oxblood / citron, Ultramarine / shell, Forest / bone, Terracotta / chalk,
Ink / saffron, Aubergine / blush, Cobalt / ice, Moss / sand, Charcoal / copper,
Petrol / stone.

## Secure provisioning checklist

Record this outside git, in the owner-controlled channel. Do not paste passwords,
API keys, tokens, or customer exports into the pack, this file, or the issue.

| Channel | Authorized access | Test and live separated | Remaining onboarding |
| --- | --- | --- | --- |
| Clerk | not recorded | not recorded | Owner must grant passwordless customer access and keep test and live apps apart. |
| Peach | not recorded | not recorded | Owner must grant Hosted Checkout access. Test payments stay off any public host. |
| Email | not recorded | not recorded | Owner must name the sender and support mailbox control, without recording credentials. |
| PostHog | not recorded | not recorded | Owner must grant the EU project and keep local or test traffic out of production reports. |
| Railway | not recorded | not recorded | Storefront hosting stays in its own project. Do not use the Marrow project. |
| Temporary hostname | not recorded | not recorded | Owner must authorize a temporary hostname. No permanent domain purchase is required. |

## Walkthrough

Command, from `apps/storefront/commerce`:

```bash
npx ts-node --swc -O '{"module":"commonjs"}' -e 'const { assessLaunchPack } = require("./src/launch-pack"); console.log(JSON.stringify(assessLaunchPack(undefined), null, 2));'
```

Result on 2026-10-05: `ready` is false and the five rows above are the only findings.
The private catalogue and checkout were not reviewed with the owner, because there
is no approved pack to place on that journey. Representative stocked and lead-time
pieces therefore were not checked against a running store. That owner review remains
an open launch check. Closing this issue would not authorize a public launch.

A fictional 30-variant pack exists only inside `launch-pack.test.ts` to prove a
complete shape can pass. It is not the retailer's catalogue and must not be loaded.
