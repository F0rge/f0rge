import type { AuthUser } from "./api";
import { can } from "./permissions";

export const SETTINGS_SECTIONS = [
  { id: "company", label: "Company", description: "Business identity, tax, currency and branding.", group: "Business" },
  { id: "documents", label: "Documents", description: "Numbering and formats for new documents.", group: "Business" },
  { id: "locations", label: "Locations", description: "Receiving and till defaults, sale hold time, and pick priority.", group: "Operations" },
  { id: "operations", label: "Operations", description: "Payment terms, till discount limits and purchase approvals.", group: "Operations" },
  { id: "labels", label: "Labels", description: "Printing dimensions and details for SKU and bin labels.", group: "Operations" },
] as const;

export type SettingsSection = (typeof SETTINGS_SECTIONS)[number]["id"];

export function findSettingsSection(tab: string | null) {
  return SETTINGS_SECTIONS.find(({ id }) => id === tab);
}

export const ADMIN_DESTINATIONS = {
  organisation: { href: "/organisation", label: "Organisation", description: "Business identity, staff access and operating locations." },
  settings: { href: "/settings", label: "Settings directory", description: "Find the defaults your team uses across the back office." },
  team: { href: "/users", label: "Team members", description: "Manage staff access, roles and invitations." },
  salesStaff: { href: "/sales-staff", label: "Sales staff", description: "The colleagues credited with sales, and their commission rates." },
  roles: { href: "/roles", label: "Roles & permissions", description: "Review role capabilities and manage access." },
  integrations: { href: "/settings/integrations", label: "Integrations", description: "Manage connections between your account and other tools." },
  mcp: { href: "/settings/integrations/mcp-tokens", label: "MCP tokens", description: "Manage personal tokens for connected tools." },
  audit: { href: "/audit", label: "Audit log", description: "Trace changes to financial documents and stock costs." },
  profile: { href: "/profile", label: "My profile", description: "Manage your profile, default location and sign-in details." },
} as const;

export type AdminDestination = keyof typeof ADMIN_DESTINATIONS | SettingsSection;

export const ADMIN_NAV_GROUPS: readonly { label: string; items: readonly AdminDestination[] }[] = [
  { label: "Workspace", items: ["organisation", "settings"] },
  { label: "People & access", items: ["team", "salesStaff", "roles"] },
  { label: "Business settings", items: SETTINGS_SECTIONS.map(({ id }) => id) },
  { label: "Integrations", items: ["mcp"] },
  { label: "Activity & data", items: ["audit"] },
  { label: "My account", items: ["profile"] },
];

export function adminDestination(id: AdminDestination) {
  if (id in ADMIN_DESTINATIONS) return ADMIN_DESTINATIONS[id as keyof typeof ADMIN_DESTINATIONS];
  const section = SETTINGS_SECTIONS.find((item) => item.id === id)!;
  return { href: `/settings?tab=${section.id}`, label: section.label, description: section.description };
}

export function currentAdminDestination(path: string, tab: string | null): AdminDestination | undefined {
  if (path === "/settings") return findSettingsSection(tab)?.id ?? "settings";
  return (Object.keys(ADMIN_DESTINATIONS) as (keyof typeof ADMIN_DESTINATIONS)[])
    .find((id) => path === ADMIN_DESTINATIONS[id].href);
}

type AdminIdentity = Pick<AuthUser, "role" | "permissions">;

export function canOpenAdminDestination(id: AdminDestination, user: AdminIdentity | null | undefined) {
  switch (id) {
    case "organisation":
      return user?.role === "owner" && can(user, "users.manage");
    case "team":
    case "salesStaff":
    case "roles":
      return can(user, "users.manage");
    default:
      return true;
  }
}

export function administrationHome(user: AuthUser | null | undefined) {
  return canOpenAdminDestination("organisation", user) ? "/organisation" : "/settings";
}


export function searchAdminDestinations(query: string, user?: AdminIdentity | null) {
  const text = query.trim().toLowerCase();
  if (!text || !user) return [];

  const terms = text.split(/\s+/);
  const ids = [...ADMIN_NAV_GROUPS.flatMap(({ items }) => items), "integrations"] as const;
  return ids
    .filter((id) => canOpenAdminDestination(id, user))
    .map(adminDestination)
    .filter(({ label, description }) => {
      const haystack = (label + " " + description).toLowerCase();
      return terms.every((term) => haystack.includes(term));
    })
    .sort((a, b) => Number(b.label.toLowerCase().includes(text)) - Number(a.label.toLowerCase().includes(text)));
}
