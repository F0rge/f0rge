import { describe, expect, it } from "vitest";

import { niaInvoiceHref } from "./nia-navigation";

describe("Nia navigation", () => {
  it("builds the invoice detail route from the invoice database id", () => {
    expect(niaInvoiceHref("4f7c/unsafe id")).toBe(
      "/invoices/4f7c%2Funsafe%20id",
    );
  });
});
