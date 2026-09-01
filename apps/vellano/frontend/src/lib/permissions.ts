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
  "sales.deliveries",
  "sales.customers",
  "books.mutate",
  "books.journals",
] as const;

export type PermissionKey = (typeof PERMISSION_CATALOG)[number];

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

export function canMutateReturns(user: PermissionHolder): boolean {
  return can(user, "sales.returns");
}

export function canMutateLaybys(user: PermissionHolder): boolean {
  return can(user, "sales.laybys");
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
