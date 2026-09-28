import { southAfricaVatRate } from "./vat-config";

test("South African VAT uses the configured percentage and defaults to the current standard rate", () => {
  expect(southAfricaVatRate(undefined)).toBe(15);
  expect(southAfricaVatRate("15.5")).toBe(15.5);
  expect(() => southAfricaVatRate("15.555")).toThrow(/at most two decimals/i);
});
