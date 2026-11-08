import { apiFetch } from "./api";
import { frontendHost, RESERVED_SLUGS } from "./tenant-host";

export const tenantSubdomainsEnabled = process.env.NEXT_PUBLIC_TENANT_SUBDOMAINS_ENABLED === "true";

export type Organisation = {
  id: string;
  name: string;
  slug: string;
  clerk_org_id: string;
  role: string;
  url: string;
};

export type CurrentOrganisation = Organisation & {
  member_count: number;
  max_members: number;
};

export type SignupIdentity = {
  clerk_user_id: string;
  email: string;
  display_name: string | null;
  organisations: Organisation[];
};

export type SignupStatus = {
  enabled: boolean;
  billing_disabled: boolean;
  billing_test_mode: boolean;
  mode: string;
  max_members: number;
};

export type CreateOrganisation = {
  name: string;
  slug: string;
  legal_name?: string;
  address?: string;
  vat_number?: string;
  location_name: string;
};

export type OrganisationInvitation = {
  id: string;
  email: string;
  role: string;
  status: string;
};

export const getSignupStatus = () => apiFetch<SignupStatus>("/tenant-signup/status");
export const getSignupIdentity = () => apiFetch<SignupIdentity>("/tenant-signup/me");
export const createOrganisation = (body: CreateOrganisation) =>
  apiFetch<Organisation>("/tenant-signup", { method: "POST", body: JSON.stringify(body) });
export const getCurrentOrganisation = () =>
  apiFetch<CurrentOrganisation>("/organisations/current");
export const getOrganisationInvitations = () =>
  apiFetch<OrganisationInvitation[]>("/organisations/current/invitations");
export const inviteOrganisationMember = (body: { email: string; role: string }) =>
  apiFetch<OrganisationInvitation>("/organisations/current/invitations", {
    method: "POST",
    body: JSON.stringify(body),
  });
export const revokeOrganisationInvitation = (id: string) =>
  apiFetch<void>(`/organisations/current/invitations/${encodeURIComponent(id)}`, { method: "DELETE" });

export function validOrganisationSlug(slug: string): boolean {
  return /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$/.test(slug) && !RESERVED_SLUGS.has(slug);
}

export function suggestedOrganisationSlug(name: string): string {
  return name.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 63).replace(/-$/, "");
}

/** The destination is derived from a validated slug, never a provider redirect URL. */
export function organisationDestination(
  slug: string,
  currentHost: string,
  path: "/" | "/organisation" = "/",
  subdomainsEnabled = tenantSubdomainsEnabled,
): string {
  if (!validOrganisationSlug(slug)) throw new Error("Invalid organisation address.");
  if (/^(localhost|127\.0\.0\.1)(:[0-9]{1,5})?$/.test(currentHost)) return path;
  if (!frontendHost(currentHost)) throw new Error("Unknown application address.");
  const host = subdomainsEnabled ? `${slug}.app.firstout.co.za` : "app.firstout.co.za";
  return `https://${host}${path}`;
}

export function organisationInvitesFull(
  organisation: Pick<CurrentOrganisation, "member_count" | "max_members">,
  invitations: OrganisationInvitation[],
): boolean {
  return organisation.member_count + invitations.filter((item) => item.status === "pending").length
    >= organisation.max_members;
}
