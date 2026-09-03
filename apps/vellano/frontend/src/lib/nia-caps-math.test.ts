import { describe, expect, it } from "vitest";

import {
  effectiveNiaCap,
  formatNiaTokenCount,
  formatNiaUsageLine,
  niaRemainingTokens,
  niaUsagePercent,
  overrideDraftFromOverride,
  parseOverrideDraft,
} from "./nia-caps-math";

describe("effectiveNiaCap", () => {
  it("inherits the team default when override is null", () => {
    expect(effectiveNiaCap(null, 5_000_000)).toBe(5_000_000);
  });

  it("uses a concrete override including zero", () => {
    expect(effectiveNiaCap(1_000_000, 500_000)).toBe(1_000_000);
    expect(effectiveNiaCap(0, 500_000)).toBe(0);
  });
});

describe("niaRemainingTokens", () => {
  it("clamps at zero when used exceeds cap", () => {
    expect(niaRemainingTokens(539_343, 500_000)).toBe(0);
    expect(niaRemainingTokens(539_343, 1_000_000)).toBe(460_657);
  });
});

describe("niaUsagePercent", () => {
  it("caps at 100 and treats zero cap as empty", () => {
    expect(niaUsagePercent(539_343, 500_000)).toBe(100);
    expect(niaUsagePercent(100, 0)).toBe(0);
    expect(niaUsagePercent(250, 1_000)).toBe(25);
  });
});

describe("override drafts", () => {
  it("treats empty / inherit as null for the PATCH body", () => {
    expect(parseOverrideDraft({ value: "", inherit: true })).toBeNull();
    expect(parseOverrideDraft({ value: "  ", inherit: false })).toBeNull();
    expect(parseOverrideDraft({ value: "1000000", inherit: false })).toBe(1_000_000);
  });

  it("round-trips null override to an inherit draft", () => {
    expect(overrideDraftFromOverride(null)).toEqual({ value: "", inherit: true });
    expect(overrideDraftFromOverride(500_000)).toEqual({
      value: "500000",
      inherit: false,
    });
  });
});

describe("formatNiaUsageLine", () => {
  it("matches the summary card wording with remaining from the new cap", () => {
    const used = 539_343;
    const cap = 1_000_000;
    const remaining = niaRemainingTokens(used, cap);
    const line = formatNiaUsageLine(used, cap, remaining);
    expect(line).toContain(formatNiaTokenCount(used));
    expect(line).toContain(formatNiaTokenCount(cap));
    expect(line).toContain(formatNiaTokenCount(remaining));
    expect(line).toContain("remaining");
    expect(remaining).toBe(460_657);
  });
});
