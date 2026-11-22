---
status: accepted
date: 2026-11-22
decided-by: Leo
---

# Discount and price-override authority

Who may lower a price is a permission check on the server, never a role-slug check: deny by default, check on every request, attach permissions to roles and test the permission in code (OWASP, NIST RBAC). This is already Firstout's permission catalog rule (`AGENTS.md`, Permissions F5). Quotes broke it by testing role slugs (`quotes.py:57`, `_DISCOUNT_ROLES`). Leo asked for whichever is best practice.

- **Line discount** on any sale document needs `till.discount`. The key name is historical; it now covers every sale document. The team's discount cap (`max_till_discount_percent`) is enforced on the server for till sales, quotes, sales orders and books invoices. Going above the cap still needs `users.manage`, as at the till today.
- **Price override** (a unit price other than the resolved one) needs a new permission, `sales.price_override`, which only the owner preset holds by default. An override is a discount by another name, so it must not ride on the discount permission.
- **Presets keep today's abilities.** The warehouse preset could discount quotes by role slug, so it gains `till.discount`; it has no `till.sell`, so nothing changes at the till. Custom roles get exactly what their permissions say.
- **Kept values**: a discount or override a document already carries needs no new permission only while the line's quantity does not grow and the customer is unchanged; otherwise it is authorised again. Pricing with no staff member (a portal order) has no authority; system authority is explicit in the code, never implied by a missing user.
- **Audit**: a document keeps who applied the discount or override, and the original resolved price, where the code already records them. No new audit table.

## Considered options

Deferred until a shop asks: manager-PIN approval above the cap (Shopify POS "approval required"), and per-user caps (Lightspeed).

## Sources

- OWASP Authorization Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- NIST RBAC FAQ: https://csrc.nist.gov/projects/role-based-access-control/faqs
- Shopify POS permissions: https://help.shopify.com/en/manual/your-account/users/roles/permissions/pos-permissions
