import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./api";
import { setStaffTokenGetter } from "./staff-fetch";
import {
  createOrganisation, getSignupIdentity, inviteOrganisationMember,
  organisationDestination, organisationInvitesFull, revokeOrganisationInvitation,
  suggestedOrganisationSlug, validOrganisationSlug,
} from "./organisations";

afterEach(() => { setStaffTokenGetter(null); vi.unstubAllGlobals(); });

describe("organisation addresses", () => {
  it("keeps local onboarding on the local server", () => {
    expect(organisationDestination("acme", "localhost:3003", "/organisation")).toBe("/organisation");
    expect(organisationDestination("acme", "127.0.0.1:3003")).toBe("/");
  });
  it("uses the shared host until tenant DNS is enabled", () => {
    expect(organisationDestination("acme", "firstout.co.za", "/organisation", false)).toBe("https://app.firstout.co.za/organisation");
    expect(organisationDestination("acme", "other.app.firstout.co.za", "/", false)).toBe("https://app.firstout.co.za/");
    expect(organisationDestination("acme", "app.firstout.co.za", "/", true)).toBe("https://acme.app.firstout.co.za/");
  });
  it("rejects foreign hosts, reserved names and redirect injection", () => {
    for (const slug of ["admin", "api", "../evil", "foo.attacker.com", "-acme", "ACME", ""]) {
      expect(validOrganisationSlug(slug)).toBe(false);
      expect(() => organisationDestination(slug, "app.firstout.co.za")).toThrow();
    }
    expect(() => organisationDestination("acme", "app.firstout.co.za.attacker.com")).toThrow();
  });
  it("suggests a portable short name without altering an explicit choice", () => {
    expect(suggestedOrganisationSlug("  São Paulo Furniture & Co. ")).toBe("sao-paulo-furniture-co");
    expect(suggestedOrganisationSlug("x".repeat(100))).toHaveLength(63);
  });
});

describe("staff invitations", () => {
  it("reserves the fifth place for a pending invitation", () => {
    const pending = { id: "invite_1", email: "staff@example.com", role: "buyer", status: "pending" };
    expect(organisationInvitesFull({ member_count: 4, max_members: 5 }, [pending])).toBe(true);
    expect(organisationInvitesFull({ member_count: 4, max_members: 5 }, [{ ...pending, status: "revoked" }])).toBe(false);
    expect(organisationInvitesFull({ member_count: 5, max_members: 5 }, [])).toBe(true);
  });
});

describe("organisation transport", () => {
  it("sends the fresh no-org bearer during signup and the selected local role during invitation", async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response("{}"));
    vi.stubGlobal("fetch", fetch);
    setStaffTokenGetter(vi.fn().mockResolvedValueOnce("pending-session").mockResolvedValueOnce("new-org-session").mockResolvedValueOnce("owner-session"));
    await getSignupIdentity();
    await createOrganisation({ name: "Acme", slug: "acme", location_name: "Shop" });
    await inviteOrganisationMember({ email: "staff@example.com", role: "buyer" });
    expect(fetch.mock.calls[0][0]).toBe("/api/v1/tenant-signup/me");
    expect(fetch.mock.calls[0][1].headers.get("Authorization")).toBe("Bearer pending-session");
    expect(fetch.mock.calls[1][1].headers.get("Authorization")).toBe("Bearer new-org-session");
    expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({ email: "staff@example.com", role: "buyer" });
    expect(fetch.mock.calls[2][0]).toBe("/api/v1/organisations/current/invitations");
  });
  it("surfaces a provider failure rather than claiming creation succeeded", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Organisation creation is unavailable" }), { status: 503 })));
    await expect(createOrganisation({ name: "Acme", slug: "acme", location_name: "Shop" })).rejects.toBeInstanceOf(ApiError);
  });
  it("revokes a pending invitation through the active organisation scope", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    await expect(revokeOrganisationInvitation("invite/1")).resolves.toBeUndefined();
    expect(fetch.mock.calls[0][0]).toBe("/api/v1/organisations/current/invitations/invite%2F1");
    expect(fetch.mock.calls[0][1].method).toBe("DELETE");
  });
});
