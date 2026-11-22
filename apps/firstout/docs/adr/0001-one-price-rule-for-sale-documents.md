---
status: accepted
date: 2026-11-22
decided-by: Leo
---

# One price rule for every sale document

Every sale document (till sale, quote, sales order, layby, books tax invoice, the draft reprice, and a storefront order where Firstout prices its lines) prices its lines through one rule on the server. Today the till, quotes, sales orders, laybys, books invoices and the draft reprice each carry their own copy, and the copies disagree on rounding and on where the unit price comes from. Leo asked for whichever is best practice; laybys honouring price lists was his explicit call.

The rule:

1. **Unit price**: the customer's hand-made price list, then the customer's classification tier, then Retail. Laybys follow it too; today they use the Retail price only (`laybys.py:402`).
2. **Line amount**: round once per line, half-up to the cent: `line_ex = round_half_up(unit_ex × qty × (100 − discount%) / 100, 2)`.
3. **VAT**: per line, from the rounded line amount, then summed: `line_inc = round_half_up(line_ex × (1 + rate), 2)`, `line_vat = line_inc − line_ex`. The rate is the document's VAT rate snapshot ([0003](0003-vat-rate-snapshot.md)).
4. **Rounding** is `ROUND_HALF_UP`, stated explicitly. Python's `Decimal` defaults to half-even.
5. **The browser does not price.** It shows the server's preview.

## Considered options

- **Round the discounted unit, then multiply** (today's quotes, sales orders and draft reprice, through `discounted_unit_ex`). Rejected: the error grows with quantity. R33.33 × 3 at 10% is R89.99 rounded once per line, R90.00 rounded per unit.
- **VAT once on the document subtotal** (Sage 200; Odoo "round globally"). Fewer rounding steps, but the printed line amounts including VAT then no longer add up to the total, which matters when shelf prices include VAT. SARS accepts either: a tax invoice may show the total and the VAT charged (VAT 404 §13.3). Xero rounds per line, as we do.

## Consequences

- A document prints the list unit price and the discount %, never a "discounted unit" that will not multiply out to the line amount.
- Rounding a cash total to the nearest coin is a separate step at payment (BGR 65), not part of line pricing.
- Known limit, not decided here: South African shelf prices must include VAT (VAT 404), but Firstout stores ex-VAT units to the cent, so some inclusive prices do not round-trip (R999 incl. → R868.70 excl. → R999.01 incl.). Storing the inclusive price, storing ex-VAT to four decimals, or using the tax fraction 15/115 each need their own decision.

## Sources

- SARS VAT 404 Guide for Vendors, Issue 15, §13.3: https://www.sars.gov.za/legal-pub-guide-vat404-vat-404-guide-for-vendors
- SARS BGR 65, rounding in cash transactions: https://www.sars.gov.za/legal-intr-r-bgr-65-value-added-tax-treatment-of-rounding-difference-in-cash-transactions
- Xero line item amount: https://rubydoc.info/gems/xero-ruby/XeroRuby/Accounting/LineItem
