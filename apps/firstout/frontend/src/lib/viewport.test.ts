import { describe, expect, it } from "vitest";

import { NARROW_VIEWPORT_PX, getNarrowViewportSnapshot } from "./viewport";

describe("narrow viewport", () => {
  it("treats innerWidth at the 42rem pixel cap as compact", () => {
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: {
        innerWidth: NARROW_VIEWPORT_PX,
        matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
      },
    });
    expect(getNarrowViewportSnapshot()).toBe(true);
  });

  it("stays desktop when the window is wider than 42rem", () => {
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: {
        innerWidth: NARROW_VIEWPORT_PX + 80,
        matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
      },
    });
    expect(getNarrowViewportSnapshot()).toBe(false);
  });
});
