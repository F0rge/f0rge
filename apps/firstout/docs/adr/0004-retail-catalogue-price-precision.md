---
status: proposed
---

# Preserve the VAT-inclusive catalogue retail price

When staff enter a VAT-inclusive retail price, Firstout converts it at the team's current VAT rate. Keep the ex-VAT price to the cent whenever it converts back to the entered retail price. Truncate the unrounded ex-VAT amount to four decimal places when the two-decimal conversion would lose a cent. This preserves the original invoice unit when it rounds to cents. For example, storing R868.6956 ex VAT preserves a catalogue and DasKasas price of R999.00 at 15% VAT.

Keeping one stored ex-VAT price lets the catalogue and its storefront feed derive the inclusive price from the team's current rate. Storing an additional gross price would also require deciding how to reconcile the two amounts when the VAT rate changes. Existing stored prices keep their values through the schema upgrade.

Firstout sale documents continue to use [ADR 0001](0001-one-price-rule-for-sale-documents.md) and the [document VAT rate snapshot](0003-vat-rate-snapshot.md). Firstout invoices round the ex-VAT unit price to cents, then calculate the line amount and VAT. Their totals can differ from the catalogue price multiplied by quantity.
