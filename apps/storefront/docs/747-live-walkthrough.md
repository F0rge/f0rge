# Issue #747 live walkthrough

Performed on 2026-09-28 against disposable local Firstout and Medusa
PostgreSQL databases, Medusa Redis, Firstout API `:8003`, commerce `:9000`,
and web `:3004`. The test payment provider was enabled only in the local
Medusa process with the explicit local runtime gate. Checkout used the
published Alba chair fixture. Delivery used the disposable `qa-jhb` zone at
R175; that is test data, not a launch rate.

- A guest selected collection, entered contact details, and prepared checkout.
  The server returned the payment amount only after validating the hold,
  persisting the confirmation capability hash, and calculating the total. The
  order showed ZAR and positive included VAT; the persisted total equalled the
  payment session amount and the sum of subtotal, shipping, and tax.
- The browser closed while the payment was pending. The scheduled expiry job
  removed the expired temporary reservation. A later success callback still
  created the order and durable inventory reservation under the inventory
  lock. Database checks found one order, one order reservation, and no
  temporary hold for the cart.
- Replaying the same event ID returned a duplicate success. A distinct event
  ID for the same cart also returned duplicate success without adding another
  order or reservation. Reusing an event ID with a different outcome returned
  HTTP 409.
- A browser without the capability received HTTP 404 from private
  confirmation. The browser holding the pre-payment httpOnly capability
  restored the confirmation after closure; its response was `no-store`.
  Attempting to prepare the paid bag with a changed address returned HTTP 409,
  and the saved order retained the original checkout contact/address snapshot.
- Decline, cancellation, pending, and unknown outcomes remained visible in the
  recovery UI and did not create a paid order.
- The configured disposable Gauteng delivery test address produced a server
  total exactly R175 above the bag total before payment. With delivery zones
  unset, checkout exposes collection only.

The Playwright checkout suite ran against the live local stack. Nx affected
lint, typecheck, and test targets, plus production builds, are recorded in the
PR checks. No real payment or production service was used.
