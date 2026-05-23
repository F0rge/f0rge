/**
 * patterns.ts — pure client-side pattern detection for the Insights card.
 *
 * No React, no API calls, no side-effects. Consumed by InsightsCard in
 * frontend/components/checkin/cards/insights-card.tsx.
 *
 * Call detectPatterns() with today's entry, the last-7-days window (most-recent
 * first, NOT including today), and today's supplement keys. It returns the
 * single highest-severity Pattern that fires, or null if no rule fires.
 *
 * Rule summary:
 *   R1 (severity 2): today AND ≥2 of last 7 days had histamine_load ≥ 4
 *   R2 (severity 3): same as R1 PLUS ≥2 of eligible day-pairs show a next-day bloating bump
 *   R3 (severity 1): last 3 calendar days had sleep_quality === 3
 *   R4 (severity 1): DAO supplement today + today's load ≥ 2 + today's bloating < yesterday's
 *
 * Data note (2026-05-23 calibration against 54 real entries):
 *   - load ≥ 4 fires on ~56% of days in this dataset — R1 is expected to fire often.
 *     That's intentional; the copy is deliberately softened.
 *   - R2 requires ≥2 bloating bumps in eligible pairs within the 7-day window, which
 *     is a strict signal. It fires rarely (~1 in 44 windows observed). Keep threshold.
 *   - R3 threshold of 3 consecutive sleep==3 days is aspirational; max streak in 54 days
 *     was 2. The threshold is correct — do not lower it to manufacture signal.
 *   - R4: 'dao' supplement key is not yet in the catalog as of 2026-05-23. The rule is
 *     structurally correct; it becomes active when DAO is added to the supplement catalog.
 */

import type { Entry } from '@/lib/api/types'

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export type PatternSeverity = 1 | 2 | 3

export type Pattern = {
  kind: string
  text: string
  severity: PatternSeverity
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Returns the server-computed histamine_load for an entry, or 0 when
 * photo_signal is absent, scores are absent, or histamine_load is missing/NaN.
 */
function histamineLoad(entry: Entry): number {
  const val = entry.photo_signal?.scores?.histamine_load
  if (typeof val !== 'number' || isNaN(val)) return 0
  return val
}

// ---------------------------------------------------------------------------
// Rule predicates
// ---------------------------------------------------------------------------

/**
 * R1 predicate — HIGH-HISTAMINE STREAK (severity 2)
 *
 * Threshold:  today.histamine_load >= 4
 *             AND >= 2 of the 7 entries in last7[] also had load >= 4
 *
 * Load >= 4 is used as the "high" boundary (SIGHI scale: a single meal with
 * 2 category-2 ingredients reaches load 4). Requiring ≥2 of the previous 7
 * days adds recurrence signal — one-off high-load days are common and not
 * worth surfacing.
 *
 * Data context (54-day sample): ~56% of days have load ≥ 4, so this pattern
 * fires frequently. The copy ends with the count ("N of the last 7 evenings")
 * so the user always sees quantitative context, and the severity is 2 (watch),
 * not 3 (concern).
 */
function r1(today: Entry, last7: Entry[]): Pattern | null {
  const HIGH = 4
  const MIN_WINDOW_COUNT = 2

  if (histamineLoad(today) < HIGH) return null

  const highDaysInWindow = last7.filter((e) => histamineLoad(e) >= HIGH).length
  if (highDaysInWindow < MIN_WINDOW_COUNT) return null

  const n = highDaysInWindow
  return {
    kind: 'histamine-streak',
    text: `You've had high-histamine meals ${n} of the last 7 evenings.`,
    severity: 2,
  }
}

/**
 * R2 predicate — HIGH-HISTAMINE + NEXT-MORNING BLOATING BUMP (severity 3)
 *
 * Threshold:  All R1 conditions hold
 *             PLUS: among the day-pairs (d, d+1) in the combined window
 *             [today, ...last7] where d.load >= 4, at least 2 of those pairs
 *             had (d+1).bloating > d.bloating.
 *
 * "Day-pair" means: d is the high-load evening, d+1 is the following calendar
 * day. last7 must be ordered most-recent-first; the function pairs adjacent
 * entries. today is index -1, last7[0] is index 0, etc.
 *
 * The bump threshold (≥2 pairs) is deliberately strict: a single coincidence
 * is noise; two confirmed bumps within the 7-day window is a meaningful signal.
 *
 * Data context (54-day sample): only 1 of 44 windows reached ≥2 bumps, making
 * this a rare but high-confidence observation when it does fire.
 *
 * Copy: appends the bloating note to the R1 sentence, then adds the flagging
 * prompt. Severity 3 (concern) wins over R1's severity 2.
 */
function r2(today: Entry, last7: Entry[]): Pattern | null {
  if (!r1(today, last7)) return null

  const HIGH = 4
  const MIN_BUMPS = 2

  // Build ascending sequence: [...last7 reversed..., today]
  const ascending: Entry[] = [...last7].reverse().concat(today)

  let bumpCount = 0

  for (let i = 0; i < ascending.length - 1; i++) {
    const d = ascending[i]
    const dNext = ascending[i + 1]
    if (histamineLoad(d) >= HIGH) {
      if (dNext.bloating > d.bloating) {
        bumpCount++
      }
    }
  }

  if (bumpCount < MIN_BUMPS) return null

  const n = last7.filter((e) => histamineLoad(e) >= HIGH).length
  return {
    kind: 'histamine-bloating',
    text: `You've had high-histamine meals ${n} of the last 7 evenings. Next morning bloating ↑ each time. Worth flagging?`,
    severity: 3,
  }
}

/**
 * R3 predicate — GOOD-SLEEP STREAK (severity 1)
 *
 * Threshold:  The 3 most-recent entries in last7 (last7[0], last7[1], last7[2])
 *             all have sleep_quality === 3 (Good).
 *
 * sleep_quality scale: 1 = Poor, 2 = OK, 3 = Good.
 * We look at the 3 most-recent days in the window (not today — sleep is logged
 * for the night that just ended, so today's entry reflects last night and is
 * already included if filed). Using last7[0..2] rather than today + last7[0..1]
 * means the streak requires 3 consecutive prior nights.
 *
 * Threshold of 3 is intentionally strict. In the 54-day sample the maximum
 * consecutive sleep==3 streak was 2 days — making R3 currently dormant.
 * The threshold is kept at 3 to avoid false positives; it will fire genuinely
 * when a 3-day good-sleep run actually occurs.
 *
 * Severity 1 (informational) — positive reinforcement only.
 */
function r3(last7: Entry[]): Pattern | null {
  const STREAK_LENGTH = 3

  if (last7.length < STREAK_LENGTH) return null

  const streak = last7.slice(0, STREAK_LENGTH).every((e) => e.sleep_quality === 3)
  if (!streak) return null

  return {
    kind: 'sleep-streak',
    text: 'Sleep has been Good 3 days running — nice.',
    severity: 1,
  }
}

/**
 * R4 predicate — DAO + REDUCED BLOATING (severity 1)
 *
 * Threshold:  'dao' is in todaySupplements
 *             AND today.histamine_load >= 2 (a triggering-level meal was present)
 *             AND today.bloating < yesterday.bloating (last7[0])
 *             AND last7[0].histamine_load >= 2 (yesterday also had a load)
 *
 * This flags a potential DAO benefit: the supplement was taken on a day with
 * notable histamine load and bloating was lower than the prior day (which also
 * had load). This is correlational, not causal.
 *
 * Supplement key: 'dao'. As of 2026-05-23, DAO has not been added to the
 * supplement catalog so this rule is currently always null. It becomes active
 * once 'dao' appears as a catalog key.
 *
 * Severity 1 (informational). Copy does not claim causation.
 */
function r4(today: Entry, last7: Entry[], todaySupplements: string[]): Pattern | null {
  const DAO_KEY = 'dao'
  const MIN_LOAD = 2

  if (!todaySupplements.includes(DAO_KEY)) return null
  if (histamineLoad(today) < MIN_LOAD) return null

  const yesterday = last7[0]
  if (!yesterday) return null
  if (histamineLoad(yesterday) < MIN_LOAD) return null
  if (today.bloating >= yesterday.bloating) return null

  return {
    kind: 'dao-benefit',
    text: 'DAO before a triggering meal coincided with less bloating than yesterday.',
    severity: 1,
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Detect the single highest-severity pattern from the current check-in state.
 *
 * @param today          Today's entry, or null if the user hasn't filed one yet.
 * @param last7          Up to 7 prior entries, most-recent-first. May be shorter
 *                       if fewer than 7 days of history exist.
 * @param todaySupplements  Array of supplement catalog keys taken today
 *                          (e.g. ['dao', 'nac', 'magnesium']).
 *
 * @returns The highest-severity Pattern that fires, or null if no rule fires.
 *          When today is null, always returns null (no entry = no signal).
 *
 * Rule evaluation order: R2 (3) → R1 (2) → R3 (1) → R4 (1).
 * When R3 and R4 both fire, R3 is returned (same severity, R3 checked first).
 */
export function detectPatterns(
  today: Entry | null,
  last7: Entry[],
  todaySupplements: string[],
): Pattern | null {
  if (!today) return null

  // Severity 3 — concern
  const patR2 = r2(today, last7)
  if (patR2) return patR2

  // Severity 2 — watch
  const patR1 = r1(today, last7)
  if (patR1) return patR1

  // Severity 1 — informational
  const patR3 = r3(last7)
  if (patR3) return patR3

  const patR4 = r4(today, last7, todaySupplements)
  if (patR4) return patR4

  return null
}
