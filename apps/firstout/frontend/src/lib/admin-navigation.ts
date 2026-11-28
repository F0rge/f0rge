import type { AuthUser } from "./api";
import { navAccess, type NavAccess, type NavRule } from "./nav";
import { can } from "./permissions";

const SETTINGS_RULE = { actions: ["settings.mutate"] } as const satisfies NavRule;
const PEOPLE_RULE = { actions: ["users.manage"] } as const satisfies NavRule;
const CATALOGUE_LISTS_RULE = { actions: ["catalogue.mutate"] } as const satisfies NavRule;

export const SETTINGS_SECTIONS = [
  { id: "company", label: "Company", description: "Business identity, tax, currency and branding.", group: "Business", ...SETTINGS_RULE },
  { id: "documents", label: "Documents", description: "Numbering and formats for new documents.", group: "Business", ...SETTINGS_RULE },
  { id: "locations", label: "Location defaults", description: "Receiving and till defaults, sale hold time, and pick priority.", group: "Operations", ...SETTINGS_RULE },
  { id: "operations", label: "Operations", description: "Payment terms, till discount limits and purchase approvals.", group: "Operations", ...SETTINGS_RULE },
  { id: "labels", label: "Labels", description: "Printing dimensions and details for SKU and bin labels.", group: "Operations", ...SETTINGS_RULE },
] as const;

export type SettingsSection = (typeof SETTINGS_SECTIONS)[number]["id"];

export function findSettingsSection(tab: string | null) {
  return SETTINGS_SECTIONS.find(({ id }) => id === tab);
}

/** Every page of the Administration shell outside the Settings tabs, with who it shows for in the shell's navigation (see `NavRule`). */
export const ADMIN_DESTINATIONS = {
  organisation: { href: "/organisation", label: "Organisation", description: "Business identity, staff access and operating locations.", ...PEOPLE_RULE },
  settings: { href: "/settings", label: "Settings directory", description: "Find the defaults your team uses across the back office.", ...SETTINGS_RULE },
  team: { href: "/users", label: "Team members", description: "Manage staff access, roles and invitations.", ...PEOPLE_RULE },
  salesStaff: { href: "/sales-staff", label: "Sales staff", description: "The colleagues credited with sales, and their commission rates.", ...PEOPLE_RULE },
  roles: { href: "/roles", label: "Roles & permissions", description: "Review role capabilities and manage access.", ...PEOPLE_RULE },
  locationsPage: { href: "/locations", label: "Locations", description: "Showrooms and warehouses, their bins and bin labels.", actions: ["stock.receive"] },
  categories: { href: "/settings/categories", label: "Categories", description: "Catalogue categories and sub-categories, their ledger posting and shop section.", ...CATALOGUE_LISTS_RULE },
  materials: { href: "/settings/materials", label: "Materials", description: "The materials SKUs are made of, grouped by family.", ...CATALOGUE_LISTS_RULE },
  integrations: { href: "/settings/integrations", label: "Integrations", description: "Manage connections between your account and other tools.", everyone: true },
  mcp: { href: "/settings/integrations/mcp-tokens", label: "MCP tokens", description: "Manage personal tokens for connected tools.", lookup: ["catalogue.mutate", "books.mutate"] },
  audit: { href: "/audit", label: "Audit log", description: "Trace changes to financial documents and stock costs.", lookup: ["books.mutate"] },
  import: { href: "/import", label: "Import", description: "Bring in SKUs and stock on hand from CSV files, previewed before anything changes.", actions: ["catalogue.mutate"] },
  archive: { href: "/history", label: "Archive", description: "The old Cin7 records: past sales, purchases and supplier prices.", lookup: ["books.mutate", "catalogue.mutate", "po.raise"] },
  profile: { href: "/profile", label: "My profile", description: "Manage your profile, default location and sign-in details.", everyone: true },
} as const satisfies Record<string, NavRule & { href: string; label: string; description: string }>;

export type AdminDestination = keyof typeof ADMIN_DESTINATIONS | SettingsSection;

export const ADMIN_NAV_GROUPS: readonly { label: string; items: readonly AdminDestination[] }[] = [
  { label: "Workspace", items: ["organisation", "settings"] },
  { label: "People & access", items: ["team", "salesStaff", "roles"] },
  { label: "Business settings", items: ["company", "documents", "locationsPage", "locations", "operations", "labels"] },
  { label: "Catalogue lists", items: ["categories", "materials"] },
  { label: "Integrations", items: ["mcp"] },
  { label: "Activity", items: ["audit"] },
  { label: "Data", items: ["import", "archive"] },
  { label: "My account", items: ["profile"] },
];

function destinationEntry(id: AdminDestination) {
  if (id in ADMIN_DESTINATIONS) return ADMIN_DESTINATIONS[id as keyof typeof ADMIN_DESTINATIONS];
  const section = SETTINGS_SECTIONS.find((item) => item.id === id)!;
  return { ...section, href: `/settings?tab=${section.id}` };
}

export function adminDestination(id: AdminDestination): { href: string; label: string; description: string } {
  const { href, label, description } = destinationEntry(id);
  return { href, label, description };
}

const ADMIN_PATHS = new Set<string>(Object.values(ADMIN_DESTINATIONS).map(({ href }) => href));

/** The page renders inside the Administration shell. */
export function isAdminPath(pathname: string): boolean {
  return ADMIN_PATHS.has(pathname);
}

export function currentAdminDestination(path: string, tab: string | null): AdminDestination | undefined {
  if (path === "/settings") return findSettingsSection(tab)?.id ?? "settings";
  return (Object.keys(ADMIN_DESTINATIONS) as (keyof typeof ADMIN_DESTINATIONS)[])
    .find((id) => path === ADMIN_DESTINATIONS[id].href);
}

type AdminIdentity = Pick<AuthUser, "role" | "permissions">;

/** Which destinations a person may open from Administration links and search (unchanged gating, not the sidebar rule). */
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

/** The shell's navigation for this person: destinations they may open and work on or look up; empty groups disappear. */
export function adminNavGroupsFor(user: AdminIdentity | null | undefined): { label: string; items: { id: AdminDestination; access: NavAccess }[] }[] {
  return ADMIN_NAV_GROUPS.map(({ label, items }) => ({
    label,
    items: items.flatMap((id) => {
      const access = canOpenAdminDestination(id, user) ? navAccess(destinationEntry(id), user) : null;
      return access ? [{ id, access }] : [];
    }),
  })).filter((group) => group.items.length > 0);
}

/** Admin landing pages, most useful first; the link takes the first one this person sees in the shell. */
const ADMIN_HOME_ORDER: readonly AdminDestination[] = [
  "organisation", "team", "settings", "locationsPage", "categories", "audit", "archive", "import",
];

/** Where the sidebar's Admin link lands. Always falls back to My profile, which everyone sees. */
export function administrationHome(user: AdminIdentity | null | undefined) {
  const visible = new Set(adminNavGroupsFor(user).flatMap((group) => group.items.map(({ id }) => id)));
  const first = ADMIN_HOME_ORDER.find((id) => visible.has(id));
  return adminDestination(first ?? "profile").href;
}

export type AdminCrumb = { label: string; href?: string };

/** Administration breadcrumbs: Administration / [Settings / [Integrations /]] page. Empty off the shell. */
export function adminBreadcrumbs(path: string, tab: string | null, home: string): AdminCrumb[] {
  const current = currentAdminDestination(path, tab);
  if (!current) return [];
  const settingsPage = (path === "/settings" && findSettingsSection(tab)) || current === "mcp" || current === "integrations"
    || current === "categories" || current === "materials";
  return [
    { label: "Administration", href: home === path && !tab ? undefined : home },
    ...(settingsPage ? [{ label: "Settings", href: "/settings" }] : []),
    ...(current === "mcp" ? [{ label: "Integrations", href: "/settings/integrations" }] : []),
    { label: adminDestination(current).label },
  ];
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
