import { describe, expect, it } from "vitest";
import { isPublicAuthPath, missingSessionDestination } from "./auth-routes";

describe("onboarding without local membership", () => {
  it("allows active personal sessions to reach onboarding without business membership", () => {
    expect(isPublicAuthPath("/sign-up/verify-email-address")).toBe(true);
    expect(isPublicAuthPath("/onboarding")).toBe(true);
    expect(isPublicAuthPath("/catalogue")).toBe(false);
    expect(isPublicAuthPath("/organisation")).toBe(false);
    expect(missingSessionDestination(true)).toBe("/onboarding");
    expect(missingSessionDestination(false)).toBe("/clerk-login");
  });
  it("allows old URL redirects and customer Clerk flows without staff membership", () => {
    for (const path of ["/login", "/forgot-password", "/reset-password", "/trade/login", "/trade/catalogue"]) {
      expect(isPublicAuthPath(path)).toBe(true);
    }
    expect(isPublicAuthPath("/trade/accept-invitation")).toBe(true);
    expect(isPublicAuthPath("/trade/sign-up/verify-email-address")).toBe(true);
  });
});
