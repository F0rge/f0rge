import { describe, expect, it } from "vitest";
import { isPublicAuthPath, missingSessionDestination } from "./auth-routes";

describe("onboarding without local membership", () => {
  it("lets pending Clerk sessions finish signup without the legacy auth redirect", () => {
    expect(isPublicAuthPath("/sign-up/verify-email-address")).toBe(true);
    expect(isPublicAuthPath("/onboarding")).toBe(true);
    expect(isPublicAuthPath("/catalogue")).toBe(false);
    expect(isPublicAuthPath("/organisation")).toBe(false);
    expect(missingSessionDestination(true)).toBe("/onboarding");
    expect(missingSessionDestination(false)).toBe("/login");
  });
  it("preserves legacy and trade login routes", () => {
    for (const path of ["/login", "/forgot-password", "/reset-password", "/trade/login", "/trade/catalogue"]) {
      expect(isPublicAuthPath(path)).toBe(true);
    }
  });
});
