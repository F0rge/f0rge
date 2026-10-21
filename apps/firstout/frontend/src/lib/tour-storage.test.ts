import { describe, expect, it } from "vitest";

import {
  pageTourStorageKey,
  readPageTourCompletion,
  writePageTourCompletion,
  type TourStore,
} from "./tour-storage";

function memoryStore(): TourStore {
  const values = new Map<string, string>();
  return {
    getItem(key) {
      return values.get(key) ?? null;
    },
    setItem(key, value) {
      values.set(key, value);
    },
  };
}

describe("tour completion storage", () => {
  it("remembers each page tour separately", () => {
    const store = memoryStore();
    expect(readPageTourCompletion("owner-1", "laybys", store)).toBeNull();

    writePageTourCompletion("owner-1", "laybys", "skipped", store);
    expect(readPageTourCompletion("owner-1", "laybys", store)).toBe("skipped");
    expect(readPageTourCompletion("owner-1", "customers", store)).toBeNull();
    expect(readPageTourCompletion("till-2", "laybys", store)).toBeNull();
    expect(store.getItem(pageTourStorageKey("owner-1", "laybys"))).toBe("skipped");
    expect(pageTourStorageKey("owner-1", "laybys").startsWith("firstout-tour-v2:")).toBe(true);
  });

  it("ignores unknown stored values", () => {
    const store = memoryStore();
    store.setItem(pageTourStorageKey("owner-1", "laybys"), "later");
    expect(readPageTourCompletion("owner-1", "laybys", store)).toBeNull();
  });
});
