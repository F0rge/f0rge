import { describe, expect, it } from "vitest";
import { collectorSkinAttribute, contrastRatio } from "./collector-skin";

describe("collector skin", () => {
  it("applies only the implemented oxblood and citron palette", () => {
    expect(collectorSkinAttribute("Oxblood / citron")).toBe("oxblood-citron");
    expect(collectorSkinAttribute("Forest / bone")).toBeNull();
    expect(collectorSkinAttribute(null)).toBeNull();
  });

  it("keeps the oxblood citron text pairs above the WCAG AA threshold", () => {
    expect(contrastRatio("#43282d", "#f2ebdf")).toBeCloseTo(11.22, 2);
    expect(contrastRatio("#f2ebdf", "#582d38")).toBeCloseTo(9.59, 2);
    expect(contrastRatio("#d9d891", "#582d38")).toBeCloseTo(7.68, 2);
    expect(contrastRatio("#78645c", "#f2ebdf")).toBeCloseTo(4.69, 2);
    expect(contrastRatio("#43282d", "#d9d891")).toBeCloseTo(8.98, 2);
  });
});
