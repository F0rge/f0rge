import { apiFetch, ApiError, type Role } from "./api";
import type { OrganisationInvitation } from "./organisations";
import { PERMISSION_CATALOG, permissionLabel } from "./permissions";

export type StaffCapacity = {
  active_count: number;
  member_count: number;
  pending_count: number;
  max_members: number;
};

export const getStaffCapacity = () =>
  apiFetch<StaffCapacity>("/organisations/current/staff-capacity");

export function availableStaffPlaces(capacity: StaffCapacity): number {
  return Math.max(0, capacity.max_members - capacity.member_count - capacity.pending_count);
}

export const isOwnerRole = (slug: string, roles: readonly Role[]) =>
  slug === "owner" || roles.some((role) => role.slug === slug && role.is_owner_preset);

const knownPermissions = new Set<string>(PERMISSION_CATALOG);

export function invitationRoleSummary(role: Pick<Role, "is_owner_preset" | "permissions">): string {
  if (role.is_owner_preset) return "Full access to the workspace.";
  if (!role.permissions.length) return "No additional permissions assigned.";

  const grants = new Set(role.permissions);
  const ordered = [
    ...PERMISSION_CATALOG.filter((key) => grants.has(key)),
    ...role.permissions.filter((key) => !knownPermissions.has(key)),
  ];
  const visible = ordered.slice(0, 3).map(permissionLabel).join(" · ");
  return ordered.length > 3 ? visible + " · " + (ordered.length - 3) + " more" : visible;
}

export function adminError(reason: unknown, fallback: string): string {
  if (reason instanceof ApiError && typeof reason.detail === "string") return reason.detail;
  return reason instanceof Error ? reason.message : fallback;
}

export function staffInvitationFor(
  invitations: readonly OrganisationInvitation[],
  email: string,
) {
  return invitations.find((item) =>
    item.status === "pending" && item.email.toLowerCase() === email.trim().toLowerCase()
  );
}
