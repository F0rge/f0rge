/**
 * hero-stats.ts — pure computation for the 5-tile hero stats strip.
 *
 * All inputs are plain data; no React. Memoize the call in CheckinBoard.
 */

import type { Entry, Treatment } from '@/lib/api/types'
import { getTreatmentDayNum } from './treatment-day'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type TrendDir = 'up' | 'same' | 'down'

export interface OverallTile {
  label: string
  trend: TrendDir | null
  trendLabel: string | null
}

export interface SleepTile {
  label: string
  trend: TrendDir | null
  trendLabel: string | null
}

export interface GutTile {
  label: string
  trend: TrendDir | null
  trendLabel: string | null
}

export interface HistamineTile {
  load: number | null        // null = no photos today
  colorBand: 'emerald' | 'amber' | 'orange'
  highDaysInWindow: number   // of last 7 with load >= 4
}

export interface TreatmentTile {
  name: string
  dayNum: number
  totalDays: number | null
  extraCount: number
}

export interface HeroStatsData {
  overall: OverallTile
  sleep: SleepTile
  gut: GutTile
  histamine: HistamineTile
  treatment: TreatmentTile | null
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const OVERALL_LABELS: Record<number, string> = { 1: 'Very Poor', 2: 'Standard', 3: 'Very Good' }
const SLEEP_LABELS: Record<number, string> = { 1: 'Poor', 2: 'OK', 3: 'Good' }

function bloatingLabel(bloating: number): string {
  switch (bloating) {
    case 0: return 'None'
    case 1: return 'Mild bloat'
    case 2: return 'Mod. bloat'
    default: return 'Severe'
  }
}

function histamineLoad(entry: Entry): number {
  const val = entry.photo_signal?.scores?.histamine_load
  if (typeof val !== 'number' || isNaN(val)) return 0
  return val
}

function histamineColorBand(load: number): 'emerald' | 'amber' | 'orange' {
  if (load < 2) return 'emerald'
  if (load < 4) return 'amber'
  return 'orange'
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * computeHeroStats — derive all 5 hero tiles from today's entry + history.
 *
 * @param today      Current day's entry, or null if not yet filed.
 * @param last7      Previous 7 entries, most-recent-first (not including today).
 * @param treatments Active treatments for the checkin date.
 * @param checkinDate  YYYY-MM-DD string for day-number calculation.
 */
export function computeHeroStats(
  today: Entry | null,
  last7: Entry[],
  treatments: Treatment[],
  checkinDate: string,
): HeroStatsData {
  const yesterday = last7[0] ?? null

  // ── Overall tile ────────────────────────────────────────────────────────
  let overall: OverallTile
  if (!today) {
    overall = { label: '—', trend: null, trendLabel: null }
  } else {
    let trend: TrendDir | null = null
    let trendLabel: string | null = null
    if (yesterday) {
      const delta = today.overall - yesterday.overall
      trend = delta > 0 ? 'up' : delta < 0 ? 'down' : 'same'
      trendLabel = trend === 'up' ? '▲ vs yesterday' : trend === 'down' ? '▼ vs yesterday' : '= same as yest.'
    }
    overall = { label: OVERALL_LABELS[today.overall] ?? '—', trend, trendLabel }
  }

  // ── Sleep tile ──────────────────────────────────────────────────────────
  let sleep: SleepTile
  if (!today) {
    sleep = { label: '—', trend: null, trendLabel: null }
  } else {
    let trend: TrendDir | null = null
    let trendLabel: string | null = null
    if (last7.length >= 1) {
      const mean = last7.reduce((s, e) => s + e.sleep_quality, 0) / last7.length
      const delta = today.sleep_quality - mean
      trend = delta > 0.25 ? 'up' : delta < -0.25 ? 'down' : 'same'
      trendLabel = trend === 'up' ? '▲ above 7-day avg' : trend === 'down' ? '▼ below 7-day avg' : '≈ avg'
    }
    sleep = { label: SLEEP_LABELS[today.sleep_quality] ?? '—', trend, trendLabel }
  }

  // ── Gut tile ────────────────────────────────────────────────────────────
  let gut: GutTile
  if (!today) {
    gut = { label: '—', trend: null, trendLabel: null }
  } else {
    const base = bloatingLabel(today.bloating)
    const label = today.stool_status === 'abnormal' ? `Abnormal · ${base}` : base
    let trend: TrendDir | null = null
    let trendLabel: string | null = null
    if (yesterday) {
      const todayScore = today.bloating + (today.stool_status === 'abnormal' ? 1 : 0)
      const yestScore = yesterday.bloating + (yesterday.stool_status === 'abnormal' ? 1 : 0)
      if (todayScore < yestScore) { trend = 'up'; trendLabel = '▲ improved' }
      else if (todayScore > yestScore) { trend = 'down'; trendLabel = '▼ worsened' }
      else { trend = 'same'; trendLabel = '= same as yest.' }
    }
    gut = { label, trend, trendLabel }
  }

  // ── Histamine tile ──────────────────────────────────────────────────────
  const load = today ? histamineLoad(today) : null
  const hasPhotosToday = today ? (today.photos?.length ?? 0) > 0 : false
  const highDaysInWindow = last7.filter((e) => histamineLoad(e) >= 4).length
  const histamine: HistamineTile = {
    load: hasPhotosToday ? load : null,
    colorBand: load !== null ? histamineColorBand(load) : 'emerald',
    highDaysInWindow,
  }

  // ── Treatment tile ──────────────────────────────────────────────────────
  let treatment: TreatmentTile | null = null
  if (treatments.length > 0) {
    const first = treatments[0]
    const dayNum = getTreatmentDayNum(first.start_date, checkinDate)
    const totalDays = first.end_date
      ? getTreatmentDayNum(first.start_date, first.end_date)
      : null
    treatment = {
      name: first.name,
      dayNum,
      totalDays,
      extraCount: treatments.length - 1,
    }
  }

  return { overall, sleep, gut, histamine, treatment }
}
