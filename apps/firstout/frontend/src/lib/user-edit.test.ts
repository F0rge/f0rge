import { describe, expect, it } from "vitest";
import type { User } from "./api";
import { userEditPayload } from "./user-edit";

const member: User = {
  id: "staff-id",
  email: "staff@example.com",
  display_name: "Staff member",
  role: "owner",
  is_disabled: false,
  team_id: "workspace-id",
  team: { id: "workspace-id", name: "Workspace" },
  default_location_id: "old-location",
};
const edit = {
  display_name: member.display_name,
  role: "buyer",
  default_location_id: "old-location",
};

describe("editing a member with a shared identity", () => {
  it("sends a demotion without requesting global identity changes", () => {
    expect(userEditPayload(member, edit)).toEqual({ role: "buyer" });
  });

  it("can clear the membership location without touching identity fields", () => {
    expect(userEditPayload(member, { ...edit, default_location_id: "" })).toEqual({
      role: "buyer", default_location_id: null,
    });
  });

  it("includes a changed local display preference for the server to authorise", () => {
    expect(userEditPayload(member, { ...edit, display_name: "Updated name" })).toEqual({
      role: "buyer", display_name: "Updated name",
    });
  });

  it("never forwards stale local login credentials with a membership edit", () => {
    const staleForm = { ...edit, email: "changed@example.com", password: "unused-local-password" };
    expect(userEditPayload(member, staleForm)).toEqual({ role: "buyer" });
  });
});
