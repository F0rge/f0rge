import { describe, expect, it } from "vitest";
import { customerFacingCopy, purchaseFeedback } from "./purchase-feedback";

describe("purchase feedback", () => {
  it("moves focus to an alert when a purchase action fails", () => {
    expect(purchaseFeedback("Could not add this piece", true)).toEqual({
      role: "alert",
      tabIndex: -1,
      message: "Could not add this piece",
    });
  });

  it("uses a status for a successful bag update", () => {
    expect(purchaseFeedback("Added to bag. Review your bag when ready.", false)).toEqual({
      role: "status",
      tabIndex: -1,
      message: "Added to bag. Review your bag when ready.",
    });
  });

  it("drops retired placeholder promises", () => {
    expect(customerFacingCopy("A considered addition to your living space.")).toBeNull();
    expect(customerFacingCopy("Our collection is taking shape. Explore again soon.")).toBeNull();
    expect(customerFacingCopy("Collections are taking shape.")).toBeNull();
    expect(customerFacingCopy("  ")).toBeNull();
    expect(customerFacingCopy("A dining piece milled from solid oak.")).toBe("A dining piece milled from solid oak.");
  });
});