import { afterEach, describe, expect, it, vi } from "vitest";
import { acceptPortalInvitation, getPortalMe, listPortalCatalogue, placePortalOrder } from "./api";
import { setStaffTokenGetter } from "./staff-fetch";

describe("Clerk customer API context", () => {
  afterEach(() => { setStaffTokenGetter(null); vi.unstubAllGlobals(); });

  it("sends a fresh Clerk token and the selected access on every customer request", async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response("{}"));
    vi.stubGlobal("fetch", fetch);
    setStaffTokenGetter(vi.fn().mockResolvedValueOnce("subject-a").mockResolvedValueOnce("subject-b").mockResolvedValueOnce("subject-b-fresh"));
    await getPortalMe("account-a");
    await listPortalCatalogue("account-b");
    await placePortalOrder("account-b", { lines: [{ sku_id: "sku-b", qty: 2 }] });
    expect(fetch.mock.calls.map((call) => call[1].headers.get("Authorization"))).toEqual(["Bearer subject-a", "Bearer subject-b", "Bearer subject-b-fresh"]);
    expect(fetch.mock.calls.map((call) => call[1].headers.get("X-Firstout-Portal-Access"))).toEqual(["account-a", "account-b", "account-b"]);
    expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({ lines: [{ sku_id: "sku-b", qty: 2 }] });
    expect(() => getPortalMe("")).toThrow("Choose a trade account first.");
  });

  it("posts the one-use invitation in the body rather than the request URL", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetch);
    setStaffTokenGetter(async () => "verified-active-customer");
    await acceptPortalInvitation("synthetic-one-use-capability");
    expect(fetch.mock.calls[0][0]).toBe("/api/v1/portal/invitations/accept");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ token: "synthetic-one-use-capability" });
  });
});
