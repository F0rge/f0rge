import { describe, expect, it } from "vitest";
import { assertLocalCheckoutEnvironment } from "./local-checkout-environment";

const local = {
  STOREFRONT_LOCAL_CHECKOUT_QA: "true",
  DATABASE_URL: "postgres://qa:fixture@127.0.0.1:15434/daskasas_checkout_fixture",
};

describe("live checkout target safety", () => {
  it("permits explicitly opted-in disposable loopback targets", () => {
    expect(() => assertLocalCheckoutEnvironment(local)).not.toThrow();
  });

  it("requires deliberate opt-in before any checkout write", () => {
    expect(() => assertLocalCheckoutEnvironment({ ...local, STOREFRONT_LOCAL_CHECKOUT_QA: undefined })).toThrow("requires STOREFRONT_LOCAL_CHECKOUT_QA");
  });

  it.each([
    ["PLAYWRIGHT_BASE_URL", "https://shop.example.com"],
    ["MEDUSA_BACKEND_URL", "https://commerce.example.com"],
    ["DATABASE_URL", "postgres://qa:fixture@db.example.com/daskasas_checkout_fixture"],
    ["PLAYWRIGHT_BASE_URL", "http://127.0.0.1.example.com"],
  ])("rejects remote or lookalike %s targets", (name, value) => {
    expect(() => assertLocalCheckoutEnvironment({ ...local, [name]: value })).toThrow("non-loopback");
  });

  it.each(["", "postgres://qa:fixture@127.0.0.1/production", "postgres://qa:fixture@127.0.0.1/storefront"])(
    "rejects missing or unrelated local databases", (DATABASE_URL) => {
      expect(() => assertLocalCheckoutEnvironment({ ...local, DATABASE_URL })).toThrow();
    },
  );

  it.each(["?host=remote.example", "?hostaddr=203.0.113.10", "?service=production", "#override"])(
    "rejects database connection overrides %s", (suffix) => {
      expect(() => assertLocalCheckoutEnvironment({ ...local, DATABASE_URL: local.DATABASE_URL + suffix })).toThrow("query parameters or fragments");
    },
  );
});
