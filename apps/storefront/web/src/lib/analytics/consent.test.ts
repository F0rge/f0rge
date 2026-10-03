import { describe, expect, it } from "vitest";
import { loadAnalyticsConsent, saveAnalyticsConsent, type ConsentStorage } from "./consent";

function memoryStorage(initial?: string): ConsentStorage {
  let value = initial ?? null;
  return {
    getItem: () => value,
    setItem: (_key, next) => { value = next; },
  };
}

describe("analytics consent storage", () => {
  it("defaults to no consent and recognizes only explicit choices", () => {
    expect(loadAnalyticsConsent(memoryStorage())).toBeNull();
    expect(loadAnalyticsConsent(memoryStorage("unknown"))).toBeNull();
    expect(loadAnalyticsConsent(memoryStorage("accepted"))).toBe("accepted");
    expect(loadAnalyticsConsent(memoryStorage("rejected"))).toBe("rejected");
  });

  it("persists a choice without throwing when browser storage is unavailable", () => {
    const storage = memoryStorage();
    saveAnalyticsConsent(storage, "rejected");
    expect(loadAnalyticsConsent(storage)).toBe("rejected");
    expect(() => saveAnalyticsConsent({ getItem: () => null, setItem: () => { throw new Error("blocked"); } }, "accepted")).not.toThrow();
  });
});
