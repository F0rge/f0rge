import { describe, expect, it } from "vitest";
import {
  clearPortalInvitation, invitationTokenFromHash, readPortalInvitation,
  rememberPortalInvitation, tradeAuthUrl, tradeReturnPath,
} from "./trade-auth";

function storage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
}

describe("trade authentication handoff", () => {
  it("never forwards an invitation capability or external destination into Clerk URLs", () => {
    for (const value of ["https://evil.example/trade/catalogue", "//evil.example/", "/\\evil.example/trade/catalogue", "/catalogue", "/trade/catalogue-extra"]) {
      expect(tradeReturnPath(value)).toBe("/trade/catalogue");
    }
    expect(tradeAuthUrl("login", "/trade/accept-invitation?token=private#token=private")).toBe("/trade/login?redirect_url=%2Ftrade%2Faccept-invitation");
    expect(tradeReturnPath("/trade/catalogue?access=private&token=private")).toBe("/trade/catalogue");
  });

  it("preserves an explicit customer workspace while dropping unrelated parameters", () => {
    const id = "4d4db1ea-a3c5-4448-9254-6b011fb6ac75";
    expect(tradeReturnPath(`/trade/catalogue?access=${id}&token=ignored`)).toBe(`/trade/catalogue?access=${id}`);
  });

  it("keeps the capability only in a bounded per-tab handoff until consumed", () => {
    const state = storage();
    const token = invitationTokenFromHash("#token=one-use-test-capability");
    expect(token).toBe("one-use-test-capability");
    rememberPortalInvitation(state, token!, 1000);
    expect(readPortalInvitation(state, 1001)).toBe(token);
    clearPortalInvitation(state);
    expect(readPortalInvitation(state, 1002)).toBeNull();
    rememberPortalInvitation(state, "another-test-capability", 2000);
    expect(readPortalInvitation(state, 2000 + 15 * 60 * 1000)).toBeNull();
  });
});
