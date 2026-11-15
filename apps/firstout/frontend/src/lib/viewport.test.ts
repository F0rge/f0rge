import { describe, expect, it } from "vitest";

import { NARROW_VIEWPORT_PX, getNarrowViewportSnapshot } from "./viewport";

describe("narrow viewport", () => {
  it("treats innerWidth below Carbon’s persistent-navigation breakpoint as compact", () => {
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: {
        innerWidth: NARROW_VIEWPORT_PX,
        matchMedia: () => ({
          matches: false,
          addEventListener() {},
          removeEventListener() {},
        }),
      },
    });
    expect(getNarrowViewportSnapshot()).toBe(true);
  });

  it("stays desktop when the window is at Carbon’s persistent-navigation breakpoint", () => {
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: {
        innerWidth: NARROW_VIEWPORT_PX + 80,
        matchMedia: () => ({
          matches: false,
          addEventListener() {},
          removeEventListener() {},
        }),
      },
    });
    expect(getNarrowViewportSnapshot()).toBe(false);
  });
});

describe("Carbon tablet navigation regression", () => {
  it.each([
    [1024, true],
    [1055, true],
    [1056, false],
    [1440, false],
  ])("uses the drawer at %ipx: %s", (width, compact) => {
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: {
        innerWidth: width,
        matchMedia: () => ({
          matches: false,
          addEventListener() {},
          removeEventListener() {},
        }),
      },
    });
    expect(getNarrowViewportSnapshot()).toBe(compact);
  });
});
