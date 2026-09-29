# Issues #752 and #753 live walkthrough

Performed on 2026-09-29 against separate disposable Firstout and Medusa Postgres databases, Firstout API `:8005`, Medusa `:9001`, and the local Medusa test-payment provider. No hosted service or real payment was used.

- Migrated a fresh Firstout database from the initial revision through `057_made_to_order_offers` and `058_storefront_fulfillment`, then bootstrapped a fresh Medusa database.
- Created and published a zero-stock sofa with a finite offer of three units and a 28–42 day lead time. The live Ops Commerce response reported physical quantity zero and capacity three; Firstout had no `location_stock` row for the SKU.
- Synced the sofa to Medusa and supplied complete test-only merchandising details. The variant retained zero stocked inventory while its current offer advertised three remaining units. A live Store API cart accepted one sofa and created a finite hold with the 28–42 day customer promise.
- Completed collection checkout through the local test-payment callback. Replaying the callback recovered the same paid order after a deliberately exposed graph-query defect was fixed. The Medusa capacity ledger committed one unit once; Firstout recorded one imported handoff and one acknowledgement. Its Sales Order remained `awaiting_stock`, with no tax invoice or fabricated stock row.
- Changed the collection order to `ready_for_collection` and then `collected` through Firstout's authenticated staff API. The normal Medusa relay function durably applied both events, acknowledged them in Firstout, and queued one status notice for each transition. Replaying an event returned `duplicate` without applying a second transition.

The configured local notification provider logged the confirmation and status messages. No external sender credentials or inbox were configured, so actual email delivery to a recipient was not verified. Peach and Clerk credentials were also unavailable; this walkthrough used the repository's local test payment and guest checkout path.
