import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

import { localIsoDate } from "./dates";

describe("localIsoDate", () => {
  beforeAll(() => {
    vi.stubEnv("TZ", "Africa/Johannesburg");
  });
  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gives the South African day just after local midnight, when UTC is still yesterday", () => {
    const justAfterMidnight = new Date("2026-11-22T22:30:00Z"); // 00:30 SAST on the 23rd
    expect(justAfterMidnight.toISOString().slice(0, 10)).toBe("2026-11-22");
    expect(localIsoDate(justAfterMidnight)).toBe("2026-11-23");
  });

  it("pads month and day", () => {
    expect(localIsoDate(new Date(2026, 0, 5, 23, 30))).toBe("2026-01-05");
  });
});
