import { expect, test } from "@playwright/test";

test("serves security headers on the storefront homepage", async ({ request }) => {
  const response = await request.get("/");

  expect(response.ok()).toBe(true);
  expect(response.headers()).toMatchObject({
    "strict-transport-security": "max-age=31536000",
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "x-frame-options": "DENY",
  });
});

test("keeps the Paystack return reference out of referrers", async ({ request }) => {
  const response = await request.get("/checkout/paystack-return?reference=fixture", { maxRedirects: 0 });

  expect(response.status()).toBe(303);
  expect(response.headers()["referrer-policy"]).toBe("no-referrer");
  expect(new URL(response.headers().location).pathname).toBe("/order/confirmation");
  expect(new URL(response.headers().location).search).toBe("");

  const confirmation = await request.get("/order/confirmation");
  expect(confirmation.ok()).toBe(true);
  expect(confirmation.headers()["referrer-policy"]).toBe("no-referrer");
});
