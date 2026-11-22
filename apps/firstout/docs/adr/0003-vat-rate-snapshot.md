---
status: accepted
date: 2026-11-22
decided-by: Leo
---

# VAT rate snapshot

Pricing code carries no hard-coded VAT rate. Today it does (`vat.py:8` `VAT_MULTIPLIER = Decimal("1.15")`; frontend `api.ts:889` `1.15` and `api.ts:2891` `0.15`), while the team's `vat_rate` is an editable setting that the PDF prints. Leo asked for whichever is best practice.

The rate comes from the team's `vat_rate` setting at pricing time, and every sale document stores the rate it used next to its VAT amount. Reprints, credit notes and conversions use the stored rate, never today's setting. Existing documents are backfilled with 0.15: live documents were all computed with 1.15; archive rows (`is_archive`) keep Cin7's imported VAT amounts, and their rate is nominal.

SARS applies the rate in force at the time of supply, generally the earlier of invoice or payment (VAT 404 §5.2). A layby's supply happens at delivery (§5.2.7), but at the 2018 change SARS kept the old rate for a layby concluded, and its reserving payment made, before the change (2018 FAQ, question 13). So a layby fixes its rate when it is concluded, and its snapshot carries into its tax invoice.

## Considered options

An effective-dated rate table (rate, valid from), chosen by each document's date. That is the full best practice, but it only matters when the statutory rate changes. South Africa has been at 15% since 1 April 2018; the 2025 proposal to raise it was withdrawn on 24 April 2025, and the February 2026 budget kept 15%. Build it when a Budget announces a rate change; changes are announced weeks before they take effect, and each comes with its own transition rules (VAT 404 §4.5.5). Until then the setting plus the snapshot is enough, and changing the setting is a deliberate act on a known date.

## Sources

- SARS VAT 404 Guide for Vendors, Issue 15, §4.5.5, §5.2, §5.2.7: https://www.sars.gov.za/legal-pub-guide-vat404-vat-404-guide-for-vendors
- SARS FAQ on the 2018 rate increase: https://www.sars.gov.za/lapd-vat-g14-vat-faqs-increase-in-the-vat-rate-from-1-april-2018
- SAnews, 2025 VAT increase withdrawn: https://www.sanews.gov.za/south-africa/proposed-vat-increase-officially-withdrawn
