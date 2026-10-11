import { describe, expect, it } from "vitest";

import {
  readTourCompletion,
  tourStorageKey,
  writeTourCompletion,
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
  it("remembers skip and completion per user", () => {
    const store = memoryStore();
    expect(readTourCompletion("owner-1", store)).toBeNull();

    writeTourCompletion("owner-1", "skipped", store);
    expect(readTourCompletion("owner-1", store)).toBe("skipped");
    expect(readTourCompletion("till-2", store)).toBeNull();

    writeTourCompletion("owner-1", "completed", store);
    expect(readTourCompletion("owner-1", store)).toBe("completed");
    expect(store.getItem(tourStorageKey("owner-1"))).toBe("completed");
  });

  it("ignores unknown stored values", () => {
    const store = memoryStore();
    store.setItem(tourStorageKey("owner-1"), "later");
    expect(readTourCompletion("owner-1", store)).toBeNull();
  });
});
