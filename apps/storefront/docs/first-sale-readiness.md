# First-sale readiness

This check records whether a private Storefront rehearsal is ready for an owner decision. It does not turn public selling on, does not spend money, and does not invent a catalogue, policy text, or provider credential.

`assessFirstSaleReadiness` in `apps/storefront/commerce/src/first-sale-readiness.ts` reads a recorded evidence file. With no file, the result is `decision: "no_go"`, `public_selling: false`, `public_selling_changed: false`, and `release_gate: "open"`. A passing file can report `decision: "go"` and `release_gate: "closed"`. That report still leaves `public_selling` false. Closing the evidence gate does not change Railway, Peach, Clerk, indexing, or the payment simulator.

The fictional Northwind pack inside the unit test only proves the checker. Do not pass that fixture to the script.

## Command

From `apps/storefront/commerce`:

```bash
npx ts-node --swc -O '{"module":"commonjs"}' src/scripts/assess-first-sale.ts
```

With no file, the command exits 1. The printed summary lists the missing owner inputs. It does not print secrets and it does not write orders, products, or configuration.

When an owner later supplies a recorded evidence file outside git:

```bash
npx ts-node --swc -O '{"module":"commonjs"}' src/scripts/assess-first-sale.ts /path/to/first-sale-evidence.json
```

The file may contain a launch pack, hosted purchase records, operator recovery records, an analytics rehearsal record, a private capacity run, measured cost lines, environment identity, and an owner decision. A secret-shaped value or the Marrow Railway project id keeps the gate open, and the secret is not copied into the summary.

## What the evidence has to show

- Hosted guest and Clerk purchases that together cover stocked goods, confirmed lead-time goods, Gauteng delivery, and collection. Each verified payment has one commerce order, one Firstout sales order, and one storefront payment journal for the same ZAR amount. Cash or EFT is not a substitute.
- An operator progressed delivery and collection, took a partial refund and a full refund without restocking, recorded a separate return, and showed customer status, notifications, and reconciliation converging. Closed-browser payment, a duplicate callback, a Firstout outage, and an unknown financial outcome are recorded. The duplicate callback keeps a single order. The outage keeps the paid order queued. The unknown outcome is reconciled rather than repeated.
- Consented, rejected, and withdrawn analytics journeys. Rejected and withdrawn visitors emit no optional events. Replay stays off for sign-in, account, checkout, and order confirmation. All seven dashboards are present and their rows contain no email address. Analytics must not block commerce. `assessAnalyticsRehearsal` in the web app produces that record from captured events.
- A private hosted capacity run: 20 concurrent shoppers, 30 minutes, five simulator completions a minute, stock sync on, first-party cart/checkout p95 at or under 1 second, unexpected errors under 1 percent, no out-of-memory stop, no growing backlog, and no duplicate effect. The in-process probe refuses a publicly reachable simulator and cannot close this gate.
- Measured monthly Storefront cost for compute, staging, media, backups, and SaaS, with the usage assumptions written down. The total must be at most USD 50. Payment fees, carrier charges, and existing Firstout hosting are disclosed beside that total and are not counted inside it. A total above USD 50 stays a no-go pending an owner decision.
- Environment identity for a private, non-indexable Storefront project, with public selling off. The Marrow project and the Firstout project do not qualify. Callbacks, allowed origins, sender records, backup evidence, restore evidence, at least two alerts, reviewed policies inside the launch pack, and a named operator are required.
- An explicit owner decision for public selling and for any real-money rehearsal. Five real orders across at least 14 days are a follow-up after an authorized launch, not a prelaunch requirement.

## Rollback

If this check fails, leave the storefront private and non-indexable, and do not start new payment attempts. Do not enable the payment simulator on a public deployment. Redeploy the last verified git release. Do not restore by overwriting paid-order tables or integration state. Use an isolated restore, then reconcile provider, order, stock, and capacity before checkout is opened again. The readiness command itself writes nothing, so stopping it is enough to leave the current release unchanged.

## Still missing before a hosted rehearsal

No owner catalogue pack, reviewed policies, provider credentials, callback configuration, sender records, named operator handover, or measured hosted cost is in this repository. The 30-minute private capacity run was not executed here. Hosted guest and Clerk purchases, Peach, and Firstout financial results were not exercised against a live stack. Public selling stays off.
