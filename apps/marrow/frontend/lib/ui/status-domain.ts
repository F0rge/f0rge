import { statusPill } from './status-core'

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

/** Lab *types* are categories — Blood ≠ error. */
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
