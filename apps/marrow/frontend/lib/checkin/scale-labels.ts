/**
 * scale-labels.ts — single source of truth for rendering a stored core-scale
 * value (overall / sleep_quality / stress / neuro) as a label, color tier, or
 * summary direction on READ-ONLY surfaces (history list, history detail,
 * calendar).
 *
 * v4+ entries use a 5-point scale; legacy entries (schema_version <= 3) keep
 * their original 3-point scale (neuro's legacy domain is -1/0/1, a genuinely
 * different domain, not a relabeling). See
 * `components/checkin/cards/wellbeing-card.tsx` for the entry side of this
 * same split — the label sets here are kept byte-for-byte identical to that
 * component's `ScaleInput` options so a value renders the same word whether
 * you're editing it or reading it back. That file is out of scope to import
 * from here (check-in cards are frozen), so keep the two in sync by hand if
 * either changes.
 */

import {
  legacyScaleBadgeClass,
  legacyScaleDotClass,
  scaleBadgeClass,
  scaleDotClass,
  type ScaleTier,
} from '@/lib/ui/status'

export type CoreScaleField = 'overall' | 'sleep_quality' | 'stress' | 'neuro'

const FIVE_POINT_LABELS: Record<CoreScaleField, Record<number, string>> = {
  overall: { 1: 'Awful', 2: 'Poor', 3: 'OK', 4: 'Good', 5: 'Great' },
  sleep_quality: { 1: 'Awful', 2: 'Poor', 3: 'OK', 4: 'Good', 5: 'Great' },
  stress: { 1: 'None', 2: 'Low', 3: 'Med', 4: 'High', 5: 'Severe' },
  neuro: { 1: 'Worst', 2: 'Worse', 3: 'Base', 4: 'Better', 5: 'Best' },
}

const LEGACY_LABELS: Record<CoreScaleField, Record<number, string>> = {
  overall: { 1: 'Very Poor', 2: 'Standard', 3: 'Very Good' },
  sleep_quality: { 1: 'Poor', 2: 'OK', 3: 'Good' },
  stress: { 1: 'Low', 2: 'Medium', 3: 'High' },
  neuro: { [-1]: 'Worse', 0: 'Baseline', 1: 'Better' },
}

export function isFivePoint(schemaVersion: number): boolean {
  return schemaVersion >= 4
}

/** Label for a core-scale field's stored value, correct for its schema version. */
export function getScaleLabel(
  field: CoreScaleField,
  value: number | null,
  schemaVersion: number,
): string {
  if (value == null) return 'Not rated'
  const table = isFivePoint(schemaVersion) ? FIVE_POINT_LABELS[field] : LEGACY_LABELS[field]
  return table[value] ?? 'Unknown'
}

export type { ScaleTier }

/** Three-way good/neutral/poor split for legacy `overall` entries. */
export function getOverallTier(value: number | null, schemaVersion: number): ScaleTier {
  if (value == null) return 'neutral'
  if (isFivePoint(schemaVersion)) {
    if (value >= 4) return 'good'
    if (value === 3) return 'neutral'
    return 'poor'
  }
  if (value === 3) return 'good'
  if (value === 2) return 'neutral'
  return 'poor'
}

/** Solid dot color for calendar wellbeing indicators. */
export function getOverallDotClass(value: number | null, schemaVersion: number): string {
  if (value == null) return 'bg-transparent ring-1 ring-chart-1'
  if (isFivePoint(schemaVersion)) {
    return scaleDotClass[value] ?? 'bg-muted-foreground'
  }
  return legacyScaleDotClass[getOverallTier(value, schemaVersion)]
}

/** Soft pill color for wellbeing badges on history surfaces. */
export function getOverallBadgeClass(value: number | null, schemaVersion: number): string {
  if (value == null) return 'bg-chart-1/25 text-foreground'
  if (isFivePoint(schemaVersion)) {
    return scaleBadgeClass[value] ?? 'bg-muted text-muted-foreground'
  }
  return legacyScaleBadgeClass[getOverallTier(value, schemaVersion)]
}

export type NeuroDirection = 'worse' | 'better' | 'baseline'

/** Coarse worse/better/baseline read on `neuro`, for one-line entry summaries. */
export function getNeuroDirection(value: number, schemaVersion: number): NeuroDirection {
  if (isFivePoint(schemaVersion)) {
    if (value <= 2) return 'worse'
    if (value >= 4) return 'better'
    return 'baseline'
  }
  if (value === -1) return 'worse'
  if (value === 1) return 'better'
  return 'baseline'
}
