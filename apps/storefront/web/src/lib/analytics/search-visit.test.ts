import { afterEach, describe, expect, it, vi } from "vitest";
import { createSearchVisitGuard } from "./search-visit";

describe("search visit guard", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("sends once for a Strict Mode remount of the same results, then again after a later visit", () => {
    vi.useFakeTimers();
    const guard = createSearchVisitGuard();
    expect(guard.shouldCapture(true, "shop:all")).toBe(true);
    guard.release();
    expect(guard.shouldCapture(true, "shop:all")).toBe(false);
    guard.release();
    vi.runAllTimers();
    expect(guard.shouldCapture(true, "shop:all")).toBe(true);
  });

  it("clears immediately when consent is withdrawn", () => {
    const guard = createSearchVisitGuard();
    expect(guard.shouldCapture(true, "shop:all")).toBe(true);
    expect(guard.shouldCapture(false, "shop:all")).toBe(false);
    expect(guard.shouldCapture(true, "shop:all")).toBe(true);
  });
});
