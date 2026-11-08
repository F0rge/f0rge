import { existsSync } from "node:fs";
import { testPaymentEnabled } from "./test-payment-config";

jest.mock("node:fs", () => ({
  ...jest.requireActual("node:fs"),
  existsSync: jest.fn(jest.requireActual("node:fs").existsSync),
}));

const local = {
  NODE_ENV: "development",
  HOST: "127.0.0.1",
  STOREFRONT_RUNTIME_KIND: "local",
  STOREFRONT_TEST_PAYMENT_ENABLED: "true",
  DATABASE_URL: "postgres://test:test@localhost:5434/storefront",
  REDIS_URL: "redis://localhost:6379",
  STOREFRONT_PUBLIC_URL: "http://localhost:3004",
  STORE_CORS: "http://localhost:3004",
  ADMIN_CORS: "http://localhost:9000",
  AUTH_CORS: "http://localhost:9000,http://localhost:3004",
  FIRSTOUT_OPS_URL: "http://localhost:8003/api/v1/ops-commerce/v1",
};

const originalArgv = process.argv;
beforeEach(() => {
  process.argv = [originalArgv[0], "medusa", "develop", "--host", "127.0.0.1"];
  jest.mocked(existsSync).mockImplementation(jest.requireActual("node:fs").existsSync);
});
afterEach(() => { process.argv = originalArgv; });

describe("test payment activation", () => {
  test("is disabled unless explicitly enabled", () => {
    expect(testPaymentEnabled({})).toBe(false);
    expect(testPaymentEnabled({ ...local, STOREFRONT_TEST_PAYMENT_ENABLED: "false" })).toBe(false);
  });

  test("accepts only explicitly isolated local and test services", () => {
    expect(testPaymentEnabled(local)).toBe(true);
    expect(testPaymentEnabled({ ...local, NODE_ENV: "test", STOREFRONT_RUNTIME_KIND: "test" })).toBe(true);
    expect(testPaymentEnabled({ ...local, HOST: "::1", REDIS_URL: "redis://[::1]:6379" })).toBe(true);
  });

  test.each([
    { NODE_ENV: "production" },
    { STOREFRONT_RUNTIME_KIND: "hosted" },
    { STOREFRONT_RUNTIME_KIND: undefined },
    { RAILWAY_PROJECT_ID: "hosted-project" },
    { VERCEL_ENV: "production" },
    { HOST: "0.0.0.0" },
    { HOST: undefined },
    { DATABASE_URL: "postgres://test:test@db.internal/storefront" },
    { DATABASE_URL: "postgres://localhost.evil.example/storefront" },
    { REDIS_URL: "redis://redis.internal:6379" },
    { REDIS_URL: undefined },
    { STOREFRONT_PUBLIC_URL: "https://shop.example" },
    { STOREFRONT_PUBLIC_URL: undefined },
    { STORE_CORS: "http://localhost:3004,https://shop.example" },
    { ADMIN_CORS: "*" },
    { AUTH_CORS: "" },
    { FIRSTOUT_OPS_URL: "https://api.example/ops" },
  ])("rejects hosted or incomplete evidence: %j", (overrides) => {
    expect(() => testPaymentEnabled({ ...local, ...overrides })).toThrow(/disabled on hosted/i);
  });

  test("a release artifact rejects simulation even when every environment setting claims local", () => {
    const actualExists = jest.requireActual("node:fs").existsSync;
    jest.mocked(existsSync).mockImplementation((path) => path === "/usr/local/share/daskasas/hosted-artifact" || actualExists(path));
    expect(() => testPaymentEnabled(local)).toThrow(/disabled on hosted/i);
    expect(() => testPaymentEnabled({ ...local, NODE_ENV: "test", STOREFRONT_RUNTIME_KIND: "test" })).toThrow(/disabled on hosted/i);
    expect(existsSync).toHaveBeenCalledWith("/usr/local/share/daskasas/hosted-artifact");
  });

  test.each([
    ["start"],
    ["develop"],
    ["develop", "--host", "0.0.0.0"],
    ["develop", "-H", "0.0.0.0"],
    ["develop", "--host=0.0.0.0"],
    ["develop", "--host", "127.0.0.1", "--host", "0.0.0.0"],
    ["develop", "--host", "127.0.0.1", "-H0.0.0.0"],
    ["start", "--host", "127.0.0.1", "--host=localhost"],
  ])("rejects an absent or conflicting actual CLI binding: %j", (...args) => {
    process.argv = [originalArgv[0], "medusa", ...args];
    expect(() => testPaymentEnabled(local)).toThrow(/disabled on hosted/i);
  });

  test("accepts an explicit CLI loopback binding for start, develop, and nonserver local bootstrap", () => {
    for (const args of [["start", "--host=127.0.0.1"], ["start", "--host", "127.0.0.1", "--types"], ["develop", "-H", "localhost", "--port", "9001", "--no-lint"], ["exec", "./src/scripts/bootstrap-storefront.ts"]]) {
      process.argv = [originalArgv[0], "medusa", ...args];
      expect(testPaymentEnabled(local)).toBe(true);
    }
  });
});
