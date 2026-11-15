import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getMobileScanServerSnapshot,
  getMobileScanSnapshot,
  subscribeMobileScan,
  supportsMobileScan,
  type MobileScanCapabilities,
} from "./mobile-scan";

const desktop: MobileScanCapabilities = {
  coarsePointer: false,
  touchPoints: 0,
  userAgent:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145 Safari/537.36",
  platform: "Win32",
  mobile: false,
};
afterEach(() => vi.unstubAllGlobals());

describe("mobile camera scan affordance", () => {
  it.each([
    [
      "Android phone",
      {
        userAgent: "Mozilla/5.0 (Linux; Android 15) Mobile",
        platform: "Linux armv8l",
      },
    ],
    [
      "Android tablet",
      {
        userAgent: "Mozilla/5.0 (Linux; Android 15; Tablet) Chrome/145",
        platform: "Linux armv8l",
      },
    ],
    [
      "iPhone",
      {
        userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0) Mobile",
        platform: "iPhone",
      },
    ],
    [
      "iPad",
      { userAgent: "Mozilla/5.0 (iPad; CPU OS 18_0) Mobile", platform: "iPad" },
    ],
    [
      "iPad desktop identity",
      {
        userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) Safari/605",
        platform: "MacIntel",
      },
    ],
    [
      "mobile client hints",
      { userAgent: "Browser", platform: "", mobile: true },
    ],
  ])("allows a coarse touch %s", (_, device) => {
    expect(
      supportsMobileScan({
        ...desktop,
        ...device,
        coarsePointer: true,
        touchPoints: 5,
      }),
    ).toBe(true);
  });

  it("rejects desktop identity, including a coarse Windows touch laptop", () => {
    expect(supportsMobileScan(desktop)).toBe(false);
    expect(
      supportsMobileScan({ ...desktop, coarsePointer: true, touchPoints: 10 }),
    ).toBe(false);
  });

  it("requires both touch capability and a coarse primary pointer", () => {
    const phone = {
      ...desktop,
      userAgent: "iPhone Mobile",
      platform: "iPhone",
    };
    expect(
      supportsMobileScan({ ...phone, coarsePointer: true, touchPoints: 0 }),
    ).toBe(false);
    expect(
      supportsMobileScan({ ...phone, coarsePointer: false, touchPoints: 5 }),
    ).toBe(false);
  });

  it("stays false during server rendering", () => {
    vi.stubGlobal("window", undefined);
    expect(getMobileScanServerSnapshot()).toBe(false);
    expect(getMobileScanSnapshot()).toBe(false);
  });

  it("updates the snapshot after capability changes and unsubscribes cleanly", () => {
    let coarse = false;
    const addMedia = vi.fn(),
      removeMedia = vi.fn(),
      addWindow = vi.fn(),
      removeWindow = vi.fn();
    vi.stubGlobal("window", {
      matchMedia: () => ({
        get matches() {
          return coarse;
        },
        addEventListener: addMedia,
        removeEventListener: removeMedia,
      }),
      addEventListener: addWindow,
      removeEventListener: removeWindow,
    });
    vi.stubGlobal("navigator", {
      userAgent: "Android Mobile",
      platform: "Linux armv8l",
      maxTouchPoints: 5,
    });
    const listener = vi.fn();
    const unsubscribe = subscribeMobileScan(listener);
    expect(getMobileScanSnapshot()).toBe(false);
    coarse = true;
    addMedia.mock.calls[0][1]();
    expect(listener).toHaveBeenCalledOnce();
    expect(getMobileScanSnapshot()).toBe(true);
    unsubscribe();
    expect(removeMedia).toHaveBeenCalledWith("change", listener);
    expect(removeWindow).toHaveBeenCalledWith("resize", listener);
  });
});
