# Ops Commerce money snapshots

The `v1` paid-order wire uses ZAR cents. The captured payment and order total
are authoritative. Gross line and delivery amounts are allocated to that
rounded total using Medusa's exact decimal values: floor each component to cents,
then assign the remaining cents in descending fractional-remainder order.
Equal remainders use external line ID order, with delivery last. VAT uses the
same rule against the rounded native order VAT total, bounded by each component's
gross cents. This avoids treating a line-rounding difference as delivery VAT.
Rounding uses decimal half-up; source prices and tax rates are never recomputed.

A line's `unit_ex_minor_zar` is its floor net unit price. The additive optional
`unit_ex_remainder_minor_zar` counts how many first units receive one extra net
cent. It must be smaller than quantity and satisfy:

`unit_ex_minor_zar * quantity + unit_ex_remainder_minor_zar = ex_minor_zar`.

Zero remainders are omitted from canonical serialized payloads, so existing
idempotency hashes are unchanged. Line identity and gross cents remain the
refund allocation weights; rounding never splits or renames order lines.

The durable handoff payload retains the full allocation. Sales-order unit prices
are the two-decimal base; tax invoices use the immutable line net/VAT/gross and
delivery snapshot rather than multiplying the base or recalculating VAT.

Both initial import and later staff invoicing load that snapshot from the durable
handoff. Made-to-order and mixed orders retain the accepted delivery fee and exact
line cents when stock arrives. Lines are matched by their original Storefront
identity, SKU, quantity and base unit price, independently of database row order;
a changed operational line blocks invoicing instead of reallocating paid money.
Current catalogue prices are irrelevant to the accepted invoice. Deposits (less
any completed refunds) are applied to the full paid invoice under the existing
refund and books-period guards.
