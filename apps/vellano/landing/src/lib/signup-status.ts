export type ProvisionStep = "verifying" | "database" | "migrating" | "seeding" | "ready";

export type ProvisionUi =
  | { kind: "invalid" }
  | { kind: "failed"; message: string }
  | { kind: "progress"; stage: ProvisionStep }
  | { kind: "ready"; workspaceUrl: string };

export const GENERIC_PROVISION_FAILURE =
  "We could not finish creating your workspace. Try again later.";

export const POLL_INTERVAL_MS = 2_000;
export const POLL_MAX_MS = 3 * 60 * 1_000;

const STEPS: ProvisionStep[] = ["verifying", "database", "migrating", "seeding", "ready"];

export function isTerminalSignupStatus(status: string): boolean {
  return status === "ready" || status === "failed" || status === "expired";
}

export function uiFromSignupStatus(
  status: string,
  workspaceUrl?: string | null,
  failure?: string | null,
): ProvisionUi {
  if (status === "expired") {
    return { kind: "invalid" };
  }
  if (status === "failed") {
    return { kind: "failed", message: failure?.trim() || GENERIC_PROVISION_FAILURE };
  }
  if (status === "ready") {
    if (workspaceUrl) {
      return { kind: "ready", workspaceUrl };
    }
    return { kind: "failed", message: GENERIC_PROVISION_FAILURE };
  }
  if (status === "pending_verify") {
    return { kind: "progress", stage: "verifying" };
  }
  if (status === "verified") {
    return { kind: "progress", stage: "database" };
  }
  if (status === "provisioning") {
    return { kind: "progress", stage: "migrating" };
  }
  return { kind: "progress", stage: "verifying" };
}

export function stepState(
  step: ProvisionStep,
  ui: ProvisionUi,
): "done" | "active" | "todo" {
  if (ui.kind === "ready") {
    return "done";
  }
  if (ui.kind !== "progress") {
    return "todo";
  }
  const current = STEPS.indexOf(ui.stage);
  const index = STEPS.indexOf(step);
  if (index < current) {
    return "done";
  }
  if (index === current) {
    return "active";
  }
  return "todo";
}
