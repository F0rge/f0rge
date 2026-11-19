import { describe, expect, it } from "vitest";
import { availableStaffPlaces, invitationRoleSummary, staffInvitationFor } from "./staff-administration";

describe("staff invitation role preview", () => {
  it("describes actual granted permissions, including custom roles", () => {
    expect(invitationRoleSummary({ is_owner_preset: false, permissions: ["sales.quotes", "users.manage", "sales.customers", "till.sell"] }))
      .toBe("Manage staff and roles · Sell at the till · Manage quotes · 1 more");
    expect(invitationRoleSummary({ is_owner_preset: false, permissions: [] }))
      .toBe("No additional permissions assigned.");
    expect(invitationRoleSummary({ is_owner_preset: true, permissions: [] }))
      .toBe("Full access to the workspace.");
  });
});

describe("staff invitation capacity", () => {
  it("deducts occupied seats and reserved invitations, clamping over-allocation", () => {
    expect(availableStaffPlaces({ active_count: 2, member_count: 3, pending_count: 1, max_members: 5 })).toBe(1);
    expect(availableStaffPlaces({ active_count: 4, member_count: 6, pending_count: 1, max_members: 5 })).toBe(0);
  });
  it("matches pending invitations case-insensitively while ignoring accepted or revoked history", () => {
    const invitation = { id: "1", email: "staff@example.com", role: "buyer", status: "pending", delivery_confirmed: false };
    expect(staffInvitationFor([invitation], " Staff@EXAMPLE.com ")).toEqual(invitation);
    expect(staffInvitationFor([{ ...invitation, status: "accepted" }, { ...invitation, status: "revoked" }], invitation.email)).toBeUndefined();
  });
});
