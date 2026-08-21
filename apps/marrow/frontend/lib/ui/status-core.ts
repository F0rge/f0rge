/**
 * Status / polarity colour classes. Semantic tokens only (ok/warn/info).
 * Chrome stays on bg-primary / bg-card. See status.ts for the barrel.
 */

export const statusPill = {
  ok: 'bg-ok/20 text-ok dark:bg-ok/25 dark:text-ok',
  warn: 'bg-warn/30 text-foreground dark:bg-warn/25 dark:text-warn',
  info: 'bg-info/20 text-info dark:bg-info/25 dark:text-info',
  destructive: 'bg-destructive/20 text-destructive',
  muted: 'bg-muted text-muted-foreground',
} as const

export const statusText = {
  ok: 'text-ok',
  warn: 'text-warn',
  info: 'text-info',
  destructive: 'text-destructive',
  muted: 'text-muted-foreground',
} as const

export const statusFill = {
  ok: 'bg-ok',
  warn: 'bg-warn',
  info: 'bg-info',
  destructive: 'bg-destructive',
  muted: 'bg-muted-foreground',
} as const

/** Five-point wellbeing / core-scale solid dots (calendar) — polarity only. */
export const scaleDotClass: Record<number, string> = {
  1: 'bg-destructive',
  2: 'bg-warn',
  3: 'bg-chart-1',
  4: 'bg-chart-3',
  5: 'bg-ok',
}

/** Soft badges for five-point scales on history surfaces. */
export const scaleBadgeClass: Record<number, string> = {
  1: 'bg-destructive/15 text-destructive',
  2: 'bg-warn/15 text-warn',
  3: 'bg-chart-1/20 text-foreground',
  4: 'bg-chart-3/20 text-ok',
  5: 'bg-ok/15 text-ok',
}

export type ScaleTier = 'good' | 'neutral' | 'poor'

export const legacyScaleDotClass: Record<ScaleTier, string> = {
  poor: statusFill.destructive,
  neutral: statusFill.warn,
  good: statusFill.ok,
}

export const legacyScaleBadgeClass: Record<ScaleTier, string> = {
  poor: statusPill.destructive,
  neutral: statusPill.warn,
  good: statusPill.ok,
}
