const DEFAULT_TZ = "Africa/Johannesburg";

export function formatNextRun(iso: string | null, timezone: string): string {
  if (!iso) {
    return "—";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString("en-ZA", {
    timeZone: timezone || DEFAULT_TZ,
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function scheduleToggleStateLabel(enabled: boolean): "On" | "Paused" {
  return enabled ? "On" : "Paused";
}

export function scheduleToggleLabel(name: string, enabled: boolean): string {
  return `${name} — ${scheduleToggleStateLabel(enabled)}`;
}

export function withScheduleEnabled<T extends { id: string; enabled: boolean }>(
  rows: T[],
  id: string,
  enabled: boolean,
): T[] {
  return rows.map((row) => (row.id === id ? { ...row, enabled } : row));
}

export function replaceScheduleTask<T extends { id: string }>(rows: T[], updated: T): T[] {
  return rows.map((row) => (row.id === updated.id ? updated : row));
}

export function isScheduleToggleKey(key: string): boolean {
  return key === " " || key === "Spacebar" || key === "Enter";
}

export type ScheduleRowKeyTarget = {
  id?: string;
  closest?: (selector: string) => unknown;
} | null;

function asKeyTarget(target: EventTarget | NonNullable<ScheduleRowKeyTarget>): NonNullable<ScheduleRowKeyTarget> {
  return target as NonNullable<ScheduleRowKeyTarget>;
}

function matchesClosest(target: NonNullable<ScheduleRowKeyTarget>, selector: string): boolean {
  return typeof target.closest === "function" && Boolean(target.closest(selector));
}

export function shouldHandleScheduleRowToggleKey(
  target: EventTarget | ScheduleRowKeyTarget,
  key: string,
  busy: boolean,
): boolean {
  if (busy || !isScheduleToggleKey(key)) {
    return false;
  }
  if (!target) {
    return true;
  }
  const node = asKeyTarget(target);
  if (typeof node.id === "string" && node.id.startsWith("nia-task-enabled-")) {
    return false;
  }
  if (
    matchesClosest(node, "button.cds--toggle__button") ||
    matchesClosest(node, '[role="switch"]') ||
    matchesClosest(node, ".cds--overflow-menu") ||
    matchesClosest(node, ".cds--overflow-menu-options") ||
    matchesClosest(node, '[role="menuitem"]') ||
    matchesClosest(node, "a") ||
    matchesClosest(node, "input") ||
    matchesClosest(node, "textarea") ||
    matchesClosest(node, "select")
  ) {
    return false;
  }
  return true;
}
