/**
 * patterns.test.ts — synthetic fixtures + assertion list for detectPatterns().
 *
 * No test runner is configured in this project's frontend (package.json has no
 * jest/vitest/mocha dependency). These tests are written as runnable assertions
 * that can be executed via:
 *
 *   cd frontend && npx tsx lib/checkin/__tests__/patterns.test.ts
 *
 * Each test case calls assert() which throws on failure and prints a pass line
 * on success. All cases are collected in CASES and run at the bottom of the file.
 *
 * When a test runner (Vitest recommended — zero-config with Next.js 15) is added
 * to the project, convert each CASE into a describe/it block. The fixtures and
 * assertions are already structured to make that mechanical.
 */

import { detectPatterns } from '../patterns'
import type { Entry } from '@/lib/api/types'

// ---------------------------------------------------------------------------
// Minimal fixture factory
// ---------------------------------------------------------------------------

/**
 * Builds a minimal Entry stub. Fields not supplied default to safe zeros/nulls.
 * Only the fields consumed by detectPatterns() need values in each test case.
 */
function makeEntry(overrides: Partial<Entry> & { date: string }): Entry {
  const { date, ...rest } = overrides
  return {
    id: 0,
    date,
    schema_version: 2,
    entry_time: null,
    period_of_day: null,
    overall: 2,
    bloating: 0,
    stool_normal: null,
    stool_type: null,
    stool_status: 'normal',
    bristol_type: null,
    joint_pain: 0,
    neuro: 0,
    sleep_quality: 2,
    stress: 2,
    diet_risk: 'normal',
    supplements: '',
    sick: false,
    hot_shower: false,
    notes: null,
    alcohol_units: null,
    caffeine_servings: null,
    symptoms_json: null,
    photos: [],
    effective_flags: [],
    photo_derived_flags: [],
    user_added_flags: [],
    // Default: no photo signal (histamine_load → 0 via histamineLoad())
    photo_signal: { flags: [], scores: { histamine_load: 0, fodmap_count: 0, gluten_count: 0, dairy_count: 0 }, sources: {} },
    created_at: '2026-01-01T00:00:00',
    updated_at: '2026-01-01T00:00:00',
    ...rest,
  }
}

/** Shorthand: entry with a specific histamine_load score. */
function withLoad(date: string, load: number, extras: Partial<Entry> = {}): Entry {
  return makeEntry({
    date,
    photo_signal: {
      flags: [],
      scores: { histamine_load: load, fodmap_count: 0, gluten_count: 0, dairy_count: 0 },
      sources: {},
    },
    ...extras,
  })
}

// ---------------------------------------------------------------------------
// Assertion helper
// ---------------------------------------------------------------------------

let _passed = 0
let _failed = 0

function assert(condition: boolean, label: string): void {
  if (condition) {
    console.log(`  PASS  ${label}`)
    _passed++
  } else {
    console.error(`  FAIL  ${label}`)
    _failed++
  }
}

function assertEqual<T>(actual: T, expected: T, label: string): void {
  const ok = JSON.stringify(actual) === JSON.stringify(expected)
  if (ok) {
    console.log(`  PASS  ${label}`)
    _passed++
  } else {
    console.error(`  FAIL  ${label}`)
    console.error(`        expected: ${JSON.stringify(expected)}`)
    console.error(`        received: ${JSON.stringify(actual)}`)
    _failed++
  }
}

// ---------------------------------------------------------------------------
// Test cases
// ---------------------------------------------------------------------------

// ── null today ──────────────────────────────────────────────────────────────

console.log('\n[null today → always null]')
;(() => {
  assert(detectPatterns(null, [], []) === null, 'null today, empty window → null')

  const window7 = Array.from({ length: 7 }, (_, i) => withLoad(`2026-05-${10 + i}`, 8))
  assert(detectPatterns(null, window7, []) === null, 'null today, high-load window → null')
})()

// ── R1: fires at threshold ───────────────────────────────────────────────────

console.log('\n[R1: high-histamine streak — severity 2]')
;(() => {
  // Today load=4 (exactly at threshold), 2 of last 7 also >= 4
  const today = withLoad('2026-05-23', 4)
  const last7: Entry[] = [
    withLoad('2026-05-22', 5),
    withLoad('2026-05-21', 1),
    withLoad('2026-05-20', 4),
    withLoad('2026-05-19', 0),
    withLoad('2026-05-18', 2),
    withLoad('2026-05-17', 0),
    withLoad('2026-05-16', 0),
  ]
  const pat = detectPatterns(today, last7, [])
  assert(pat !== null, 'R1 fires when today=4, window has 2 days >= 4')
  assertEqual(pat?.kind, 'histamine-streak', 'R1 kind = histamine-streak')
  assertEqual(pat?.severity, 2, 'R1 severity = 2')
  assert(pat?.text.includes('2 of the last 7') ?? false, 'R1 text contains count "2"')
})()

;(() => {
  // Today load=3 (below threshold) — R1 should NOT fire
  const today = withLoad('2026-05-23', 3)
  const last7 = Array.from({ length: 7 }, (_, i) => withLoad(`2026-05-${16 + i}`, 6))
  assert(
    detectPatterns(today, last7, []) === null,
    'R1 does NOT fire when today load < 4, even if window is all high',
  )
})()

;(() => {
  // Today load=5, but only 1 of last 7 is >= 4 — R1 should NOT fire
  const today = withLoad('2026-05-23', 5)
  const last7: Entry[] = [
    withLoad('2026-05-22', 5),
    withLoad('2026-05-21', 0),
    withLoad('2026-05-20', 0),
    withLoad('2026-05-19', 0),
    withLoad('2026-05-18', 1),
    withLoad('2026-05-17', 2),
    withLoad('2026-05-16', 3),
  ]
  assert(
    detectPatterns(today, last7, []) === null,
    'R1 does NOT fire when window count < 2',
  )
})()

// ── R2: bloating bump pattern supersedes R1 ──────────────────────────────────

console.log('\n[R2: bloating-bump correlation — severity 3]')
;(() => {
  // R1 conditions hold + 2 eligible pairs with next-day bloating bump
  // Ascending order needed: [oldest ... newest, today]
  // last7 is most-recent-first: [d-1, d-2, d-3, d-4, d-5, d-6, d-7]
  // Pairs evaluated in ascending: oldest first
  // Pair A: last7[6] (load=5, bloat=0) → last7[5] (bloat=1) ✓ bump
  // Pair B: last7[4] (load=4, bloat=0) → last7[3] (bloat=2) ✓ bump
  // Pair C: last7[2] (load=6, bloat=0) → last7[1] (bloat=0) ✗ no bump
  const last7: Entry[] = [
    withLoad('2026-05-22', 4, { bloating: 0 }),  // idx 0 = yesterday
    withLoad('2026-05-21', 0, { bloating: 0 }),  // idx 1 → no bump after idx 2
    withLoad('2026-05-20', 6, { bloating: 0 }),  // idx 2 = load >=4, next = idx1 bloat=0 → no bump
    withLoad('2026-05-19', 2, { bloating: 2 }),  // idx 3 = next after idx 4 load=4 → bump (0→2)
    withLoad('2026-05-18', 4, { bloating: 0 }),  // idx 4 = load >=4
    withLoad('2026-05-17', 1, { bloating: 1 }),  // idx 5 = next after idx 6 load=5 → bump (0→1)
    withLoad('2026-05-16', 5, { bloating: 0 }),  // idx 6 = load >=4
  ]
  const today = withLoad('2026-05-23', 5, { bloating: 0 })
  const pat = detectPatterns(today, last7, [])
  assert(pat !== null, 'R2 fires when R1 conditions + 2 bloating bumps')
  assertEqual(pat?.kind, 'histamine-bloating', 'R2 kind = histamine-bloating')
  assertEqual(pat?.severity, 3, 'R2 severity = 3 (supersedes R1)')
  assert(
    pat?.text.includes('Next morning bloating') ?? false,
    'R2 text includes bloating note',
  )
  assert(
    pat?.text.includes('Worth flagging?') ?? false,
    'R2 text includes flagging prompt',
  )
})()

;(() => {
  // R1 fires but only 1 bloating bump — R2 should NOT fire, R1 should be returned
  const last7: Entry[] = [
    withLoad('2026-05-22', 5, { bloating: 1 }),  // idx 0
    withLoad('2026-05-21', 0, { bloating: 1 }),  // idx 1 — next after idx 2, but idx 2 load < 4
    withLoad('2026-05-20', 3, { bloating: 0 }),  // idx 2 — load < 4, not eligible
    withLoad('2026-05-19', 2, { bloating: 2 }),  // idx 3 — next after idx 4 → bump (0→2) ✓
    withLoad('2026-05-18', 5, { bloating: 0 }),  // idx 4 — eligible, bump
    withLoad('2026-05-17', 0, { bloating: 0 }),  // idx 5
    withLoad('2026-05-16', 0, { bloating: 0 }),  // idx 6
  ]
  const today = withLoad('2026-05-23', 6, { bloating: 0 })
  const pat = detectPatterns(today, last7, [])
  assert(pat !== null, 'R1 fires when only 1 bump (R2 does not)')
  assertEqual(pat?.kind, 'histamine-streak', 'Returns R1 (histamine-streak) not R2')
  assertEqual(pat?.severity, 2, 'Severity 2, not 3')
})()

// ── R3: 3-day good-sleep streak ───────────────────────────────────────────────

console.log('\n[R3: good-sleep streak — severity 1]')
;(() => {
  // Exactly 3 days sleep==3 at the head of last7
  const last7: Entry[] = [
    makeEntry({ date: '2026-05-22', sleep_quality: 3 }),
    makeEntry({ date: '2026-05-21', sleep_quality: 3 }),
    makeEntry({ date: '2026-05-20', sleep_quality: 3 }),
    makeEntry({ date: '2026-05-19', sleep_quality: 2 }),
    makeEntry({ date: '2026-05-18', sleep_quality: 1 }),
    makeEntry({ date: '2026-05-17', sleep_quality: 2 }),
    makeEntry({ date: '2026-05-16', sleep_quality: 3 }),
  ]
  const today = makeEntry({ date: '2026-05-23', sleep_quality: 2 })
  const pat = detectPatterns(today, last7, [])
  assert(pat !== null, 'R3 fires on exact 3-day sleep==3 streak')
  assertEqual(pat?.kind, 'sleep-streak', 'R3 kind = sleep-streak')
  assertEqual(pat?.severity, 1, 'R3 severity = 1')
  assertEqual(
    pat?.text,
    'Sleep has been Good 3 days running — nice.',
    'R3 copy matches spec exactly',
  )
})()

;(() => {
  // Only 2 days sleep==3 — R3 should NOT fire
  const last7: Entry[] = [
    makeEntry({ date: '2026-05-22', sleep_quality: 3 }),
    makeEntry({ date: '2026-05-21', sleep_quality: 3 }),
    makeEntry({ date: '2026-05-20', sleep_quality: 2 }),  // breaks streak
    makeEntry({ date: '2026-05-19', sleep_quality: 3 }),
    makeEntry({ date: '2026-05-18', sleep_quality: 3 }),
    makeEntry({ date: '2026-05-17', sleep_quality: 3 }),
    makeEntry({ date: '2026-05-16', sleep_quality: 3 }),
  ]
  const today = makeEntry({ date: '2026-05-23', sleep_quality: 1 })
  assert(
    detectPatterns(today, last7, []) === null,
    'R3 does NOT fire at 2-day streak',
  )
})()

;(() => {
  // last7 has fewer than 3 entries — R3 should NOT fire
  const last7 = [
    makeEntry({ date: '2026-05-22', sleep_quality: 3 }),
    makeEntry({ date: '2026-05-21', sleep_quality: 3 }),
  ]
  const today = makeEntry({ date: '2026-05-23' })
  assert(
    detectPatterns(today, last7, []) === null,
    'R3 does NOT fire when last7 has fewer than 3 entries',
  )
})()

// ── R4: DAO + reduced bloating ────────────────────────────────────────────────

console.log('\n[R4: DAO benefit signal — severity 1]')
;(() => {
  // All conditions hold: dao in supplements, today load>=2, today bloat < yesterday bloat,
  // yesterday load>=2
  const yesterday = withLoad('2026-05-22', 3, { bloating: 2 })
  const today = withLoad('2026-05-23', 4, { bloating: 1 })
  const last7 = [yesterday]
  const pat = detectPatterns(today, last7, ['dao', 'magnesium'])
  assert(pat !== null, 'R4 fires when all conditions hold')
  assertEqual(pat?.kind, 'dao-benefit', 'R4 kind = dao-benefit')
  assertEqual(pat?.severity, 1, 'R4 severity = 1')
  assertEqual(
    pat?.text,
    'DAO before a triggering meal coincided with less bloating than yesterday.',
    'R4 copy matches spec exactly',
  )
})()

;(() => {
  // dao missing from supplements — R4 does NOT fire
  const yesterday = withLoad('2026-05-22', 3, { bloating: 2 })
  const today = withLoad('2026-05-23', 4, { bloating: 1 })
  assert(
    detectPatterns(today, [yesterday], ['magnesium', 'nac']) === null,
    'R4 does NOT fire when dao not in supplements',
  )
})()

;(() => {
  // today bloating >= yesterday bloating — R4 does NOT fire
  const yesterday = withLoad('2026-05-22', 3, { bloating: 1 })
  const today = withLoad('2026-05-23', 4, { bloating: 1 })  // equal, not less
  assert(
    detectPatterns(today, [yesterday], ['dao']) === null,
    'R4 does NOT fire when today bloating >= yesterday',
  )
})()

;(() => {
  // today load < 2 — R4 does NOT fire
  const yesterday = withLoad('2026-05-22', 3, { bloating: 2 })
  const today = withLoad('2026-05-23', 1, { bloating: 1 })
  assert(
    detectPatterns(today, [yesterday], ['dao']) === null,
    'R4 does NOT fire when today load < 2',
  )
})()

;(() => {
  // yesterday load < 2 — R4 does NOT fire
  const yesterday = withLoad('2026-05-22', 1, { bloating: 2 })
  const today = withLoad('2026-05-23', 4, { bloating: 1 })
  assert(
    detectPatterns(today, [yesterday], ['dao']) === null,
    'R4 does NOT fire when yesterday load < 2',
  )
})()

// ── No rule fires → null ──────────────────────────────────────────────────────

console.log('\n[no rule fires]')
;(() => {
  // All low histamine, poor sleep, no DAO
  const today = makeEntry({ date: '2026-05-23', sleep_quality: 1, bloating: 0 })
  const last7 = Array.from({ length: 7 }, (_, i) =>
    makeEntry({ date: `2026-05-${16 + i}`, sleep_quality: 1 }),
  )
  assert(detectPatterns(today, last7, []) === null, 'null when no rule fires')
})()

// ── Missing/null photo_signal handled gracefully ───────────────────────────────

console.log('\n[missing photo_signal edge cases]')
;(() => {
  // Entry with no photo_signal at all (treated as load=0)
  const entryNoSignal = makeEntry({ date: '2026-05-23' })
  // Force photo_signal to undefined to simulate old entries
  ;(entryNoSignal as unknown as Record<string, unknown>).photo_signal = undefined
  const last7 = Array.from({ length: 7 }, (_, i) =>
    makeEntry({ date: `2026-05-${16 + i}` }),
  )
  assert(
    detectPatterns(entryNoSignal, last7, []) === null,
    'null photo_signal treated as load=0, no R1 fire',
  )
})()

;(() => {
  // Entry with photo_signal but missing scores.histamine_load
  const entryMissingLoad = makeEntry({ date: '2026-05-23' })
  ;(entryMissingLoad as unknown as Record<string, unknown>).photo_signal = {
    flags: [],
    scores: {},
    sources: {},
  }
  const last7 = Array.from({ length: 7 }, (_, i) => withLoad(`2026-05-${16 + i}`, 6))
  assert(
    detectPatterns(entryMissingLoad, last7, []) === null,
    'missing histamine_load in scores treated as 0',
  )
})()

// ── Mixed last7 lengths ───────────────────────────────────────────────────────

console.log('\n[partial history — fewer than 7 prior entries]')
;(() => {
  // Only 1 prior entry — R1 minimum count (2) cannot be reached
  const today = withLoad('2026-05-23', 8)
  const last7 = [withLoad('2026-05-22', 8)]
  assert(
    detectPatterns(today, last7, []) === null,
    'R1 does NOT fire when only 1 prior high entry (need >= 2)',
  )
})()

;(() => {
  // Exactly 2 prior entries both >= 4 — R1 fires
  const today = withLoad('2026-05-23', 5)
  const last7 = [withLoad('2026-05-22', 6), withLoad('2026-05-21', 4)]
  const pat = detectPatterns(today, last7, [])
  assert(pat !== null, 'R1 fires with only 2 prior entries both >= 4')
  assertEqual(pat?.kind, 'histamine-streak', 'Correct kind')
})()

// ── Summary ───────────────────────────────────────────────────────────────────

console.log(`\n${'─'.repeat(50)}`)
console.log(`Results: ${_passed} passed, ${_failed} failed`)
if (_failed > 0) {
  process.exit(1)
}
