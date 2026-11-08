import { describe, expect, it } from "vitest";

import {
  partialPaymentError,
  settlementStatusLabel,
  settlementTagType,
} from "./payment-status";

describe("settlement status", () => {
  it("labels the three payment states", () => {
    expect(settlementStatusLabel("unpaid")).toBe("Unpaid");
    expect(settlementStatusLabel("partially_paid")).toBe("Partially paid");
    expect(settlementStatusLabel("paid")).toBe("Paid");
    expect(settlementTagType("partially_paid")).toBe("blue");
    expect(settlementTagType("paid")).toBe("green");
  });
});

describe("partialPaymentError", () => {
  const balance = "1150.00";

  it("accepts a smaller amount and the exact balance", () => {
    const input = { balance, documentNumber: "INV-0001" };
    expect(partialPaymentError({ ...input, amount: "400.00" })).toBeNull();
    expect(partialPaymentError({ ...input, amount: "1150" })).toBeNull();
    expect(partialPaymentError({ ...input, amount: "1150.00" })).toBeNull();
    expect(partialPaymentError({ ...input, amount: "0.01" })).toBeNull();
  });

  it("rejects zero, negative, sub-cent, and overpayments in plain English", () => {
    const input = { balance, documentNumber: "INV-0004" };
    expect(partialPaymentError({ ...input, amount: "" })).toBe("Enter a payment amount.");
    expect(partialPaymentError({ ...input, amount: "0" })).toBe(
      "Payment amount must be more than zero.",
    );
    expect(partialPaymentError({ ...input, amount: "-10.00" })).toBe(
      "Payment amount must be more than zero.",
    );
    expect(partialPaymentError({ ...input, amount: "10.001" })).toBe(
      "Payment amount must be in cents.",
    );
    expect(partialPaymentError({ ...input, amount: "1150.01" })).toBe(
      "Payment is more than the R 1,150.00 still owing on INV-0004.",
    );
  });

  it("uses the bill currency when the payment is not rand", () => {
    expect(
      partialPaymentError({
        amount: "40.01",
        balance: "40.00",
        documentNumber: "BILL-0002",
        currency: "USD",
      }),
    ).toBe("Payment is more than the USD 40.00 still owing on BILL-0002.");
  });
});
