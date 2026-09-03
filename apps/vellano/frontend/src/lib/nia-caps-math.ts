/** Pure helpers for Nia monthly token cap display and override drafts. */

export type NiaOverrideDraft = {
  value: string;
  inherit: boolean;
};

export function formatNiaTokenCount(value: number): string {
  return value.toLocaleString("en-ZA");
}

export function niaRemainingTokens(used: number, cap: number): number {
  return Math.max(cap - used, 0);
}

export function niaUsagePercent(used: number, cap: number): number {
  if (cap <= 0) {
    return 0;
  }
  return Math.min(100, (used / cap) * 100);
}

/** Effective cap: per-user override when set, otherwise team default. */
export function effectiveNiaCap(
  override: number | null | undefined,
  teamDefaultCap: number,
): number {
  if (override === null || override === undefined) {
    return teamDefaultCap;
  }
  return override;
}

export function overrideDraftFromOverride(override: number | null): NiaOverrideDraft {
  if (override === null) {
    return { value: "", inherit: true };
  }
  return { value: String(override), inherit: false };
}

/** Empty / inherit drafts serialize as null (inherit team default). */
export function parseOverrideDraft(draft: NiaOverrideDraft): number | null {
  if (draft.inherit || draft.value.trim() === "") {
    return null;
  }
  const parsed = Number(draft.value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return null;
  }
  return Math.trunc(parsed);
}

export function formatNiaUsageLine(used: number, cap: number, remaining: number): string {
  return `${formatNiaTokenCount(used)} used of ${formatNiaTokenCount(cap)} cap (${formatNiaTokenCount(remaining)} remaining)`;
}
