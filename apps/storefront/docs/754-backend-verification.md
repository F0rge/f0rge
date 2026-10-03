# Issue #754 backend verification

This is the backend verification record for the Storefront refund workflow. All test databases and the live API database were disposable Firstout databases. No shared Firstout/Marrow database was used.

## PostgreSQL-backed ASGI/HTTP tests

The refund tests run FastAPI through HTTPX ASGI transport against PostgreSQL from the disposable Testcontainers fixture. They exercise the staff, Storefront operations, returns, invoice, and refund-event HTTP routes and assert persisted domain and accounting state.

- `test_invoiced_refund_is_bounded_by_completed_return_credit_note` creates an invoiced 1,150.00 ZAR order, rejects staff initiation before a completed accepted return, then completes a RESTOCK return and verifies a single persisted 1,150.00 ZAR credit note. Return completion changes stock from 1 to 2 once; duplicate completion and another return for the same invoice are rejected without another stock change. Post-invoice selected-line and cancel requests are rejected; amount-only requests for 600.00 and 550.00 succeed, while requests above the credit-note cap fail. Verified refund events exhaust the accepted credit-note amount and reduce `SalesOrder.amount_paid` to 0.00. Each successful amount creates one journal entry with Dr account 1200 / Cr Storefront clearing account 1150. Refund events do not change stock or cancel the invoiced order. The captured amount and original payload totals remain 1,150.00 ZAR. Duplicate provider events do not create extra journals.
- `test_cancelled_order_keeps_refund_history_readable_and_late_event_does_not_release_twice` requests a full pre-invoice cancel refund, then submits a verified success event. It verifies stock returns once, `SalesOrder.status` and handoff fulfillment status become cancelled, `amount_paid` becomes 0, and fulfillment revision increments once. GET status remains readable after cancellation. A duplicate late webhook and a separate out-of-band signed event do not return more stock or advance the fulfillment revision; the out-of-band provider success is represented separately from its ledger-review status.
- `test_books_refund_command_records_verified_partial_refund_once` exercises a 575.00 ZAR partial refund, the dispatch and provider-event HTTP routes, duplicate delivery, journal uniqueness, and a conflicting event. The conflicting event returns `binding_capture_mismatch` without a request binding and leaves the original refund's provider ID, amount, outcome, and succeeded status unchanged.
- Additional passing PostgreSQL-backed HTTP tests cover company scope and staff permission, no-accepted-return post-invoice provider observations, unmatched capture binding codes, pre-invoice invoice blocking while a refund is unresolved and invoice recovery after terminal success/failure, concurrent refund reservations across independent database sessions, and dispatch-feed starvation avoidance.

All the above refund/order cases passed in the full backend run. The full run completed with 638 passed and one failed in 514 seconds. Its only failure was the date-sensitive CRM test `test_unpaid_invoice_increases_open_invoices_zar`, whose hard-coded 2026-09-01 invoice was overdue on the 2026-10-02 run date. The test-only issue-date fixture was then changed to be relative to the current date; the isolated test passed and the complete CRM module passed all 16 tests. The full suite was not rerun after that test-only adjustment; no production behavior changed.

## Migration and running-server checks

- Alembic upgraded the disposable database on localhost:5499 through revision `059_storefront_refunds`; a subsequent `alembic current` reported `059_storefront_refunds (head)`.
- A real Uvicorn process served the synthetic database on localhost:18003 while the staff UI walkthrough used it. Backend log monitoring during that window found no HTTP 5xx response, traceback, or exception output. Detailed UI scenario outcomes belong in QA's separate `754-staff-walkthrough.md`.
- The synthetic API and UI walkthrough did not dispatch a Peach provider call or move real money. Backend tests submit trusted-machine event fixtures marked `signature_verified` to exercise the Ops contract; cryptographic provider verification belongs to the commerce boundary. These tests do not prove Peach sandbox interoperability.

## Static checks

- `ruff check app tests` passed.
- `ruff format --check app tests` passed (439 files already formatted).
- `git diff --check -- apps/firstout/backend` passed.
