import { describe, expect, it } from "vitest";

import { cashTenderIsShort } from "./till-tender";

describe("cashTenderIsShort", () => {
  it("refuses R1 tendered for a R1000 cash sale", () => {
    expect(cashTenderIsShort("cash", 1, 1000)).toBe(true);
  });

  it("refuses a cash tender below the VAT-inclusive total", () => {
    expect(cashTenderIsShort("cash", 1, 1150)).toBe(true);
    expect(cashTenderIsShort("cash", 1149.99, 1150)).toBe(true);
  });

  it("accepts a cash tender that covers the sale", () => {
    expect(cashTenderIsShort("cash", 1000, 1000)).toBe(false);
    expect(cashTenderIsShort("cash", 1150, 1150)).toBe(false);
    expect(cashTenderIsShort("cash", 1200, 1150)).toBe(false);
  });

  it("does not treat card, deposit, or EFT as a cash count", () => {
    expect(cashTenderIsShort("card", 1, 1000)).toBe(false);
    expect(cashTenderIsShort("deposit", 1, 1000)).toBe(false);
    expect(cashTenderIsShort("eft", 1, 1000)).toBe(false);
  });

  it("leaves an empty cash field for the till to fill with the amount due", () => {
    expect(cashTenderIsShort("cash", null, 1000)).toBe(false);
  });
});
