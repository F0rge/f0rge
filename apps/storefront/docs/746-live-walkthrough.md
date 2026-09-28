# Issue #746 live walkthrough

Performed on 2026-09-28 against disposable Firstout and Medusa PostgreSQL
databases, Medusa Redis, Firstout API `:8003`, commerce `:9000`, and web `:3004`.
The Arc sofa fixture had one free unit; the Alba chair had eleven. All changes
to stock and metadata below were local test data and were restored.

- Two independent browser contexts added the Arc sofa. Add-to-bag created two
  separate carts without reservations. Concurrent checkout-hold requests left
  one shopper with “Reserved until” and the other with “Review changes”; both
  bags retained their lines. The database had one active `reservation_item`
  for that inventory item. Cancelling the winner set `deleted_at`; a second
  cancellation left no active reservation.
- The Alba bag survived navigation and refresh. Changing quantity one to two
  changed Medusa's server total and persisted through refresh. Removing the
  line left the bag empty after refresh. Quantities 0, -1, 1.5 and 100 returned
  HTTP 400. A second shopper could not PATCH the first shopper's line ID
  (HTTP 404); their own bag was unchanged.
- A direct Medusa `GET /store/carts/:id` with the publishable key but without
  the server-only BFF credential returned HTTP 403. This was checked against
  the running server after its middleware was loaded.
- A disposable hold was given an expired timestamp in Postgres. At the next
  minute the Medusa expiry job set its `deleted_at` and the active reservation
  count returned to zero. The cart's bag remained available.
- A synthetic pending paid-commitment ID was stored in disposable variant
  metadata; the next Ops sync reduced Medusa `stocked_quantity` from 1 to 0
  without changing the source revision, with `reserved_quantity` still 0.
  After marking the applied revision newer than the source, replaying the
  older source left stock at 0. Removing the
  synthetic commitment and resyncing restored stock to 1. This tests the
  contract seam; paid-order import itself belongs to the later issue.

The full Firstout pytest suite passed (616 tests). Commerce unit tests passed
(15 tests), and the commerce and web production builds succeeded. The web
Playwright suite passed all 14 tests with the sofa, chair, group, draft,
last-unit, and local publishable-key fixtures set.
