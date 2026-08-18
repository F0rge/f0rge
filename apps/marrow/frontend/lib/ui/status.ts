/**
 * Single source of truth for status / flag / illustration colour classes.
 * Chrome stays on semantic tokens (bg-primary, bg-card, …). Domain colour
 * for data (ok/warn/info, scales, lab flags, diet, treatment types) lives here.
 *
 * Red/terracotta (--destructive, --chart-2) is for actual negatives only —
 * never category labels or selected toggles. Diet flags are equivalent tags:
 * selected chrome is ink; small pills share one warn wash.
 *
 * Uses Tailwind classes that map to skin CSS vars (--ok, --warn, --info,
 * --chart-*, --destructive, --muted). No zinc/amber/teal/emerald palette.
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

export type CustomizeTier = 'core' | 'catalog' | 'custom'

export const tierPillClass: Record<CustomizeTier, string> = {
  core: 'bg-chart-1/30 text-foreground',
  catalog: 'bg-info/15 text-info dark:bg-info/20',
  custom: 'bg-chart-3/20 text-ok dark:text-ok',
}

export const tierBannerClass: Record<
  CustomizeTier,
  { wrapperClass: string; iconClass: string }
> = {
  core: {
    wrapperClass: 'bg-chart-1/15 border-chart-1/25',
    iconClass: 'text-foreground',
  },
  catalog: {
    wrapperClass: 'bg-info/10 border-info/20',
    iconClass: 'text-info',
  },
  custom: {
    wrapperClass: 'bg-ok/10 border-ok/20',
    iconClass: 'text-ok',
  },
}

/** Shared attention wash — diet flags are equivalent tags, not severities. */
const dietAttention = statusPill.warn

/** Diet risk flag pills (backend FLAG_VOCAB). */
export const dietFlagClass: Record<string, { label: string; className: string }> = {
  'high-histamine': { label: 'Histamine', className: dietAttention },
  'high-fodmap': { label: 'FODMAP', className: dietAttention },
  gluten: { label: 'Gluten', className: dietAttention },
  dairy: { label: 'Dairy', className: dietAttention },
}

export const dietFlagFallback = { label: '', className: statusPill.muted }

/** Histamine score 0–3 → pill. Score 3 is actual severity → destructive. */
export const histamineClass: Record<number, string> = {
  0: statusPill.ok,
  1: 'bg-chart-1/25 text-foreground',
  2: statusPill.warn,
  3: statusPill.destructive,
}

export const fodmapHighClass = statusPill.warn
export const fodmapModClass = 'bg-chart-1/20 text-foreground'
export const confirmedFreeClass = statusPill.ok

export type MarkerFlag = 'normal' | 'low' | 'high' | 'abnormal' | 'unknown'

export const labFlagClass: Record<MarkerFlag, string> = {
  normal: statusPill.muted,
  low: statusPill.info,
  high: statusPill.destructive,
  abnormal: statusPill.warn,
  unknown: statusPill.muted,
}

/** Lab *types* are categories — not severity. Blood ≠ error. */
export const labTypeClass: Record<string, string> = {
  blood: 'bg-chart-4/25 text-foreground',
  breath: statusPill.info,
  imaging: 'bg-chart-5/20 text-info',
  microbiology: statusPill.ok,
  allergy: statusPill.warn,
  comprehensive: statusPill.info,
  other: statusPill.muted,
}

/** Treatment *types* are categories — antibiotic is not an error state. */
export const treatmentTypeClass: Record<string, string> = {
  antibiotic: statusPill.info,
  antimicrobial: statusPill.warn,
  prescription: statusPill.info,
  intervention: 'bg-chart-4/25 text-foreground',
  protocol: statusPill.ok,
  other: statusPill.muted,
}

export const treatmentTimelineBarClass: Record<string, string> = {
  antibiotic: 'bg-info',
  antimicrobial: 'bg-warn',
  prescription: 'bg-info',
  intervention: 'bg-chart-4',
  protocol: 'bg-ok',
  other: 'bg-muted-foreground',
}

/** Chart stroke/fill CSS var strings for Recharts. */
export const chartStroke = {
  1: 'var(--chart-1)',
  2: 'var(--chart-2)',
  3: 'var(--chart-3)',
  4: 'var(--chart-4)',
  5: 'var(--chart-5)',
  muted: 'var(--muted-foreground)',
  ok: 'var(--ok)',
  warn: 'var(--warn)',
} as const

/** Meal thumb illustration gradients keyed by icon — chart tokens only. */
export const mealThumbBg: Record<string, string> = {
  duck: 'from-chart-1/55 to-chart-1/20',
  sandwich: 'from-chart-4/50 to-chart-1/15',
  pastry: 'from-chart-4/50 to-chart-4/15',
  fish: 'from-chart-5/45 to-chart-5/15',
  salad: 'from-chart-3/45 to-chart-3/15',
  curry: 'from-chart-1/50 to-chart-3/15',
  toast: 'from-chart-1/40 to-muted',
  soup: 'from-chart-5/30 to-muted/50',
  bowl: 'from-chart-3/25 to-muted/40',
}

/**
 * Illustration tones for chrome artifacts — mustard / forest / cobalt.
 * Rose (--chart-4) is a soft wash on category pills only; terracotta
 * (--chart-2) is Recharts series 2. Neither is used as a solid icon well
 * (both read as danger-adjacent).
 * Hue is always paired with a distinct shape (WCAG 1.4.1).
 *
 * Colour is never hashed from a title. Governance tiers own chroma:
 * core = mustard, catalog = cobalt, custom = forest (same as TierPill).
 * Chrome with no tier (nav, settings, people, notes) uses mustard only.
 */
export type ArtifactTone = 1 | 3 | 5

/** Decorative chrome — nucleus mustard. */
export const CHROME_TONE: ArtifactTone = 1

export function toneFromTier(tier: CustomizeTier): ArtifactTone {
  if (tier === 'catalog') return 5
  if (tier === 'custom') return 3
  return 1
}

/** Hub / settings icon wells — chroma fill + contrasting glyph. */
export const iconWellClass: Record<ArtifactTone, string> = {
  1: 'bg-chart-1 text-foreground',
  3: 'bg-chart-3 text-primary-foreground',
  5: 'bg-chart-5 text-primary-foreground',
}

/** Section marks — hue + shape so colour is never the only cue. */
export const sectionMarkClass: Record<ArtifactTone, string> = {
  1: 'rounded-full bg-chart-1',
  3: 'rounded-[5px] bg-chart-3',
  5: 'rounded-sm bg-chart-5',
}

export const mealThumbBgFallback = 'from-muted to-muted/50'

export const tagStatusClass: Record<string, string> = {
  pending_analysis: statusPill.warn,
  delivered: statusPill.ok,
  default: statusPill.muted,
}
