import { describe, expect, it } from "vitest";

import { labelForNavPath } from "./nav";
import { TOUR_STEPS, stepsForUser } from "./tour-steps";

describe("firstout tour steps", () => {
  it("walks real routes, stays detailed, and can be skipped or replayed", () => {
    const ids = TOUR_STEPS.map((step) => step.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids[0]).toBe("welcome");
    expect(ids.at(-1)).toBe("replay");
    expect(TOUR_STEPS[0]?.content.toLowerCase()).toContain("skip");
    expect(TOUR_STEPS[0]?.content.toLowerCase()).toContain("escape");
    expect(TOUR_STEPS.find((step) => step.id === "replay")?.target).toBe(
      "[data-tour='header-tour']",
    );
    expect(TOUR_STEPS.find((step) => step.id === "replay")?.content.toLowerCase()).toContain(
      "profile",
    );

    for (const step of TOUR_STEPS) {
      expect(step.title.trim().length).toBeGreaterThan(2);
      expect(step.content.trim().length).toBeGreaterThan(80);
      expect(step.target.trim().length).toBeGreaterThan(0);
      if (step.route) {
        expect(labelForNavPath(step.route)).not.toBe(step.route);
      }
    }
  });

  it("includes Nia only when the user can open it", () => {
    expect(stepsForUser({ nia: false }).some((step) => step.id === "nia")).toBe(false);
    expect(stepsForUser({ nia: true }).some((step) => step.id === "nia")).toBe(true);
    expect(stepsForUser({ nia: false }).at(-1)?.id).toBe("replay");
  });
});
