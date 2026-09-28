import { testPaymentEnabled } from "./test-payment-config";

describe("test payment activation", () => {
  test("is disabled unless explicitly enabled", () => {
    expect(testPaymentEnabled({ NODE_ENV: "development" })).toBe(false);
    expect(testPaymentEnabled({ NODE_ENV: "development", STOREFRONT_TEST_PAYMENT_ENABLED: "false" })).toBe(false);
  });

  test("can only be enabled in explicit local and test environments", () => {
    expect(testPaymentEnabled({ NODE_ENV: "development", STOREFRONT_RUNTIME_KIND: "local", STOREFRONT_TEST_PAYMENT_ENABLED: "true" })).toBe(true);
    expect(testPaymentEnabled({ NODE_ENV: "test", STOREFRONT_RUNTIME_KIND: "test", STOREFRONT_TEST_PAYMENT_ENABLED: "true" })).toBe(true);
    expect(() => testPaymentEnabled({ NODE_ENV: "production", STOREFRONT_RUNTIME_KIND: "local", STOREFRONT_TEST_PAYMENT_ENABLED: "true" })).toThrow(/disabled on hosted/i);
    expect(() => testPaymentEnabled({ NODE_ENV: "development", STOREFRONT_RUNTIME_KIND: "local", RAILWAY_ENVIRONMENT_NAME: "production", STOREFRONT_TEST_PAYMENT_ENABLED: "true" })).toThrow(/disabled on hosted/i);
    expect(() => testPaymentEnabled({ NODE_ENV: "development", STOREFRONT_RUNTIME_KIND: "local", RAILWAY_PROJECT_ID: "project", STOREFRONT_TEST_PAYMENT_ENABLED: "true" })).toThrow(/disabled on hosted/i);
    expect(() => testPaymentEnabled({ NODE_ENV: "development", STOREFRONT_RUNTIME_KIND: "local", VERCEL_ENV: "production", STOREFRONT_TEST_PAYMENT_ENABLED: "true" })).toThrow(/disabled on hosted/i);
    expect(() => testPaymentEnabled({ NODE_ENV: "development", STOREFRONT_TEST_PAYMENT_ENABLED: "true" })).toThrow(/explicit local or test runtime/i);
    expect(() => testPaymentEnabled({ NODE_ENV: "development", STOREFRONT_RUNTIME_KIND: "local", STOREFRONT_TEST_PAYMENT_ENABLED: "true", FLY_APP_NAME: "storefront" })).toThrow(/disabled on hosted/i);
  });
});
