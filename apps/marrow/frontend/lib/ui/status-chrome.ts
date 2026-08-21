import type { CustomizeTier } from './status-domain'
import { statusPill } from './status-core'

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
