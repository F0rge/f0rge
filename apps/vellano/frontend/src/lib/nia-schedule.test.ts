import { describe, expect, it } from "vitest";

import { formatNextRun } from "./nia-schedule";

describe("formatNextRun", () => {
  it("returns an em dash when next run is missing", () => {
    expect(formatNextRun(null, "Africa/Johannesburg")).toBe("—");
  });

  it("formats a UTC instant in Johannesburg", () => {
    const label = formatNextRun("2026-09-02T06:00:00.000Z", "Africa/Johannesburg");
    expect(label).toContain("2026");
    expect(label.includes("08:00") || label.includes("8:00")).toBe(true);
  });
});
