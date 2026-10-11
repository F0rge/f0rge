import { describe, expect, it } from "vitest";

import {
  overviewStorageKey,
  pageTourStorageKey,
  readOverviewCompletion,
  readPageTourCompletion,
  writeOverviewCompletion,
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
  it("remembers each page tour and the overview separately", () => {
    const store = memoryStore();
    expect(readPageTourCompletion("owner-1", "laybys", store)).toBeNull();
    expect(readOverviewCompletion("owner-1", store)).toBeNull();

    writePageTourCompletion("owner-1", "laybys", "skipped", store);
    expect(readPageTourCompletion("owner-1", "laybys", store)).toBe("skipped");
    expect(readPageTourCompletion("owner-1", "customers", store)).toBeNull();
    expect(readPageTourCompletion("till-2", "laybys", store)).toBeNull();
    expect(readOverviewCompletion("owner-1", store)).toBeNull();

    writeOverviewCompletion("owner-1", "completed", store);
    expect(readOverviewCompletion("owner-1", store)).toBe("completed");
    expect(store.getItem(pageTourStorageKey("owner-1", "laybys"))).toBe("skipped");
    expect(store.getItem(overviewStorageKey("owner-1"))).toBe("completed");
    expect(pageTourStorageKey("owner-1", "laybys").startsWith("firstout-tour-v2:")).toBe(true);
  });

  it("ignores unknown stored values", () => {
    const store = memoryStore();
    store.setItem(pageTourStorageKey("owner-1", "laybys"), "later");
    store.setItem(overviewStorageKey("owner-1"), "later");
    expect(readPageTourCompletion("owner-1", "laybys", store)).toBeNull();
    expect(readOverviewCompletion("owner-1", store)).toBeNull();
  });
});
