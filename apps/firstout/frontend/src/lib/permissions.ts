export const PERMISSION_CATALOG = [
  "users.manage",
  "settings.mutate",
  "catalogue.mutate",
  "po.raise",
  "stock.receive",
  "stock.transfer",
  "stock.adjust",
  "stock.cost.view",
  "till.sell",
  "till.discount",
  "sales.returns",
  "sales.laybys",
  "sales.quotes",
  "sales.orders",
  "sales.refunds",
  "sales.deliveries",
  "sales.customers",
  "books.mutate",
  "books.journals",
] as const;

export type PermissionKey = (typeof PERMISSION_CATALOG)[number];

export const PERMISSION_LABELS = {
  "users.manage": "Manage staff and roles",
  "settings.mutate": "Change workspace settings",
  "catalogue.mutate": "Edit the catalogue",
  "po.raise": "Raise purchase orders",
  "stock.receive": "Receive stock",
  "stock.transfer": "Transfer stock",
  "stock.adjust": "Adjust stock",
  "stock.cost.view": "View stock costs",
  "till.sell": "Sell at the till",
  "till.discount": "Apply till discounts",
  "sales.returns": "Process returns",
  "sales.laybys": "Manage laybys",
  "sales.quotes": "Manage quotes",
  "sales.orders": "Manage orders",
  "sales.refunds": "Manage refunds",
  "sales.deliveries": "Manage deliveries",
  "sales.customers": "Manage customers",
  "books.mutate": "Manage accounting records",
  "books.journals": "Manage journals",
} satisfies Record<PermissionKey, string>;

export function permissionLabel(key: string): string {
  return Object.hasOwn(PERMISSION_LABELS, key)
    ? PERMISSION_LABELS[key as PermissionKey]
    : key.split(/[._]/).join(" ");
}

export type PermissionHolder = {
  permissions?: readonly string[];
} | null | undefined;

export function hasPermission(
  permissions: readonly string[] | undefined,
  key: string,
): boolean {
  return permissions?.includes(key) === true;
}

export function can(user: PermissionHolder, key: string): boolean {
  return hasPermission(user?.permissions, key);
}

export function canManageLocations(user: PermissionHolder): boolean {
  return can(user, "stock.receive");
}

export function canMutateCatalogue(user: PermissionHolder): boolean {
  return can(user, "catalogue.mutate");
}

export function canRaisePo(user: PermissionHolder): boolean {
  return can(user, "po.raise");
}

export function canReceive(user: PermissionHolder): boolean {
  return can(user, "stock.receive");
}

export function canTransfer(user: PermissionHolder): boolean {
  return can(user, "stock.transfer");
}

export function canReceiveTransfer(user: PermissionHolder): boolean {
  return can(user, "stock.transfer") || can(user, "till.sell");
}

export function canUseTill(user: PermissionHolder): boolean {
  return can(user, "till.sell");
}

export function canMutateBooks(user: PermissionHolder): boolean {
  return can(user, "books.mutate");
}


export function canViewCostAudit(user: PermissionHolder): boolean {
  return can(user, "stock.cost.view");
}

export function canMutateSettings(user: PermissionHolder): boolean {
  return can(user, "settings.mutate");
}

export function canManageUsers(user: PermissionHolder): boolean {
  return can(user, "users.manage");
}

export function canMutateReturns(user: PermissionHolder): boolean {
  return can(user, "sales.returns");
}

export function canMutateLaybys(user: PermissionHolder): boolean {
  return can(user, "sales.laybys");
}

export function canMutateQuotes(user: PermissionHolder): boolean {
  return can(user, "sales.quotes");
}

export function canMutateOrders(user: PermissionHolder): boolean {
  return can(user, "sales.orders");
}

export function canMutateCustomers(user: PermissionHolder): boolean {
  return can(user, "sales.customers");
}

export function canManageCustomerCredit(user: PermissionHolder): boolean {
  return can(user, "users.manage") || can(user, "po.raise");
}

export function canMutateDeliveries(user: PermissionHolder): boolean {
  return can(user, "sales.deliveries");
}

export function canMutatePicks(user: PermissionHolder): boolean {
  return can(user, "stock.transfer") || can(user, "till.sell") || can(user, "sales.deliveries");
}

