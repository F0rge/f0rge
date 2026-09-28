import { describe, expect, it } from "vitest";
import { isProductAttentionEligible, ProductAttentionAccumulator } from "./attention";

describe("product attention accumulation", () => {
  it("requires at least half visibility, a visible document, and focus", () => {
    expect(isProductAttentionEligible(0.49, "visible", true)).toBe(false);
    expect(isProductAttentionEligible(0.5, "visible", true)).toBe(true);
    expect(isProductAttentionEligible(1, "hidden", true)).toBe(false);
    expect(isProductAttentionEligible(1, "visible", false)).toBe(false);
  });

  it("counts only visible, focused intervals and caps idle time at 30 seconds", () => {
    let now = 0;
    const attention = new ProductAttentionAccumulator(() => now);
    attention.setEligible(true);
    now = 10_000;
    attention.sample();
    now = 45_000;
    attention.sample();
    expect(attention.activeMilliseconds).toBe(30_000);
  });

  it("pauses while hidden or unfocused, then resumes on qualifying activity", () => {
    let now = 0;
    const attention = new ProductAttentionAccumulator(() => now);
    attention.setEligible(true);
    now = 8_000;
    attention.setEligible(false);
    now = 20_000;
    attention.setEligible(true);
    now = 25_000;
    attention.sample();
    expect(attention.activeMilliseconds).toBe(13_000);

    now = 60_000;
    attention.sample();
    attention.noteInteraction();
    now = 65_000;
    attention.sample();
    expect(attention.activeMilliseconds).toBe(23_000);
  });

  it("returns one rounded summary and deduplicates later leave signals", () => {
    let now = 0;
    const attention = new ProductAttentionAccumulator(() => now);
    attention.setEligible(true);
    now = 2_999;
    expect(attention.finish()).toBe(2);
    expect(attention.finish()).toBeNull();
  });
});
