import { describe, expect, it } from "vitest";

import {
  GENERIC_PROVISION_FAILURE,
  isTerminalSignupStatus,
  stepState,
  uiFromSignupStatus,
} from "./signup-status";

describe("uiFromSignupStatus", () => {
  it("maps expired to invalid", () => {
    expect(uiFromSignupStatus("expired")).toEqual({ kind: "invalid" });
  });

  it("maps failed without leaking internals", () => {
    expect(uiFromSignupStatus("failed", null, "  ")).toEqual({
      kind: "failed",
      message: GENERIC_PROVISION_FAILURE,
    });
    expect(uiFromSignupStatus("failed", null, "We could not finish creating your workspace. Try again later.")).toEqual(
      {
        kind: "failed",
        message: "We could not finish creating your workspace. Try again later.",
      },
    );
  });

  it("maps ready only when a workspace origin is present", () => {
    expect(uiFromSignupStatus("ready", "http://acme.localhost:3003")).toEqual({
      kind: "ready",
      workspaceUrl: "http://acme.localhost:3003",
    });
    expect(uiFromSignupStatus("ready")).toEqual({
      kind: "failed",
      message: GENERIC_PROVISION_FAILURE,
    });
  });

  it("maps in-flight statuses to progress steps", () => {
    expect(uiFromSignupStatus("pending_verify")).toEqual({ kind: "progress", stage: "verifying" });
    expect(uiFromSignupStatus("verified")).toEqual({ kind: "progress", stage: "database" });
    expect(uiFromSignupStatus("provisioning")).toEqual({ kind: "progress", stage: "migrating" });
  });
});

describe("isTerminalSignupStatus", () => {
  it("stops polling on ready, failed, and expired", () => {
    expect(isTerminalSignupStatus("ready")).toBe(true);
    expect(isTerminalSignupStatus("failed")).toBe(true);
    expect(isTerminalSignupStatus("expired")).toBe(true);
    expect(isTerminalSignupStatus("provisioning")).toBe(false);
  });
});

describe("stepState", () => {
  it("marks earlier steps done when migrating", () => {
    const ui = uiFromSignupStatus("provisioning");
    expect(stepState("verifying", ui)).toBe("done");
    expect(stepState("database", ui)).toBe("done");
    expect(stepState("migrating", ui)).toBe("active");
    expect(stepState("seeding", ui)).toBe("todo");
    expect(stepState("ready", ui)).toBe("todo");
  });

  it("marks every step done when ready", () => {
    const ui = uiFromSignupStatus("ready", "http://acme.localhost:3003");
    expect(stepState("verifying", ui)).toBe("done");
    expect(stepState("ready", ui)).toBe("done");
  });
});
