import { describe, expect, it } from "vitest";

import { pageErrorText } from "@/hooks/use-page-error";

describe("pageErrorText", () => {
  const failure = new Error("Network down");

  it("prefers the action error", () => {
    expect(pageErrorText("Save failed", failure, null, "Failed to load.")).toBe("Save failed");
  });

  it("shows a load failure until that same failure is dismissed", () => {
    expect(pageErrorText(null, failure, null, "Failed to load.")).toBe("Network down");
    expect(pageErrorText(null, failure, failure, "Failed to load.")).toBeNull();
    expect(pageErrorText(null, new Error("Network down"), failure, "Failed to load.")).toBe("Network down");
  });

  it("falls back when the failure has no message", () => {
    expect(pageErrorText(null, new Error(""), null, "Failed to load.")).toBe("Failed to load.");
    expect(pageErrorText(null, null, null, "Failed to load.")).toBeNull();
  });
});
