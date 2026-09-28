import { expect, test } from "@playwright/test";
import { Client } from "pg";

const skuId = process.env.STOREFRONT_TEST_CHECKOUT_SKU_ID || process.env.STOREFRONT_TEST_SKU_ID;
const backendUrl = process.env.MEDUSA_BACKEND_URL || "http://127.0.0.1:9000";
const publishableKey = process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY;
const bffSecret = process.env.STOREFRONT_BFF_SECRET;

async function openHeldCheckout(page: import("@playwright/test").Page) {
  await page.goto("/product/" + skuId);
  await page.getByRole("button", { name: "Add to bag" }).click();
  await page.getByRole("link", { name: "View bag" }).click();
  await page.getByRole("button", { name: "Continue to checkout" }).click();
  await expect(page).toHaveURL(/\/checkout$/);
  await expect(page.getByRole("heading", { name: "Review your order" })).toBeVisible();
}

test("a guest collection checkout resolves after the browser closes and duplicate callbacks persist one order", async ({ browser, request, page }) => {
  test.setTimeout(150_000);
  test.skip(!skuId || !publishableKey || !bffSecret || !process.env.DATABASE_URL,
    "Set storefront test SKU, Medusa publishable key, BFF secret, and disposable Medusa DATABASE_URL for live checkout QA");
  const database = new Client({ connectionString: process.env.DATABASE_URL });
  await database.connect();
  try {
    await openHeldCheckout(page);
    await page.getByLabel("Email").fill("checkout-guest@example.com");
    await page.getByLabel("First name").fill("Checkout");
    await page.getByLabel("Last name").fill("Guest");
    await page.getByLabel("Phone").fill("+27110000000");
    await page.getByLabel("Collection", { exact: true }).check();

    const preparedResponse = page.waitForResponse((response) => response.url().includes("/api/checkout/prepare"));
    await page.getByRole("button", { name: "Review total and continue" }).click();
    const prepared = await (await preparedResponse).json() as { checkout: { session_id: string; amount: number } };
    await expect(page.getByTestId("test-payment-panel")).toBeVisible();
    await expect(page.getByTestId("checkout-total")).toContainText("R");

    const bag = await (await page.request.get("/api/bag")).json() as { id: string };
    const existingOrders = await database.query(
      "SELECT COUNT(*)::int AS count FROM order_cart WHERE cart_id = $1 AND deleted_at IS NULL", [bag.id],
    );
    expect(existingOrders.rows[0].count).toBe(0);
    const holdCreator = `storefront_hold:${bag.id}`;
    const expiry = new Date(Date.now() - 60_000).toISOString();
    const expiredHolds = await database.query(
      `UPDATE reservation_item
         SET metadata = jsonb_set(COALESCE(metadata, '{}'::jsonb), '{expires_at}', to_jsonb($2::text), true)
       WHERE created_by = $1 AND deleted_at IS NULL
       RETURNING id`, [holdCreator, expiry],
    );
    expect(expiredHolds.rowCount).toBeGreaterThan(0);
    await expect.poll(async () => {
      const remaining = await database.query(
        "SELECT COUNT(*)::int AS count FROM reservation_item WHERE created_by = $1 AND deleted_at IS NULL", [holdCreator],
      );
      return remaining.rows[0].count;
    }, { timeout: 75_000, intervals: [1_000, 2_000, 5_000] }).toBe(0);
    const sweptExpiry = await database.query(
      "SELECT COUNT(*)::int AS count FROM reservation_item WHERE created_by = $1 AND deleted_at IS NULL", [holdCreator],
    );
    expect(sweptExpiry.rows[0].count).toBe(0);
    const browserContext = page.context();
    const storageState = await browserContext.storageState();
    expect(storageState.cookies.find((cookie) => cookie.name === "collector_order_access")?.httpOnly).toBe(true);
    await page.getByRole("button", { name: "Simulate pending" }).click();
    await expect(page.getByTestId("payment-status")).toContainText("pending");
    await page.close();
    await browserContext.close();

    const eventId = "browser-closed-success-001";
    const callback = async (callbackEventId: string, outcome = "success") => await request.post(backendUrl + "/store/carts/" + bag.id + "/storefront-test-payment", {
      headers: {
        "x-publishable-api-key": publishableKey!,
        "x-storefront-bff-secret": bffSecret!,
      },
      data: { session_id: prepared.checkout.session_id, outcome, event_id: callbackEventId },
    });
    const first = await callback(eventId);
    expect(first.status()).toBe(200);
    expect((await first.json()).payment).toMatchObject({ status: "captured", duplicate: false });
    const replay = await callback(eventId);
    expect(replay.status()).toBe(200);
    expect((await replay.json()).payment).toMatchObject({ status: "captured", duplicate: true });
    const reusedEvent = await callback(eventId, "declined");
    expect(reusedEvent.status()).toBe(409);
    const distinctEventReplay = await callback("browser-closed-success-002");
    expect(distinctEventReplay.status()).toBe(200);
    expect((await distinctEventReplay.json()).payment).toMatchObject({ status: "captured", duplicate: true });

    const persistedOrders = await database.query(
      "SELECT COUNT(*)::int AS count FROM order_cart WHERE cart_id = $1 AND deleted_at IS NULL", [bag.id],
    );
    const persistedReservations = await database.query(
      `SELECT COUNT(*)::int AS count
         FROM reservation_item AS reservation
         JOIN order_item AS item ON item.item_id = reservation.line_item_id
         JOIN order_cart AS cart_link ON cart_link.order_id = item.order_id
        WHERE cart_link.cart_id = $1 AND reservation.deleted_at IS NULL`, [bag.id],
    );
    const temporaryHolds = await database.query(
      "SELECT COUNT(*)::int AS count FROM reservation_item WHERE created_by = $1 AND deleted_at IS NULL", [holdCreator],
    );
    expect(persistedOrders.rows[0].count).toBe(1);
    expect(persistedReservations.rows[0].count).toBe(1);
    expect(temporaryHolds.rows[0].count).toBe(0);

    const stranger = await browser.newContext();
    try {
      const hidden = await stranger.request.get("/api/order/confirmation");
      expect(hidden.status()).toBe(404);
    } finally { await stranger.close(); }

    const restoredContext = await browser.newContext({ storageState });
    try {
      const confirmation = await restoredContext.newPage();
      await confirmation.goto("/order/confirmation");
      await expect(confirmation.getByRole("heading", { name: "Thank you. Your order is confirmed." })).toBeVisible();
      await expect(confirmation.getByText("Private order reference")).toBeVisible();
      const changedAddress = await restoredContext.request.post("http://127.0.0.1:3004/api/checkout/prepare", {
        headers: { origin: "http://127.0.0.1:3004" },
        data: {
          email: "changed@example.com", first_name: "Changed", last_name: "Address", phone: "+27110000009",
          fulfillment_type: "collection",
        },
      });
      expect(changedAddress.status()).toBe(409);
      const privateApi = await confirmation.request.get("/api/order/confirmation");
      expect(privateApi.headers()["cache-control"]).toContain("no-store");
      const persisted = await privateApi.json() as {
        status: string;
        order: {
          currency_code: string;
          subtotal: number;
          shipping_total: number;
          tax_total: number;
          total: number;
          email: string;
          address: { first_name: string; city: string } | null;
        };
      };
      expect(persisted.status).toBe("captured");
      expect(persisted.order.currency_code).toBe("zar");
      expect(persisted.order.tax_total).toBeGreaterThan(0);
      expect(persisted.order.total).toBe(prepared.checkout.amount);
      expect(persisted.order.total).toBe(persisted.order.subtotal + persisted.order.shipping_total + persisted.order.tax_total);
      expect(persisted.order.email).toBe("checkout-guest@example.com");
      expect(persisted.order.address?.first_name).toBe("Checkout");
      expect(persisted.order.address?.city).toBe("Johannesburg");
    } finally { await restoredContext.close(); }
  } finally {
    await database.end();
  }
});

test("declined, cancelled, pending, and unknown results remain recoverable without creating an order", async ({ page }) => {
  test.skip(!skuId || !process.env.DATABASE_URL, "Set a published checkout SKU and disposable Medusa DATABASE_URL for live payment-state QA");
  const database = new Client({ connectionString: process.env.DATABASE_URL });
  await database.connect();
  try {
    await openHeldCheckout(page);
    await page.getByLabel("Email").fill("recovery-guest@example.com");
    await page.getByLabel("First name").fill("Recovery");
    await page.getByLabel("Last name").fill("Guest");
    await page.getByLabel("Phone").fill("+27110000003");
    await page.getByLabel("Collection", { exact: true }).check();
    await page.getByRole("button", { name: "Review total and continue" }).click();
    await expect(page.getByTestId("test-payment-panel")).toBeVisible();
    const bag = await (await page.request.get("/api/bag")).json() as { id: string };

    for (const [button, status] of [
      ["Simulate decline", "declined"],
      ["Simulate cancellation", "cancelled"],
      ["Simulate pending", "pending"],
      ["Simulate unknown result", "unknown"],
    ]) {
      await page.getByRole("button", { name: button }).click();
      await expect(page.getByTestId("payment-status")).toContainText(status);
      const confirmation = await page.request.get("/api/order/confirmation");
      expect((await confirmation.json()).status).toBe(status);
    }
    await page.goto("/order/confirmation");
    await expect(page.getByRole("heading", { name: "Payment result is unknown" })).toBeVisible();
    const orders = await database.query(
      "SELECT COUNT(*)::int AS count FROM order_cart WHERE cart_id = $1 AND deleted_at IS NULL", [bag.id],
    );
    expect(orders.rows[0].count).toBe(0);
  } finally {
    await database.end();
  }
});

test("a configured Gauteng delivery rate is calculated by the server before payment", async ({ page }) => {
  test.skip(!skuId || !process.env.STOREFRONT_TEST_DELIVERY_CITY || !process.env.STOREFRONT_TEST_DELIVERY_SUBURB ||
    !process.env.STOREFRONT_TEST_DELIVERY_POSTAL_CODE, "Set a disposable test Gauteng zone and published SKU for delivery QA");
  await openHeldCheckout(page);
  await page.getByLabel("Email").fill("delivery-guest@example.com");
  await page.getByLabel("First name").fill("Delivery");
  await page.getByLabel("Last name").fill("Guest");
  await page.getByLabel("Phone").fill("+27110000001");
  await page.getByLabel("Street address").fill("1 Test Street");
  await page.getByLabel("Suburb").fill(process.env.STOREFRONT_TEST_DELIVERY_SUBURB!);
  await page.getByLabel("City").fill(process.env.STOREFRONT_TEST_DELIVERY_CITY!);
  await page.getByLabel("Province").fill("Gauteng");
  await page.getByLabel("Postal code").fill(process.env.STOREFRONT_TEST_DELIVERY_POSTAL_CODE!);
  const bagBefore = await (await page.request.get("/api/bag")).json() as { total: number };
  const preparedResponse = page.waitForResponse((response) => response.url().includes("/api/checkout/prepare"));
  await page.getByRole("button", { name: "Review total and continue" }).click();
  const prepared = await (await preparedResponse).json() as { checkout: { amount: number } };
  await expect(page.getByTestId("test-payment-panel")).toBeVisible();
  const after = await page.getByTestId("checkout-total").textContent();
  expect(prepared.checkout.amount - bagBefore.total).toBe(175);
  expect(after).toContain(new Intl.NumberFormat("en-ZA", { minimumFractionDigits: 2 }).format(prepared.checkout.amount));
  await page.request.delete("/api/bag/checkout");
});
