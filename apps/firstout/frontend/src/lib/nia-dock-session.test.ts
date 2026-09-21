import { beforeEach, describe, expect, it } from "vitest";

import {
  OPEN_STORAGE_KEY,
  THREAD_STORAGE_KEY,
  clearDockSession,
  getDockOpenSnapshot,
  readDockOpen,
  readDockThreadId,
  setDockOpen,
  writeDockOpen,
  writeDockThreadId,
} from "./nia-dock-session";

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

describe("nia dock session", () => {
  it("defaults to closed when the open key is missing", () => {
    expect(readDockOpen()).toBe(false);
  });

  it("writes open and a remount-style read returns open", () => {
    writeDockOpen(true);
    expect(window.sessionStorage.getItem(OPEN_STORAGE_KEY)).toBe("1");
    expect(readDockOpen()).toBe(true);
  });

  it("treats stored true as open", () => {
    window.sessionStorage.setItem(OPEN_STORAGE_KEY, "true");
    expect(readDockOpen()).toBe(true);
  });

  it("writes closed and a remount-style read stays closed", () => {
    writeDockOpen(true);
    writeDockOpen(false);
    expect(window.sessionStorage.getItem(OPEN_STORAGE_KEY)).toBe("0");
    expect(readDockOpen()).toBe(false);
  });

  it("persists a thread id and clears it with null", () => {
    writeDockThreadId("thread-abc");
    expect(readDockThreadId()).toBe("thread-abc");
    writeDockThreadId(null);
    expect(readDockThreadId()).toBeNull();
    expect(window.sessionStorage.getItem(THREAD_STORAGE_KEY)).toBeNull();
  });

  it("clearDockSession removes both keys", () => {
    writeDockOpen(true);
    writeDockThreadId("thread-abc");
    clearDockSession();
    expect(window.sessionStorage.getItem(OPEN_STORAGE_KEY)).toBeNull();
    expect(window.sessionStorage.getItem(THREAD_STORAGE_KEY)).toBeNull();
    expect(readDockOpen()).toBe(false);
    expect(readDockThreadId()).toBeNull();
  });
});

describe("nia dock open store", () => {
  it("setDockOpen updates snapshot and sessionStorage", () => {
    setDockOpen(true);
    expect(getDockOpenSnapshot()).toBe(true);
    expect(readDockOpen()).toBe(true);
    setDockOpen(false);
    expect(getDockOpenSnapshot()).toBe(false);
  });
});
