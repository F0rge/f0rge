---
status: accepted
date: 2026-11-26
decided-by: Leo
---

# Sale quantity rule

Some pieces are sold only in batches: dining chairs in pairs, a modular sofa in a set of four. Each SKU carries "Sold in multiples of" (`sell_multiple`, default 1) and "Minimum quantity" (`min_sell_qty`, default 1, always a multiple of the first; the database enforces both). Firstout's sale documents and the DasKasas shop must both honour it, and one rule must decide it so the till, quotes, laybys, invoices and the trade portal never disagree.

- **One place.** Sale line pricing ([0001](0001-one-price-rule-for-sale-documents.md)) checks every line: a line breaks the rule when its quantity is not a multiple of `sell_multiple` or is below `min_sell_qty`. Lines without a SKU are never checked. A kit line is checked against the kit SKU's own rule; its components' rules do not apply.
- **Report, then refuse.** A preview returns the line's message ("Oslo dining chair is sold in multiples of 2, minimum 4.") in `quantity_rule`, and `blocked_by = "quantity_rule"` when the user may not break the rule. Saving or completing refuses with HTTP 409, `detail.code = "sale_quantity_rule"`, listing every offending line.
- **Authority.** Breaking a batch (one replacement chair) is a pricing decision, so it rides on `sales.price_override` ([0002](0002-discount-and-price-override-authority.md)); no new permission. The preview still tells that user the rule is being broken. The trade portal has no authority and is refused. Firstout's own draft reprice uses system authority and is never refused.
- **Kept lines.** In the spirit of 0002's kept values, a saved line whose SKU and quantity are unchanged is not checked again, so tightening a SKU's rule never blocks re-saving or finishing an existing document. Unlike 0002, a customer change does not re-check it: the rule belongs to the SKU, not the customer. Copying a quote into a sales order, completing a layby and running a repeating invoice (whose lines carry no SKU) do not re-price and are never blocked. Ringing up a saved quote or a held sale at the till keeps each line's saved quantity while it is unchanged; a changed quantity or an added line is checked. Only the quantity is kept there: the till still authorises prices and discounts afresh (0002). A held line keeps its quantity only if it met the rule when it was held, or the holder could break it, so holding a sale is never a way round the rule.
- **The shop enforces before payment; Firstout never refuses a paid order.** The feed sends the rule only when commerce asks (`include_sell_rules=true`); commerce refuses off-rule carts when lines are added or changed, and turns an off-rule bag into a review at the checkout hold, so payment cannot start. Storefront order intake records a paid order whatever its quantities, because the customer has already paid.

## Consequences

- Staff without `sales.price_override` cannot sell an off-rule quantity anywhere in Firstout; owners (the only preset with the permission) can, with a visible notice.
- A rule change takes effect for new and changed lines only.
- If a shop order arrives off-rule (a rule tightened between payment and import, or a commerce bug), Firstout records it and staff deal with it; Firstout refuses nothing after payment. On the shop side, the Paystack webhook re-runs the checkout hold after payment, so a rule tightened between payment start and the webhook turns that paid cart into a paid exception for staff instead of an order, the same way price and stock drift are handled.

## Considered options

A separate `sales.break_batch` permission (rejected: an override already lets a user charge any price, so a separate key adds a role decision without adding control). Enforcing at storefront intake (rejected: it would refuse orders the customer has paid for).
