import { beforeEach, describe, expect, it } from "vitest";

import {
  SIDE_NAV_EXPANDED_KEY,
  readSideNavExpanded,
  writeSideNavExpanded,
} from "./side-nav-preference";

class MemoryStorage {
  private readonly data = new Map<string, string>();

  getItem(key: string): string | null {
    return this.data.has(key) ? (this.data.get(key) as string) : null;
  }

  setItem(key: string, value: string): void {
    this.data.set(key, value);
  }

  removeItem(key: string): void {
    this.data.delete(key);
  }
}

beforeEach(() => {
  const session = new MemoryStorage();
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { sessionStorage: session },
  });
});

describe("side nav preference", () => {
  it("defaults to expanded when the key is missing", () => {
    expect(readSideNavExpanded()).toBe(true);
  });

  it("honours an explicit default when unset", () => {
    expect(readSideNavExpanded(false)).toBe(false);
  });

  it("persists collapsed and remount-style read stays collapsed", () => {
    writeSideNavExpanded(false);
    expect(window.sessionStorage.getItem(SIDE_NAV_EXPANDED_KEY)).toBe("0");
    expect(readSideNavExpanded()).toBe(false);
  });

  it("persists expanded and treats stored true as expanded", () => {
    writeSideNavExpanded(true);
    expect(window.sessionStorage.getItem(SIDE_NAV_EXPANDED_KEY)).toBe("1");
    expect(readSideNavExpanded()).toBe(true);
    window.sessionStorage.setItem(SIDE_NAV_EXPANDED_KEY, "true");
    expect(readSideNavExpanded()).toBe(true);
  });
});
