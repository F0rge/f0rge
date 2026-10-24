import { describe, expect, it } from 'vitest'

import { shouldApplyEntryHydration } from './checkin-board-entry-sync'
import { resolveEmptyDayDefaults, type EmptyDayDefaultsInput } from './checkin-board-defaults'

const ready: EmptyDayDefaultsInput = {
  defaultsReady: true,
  defaultSupplements: 'magnesium',
  defaultSymptoms: { example_symptom: 4 },
}

/**
 * Mirrors the two effects in useCheckinBoardState for supplement and symptom
 * fields. The defaults seed runs first. The no-entry reset runs second and
 * must write resolveEmptyDayDefaults, not blanks.
 */
function supplementsAfterBoardEffects(
  input: EmptyDayDefaultsInput & {
    hasEntry: boolean
    isDirty: boolean
    supplementsTouched: boolean
    symptomsTouched: boolean
    currentSupplements: string
    currentSymptoms: Record<string, number>
    entrySupplements?: string
    entrySymptoms?: Record<string, number>
  },
) {
  let supplements = input.currentSupplements
  let symptoms = input.currentSymptoms

  const canSeed =
    !input.hasEntry &&
    !input.isDirty &&
    !input.supplementsTouched &&
    !input.symptomsTouched &&
    input.defaultsReady
  if (canSeed) {
    const seeded = resolveEmptyDayDefaults(input)
    supplements = seeded.supplements
    symptoms = seeded.symptoms
  }

  if (!shouldApplyEntryHydration(input.isDirty)) {
    return { supplements, symptoms }
  }
  if (input.hasEntry) {
    return {
      supplements: input.entrySupplements ?? '',
      symptoms: input.entrySymptoms ?? {},
    }
  }
  return resolveEmptyDayDefaults(input)
}

const untouched = {
  hasEntry: false,
  isDirty: false,
  supplementsTouched: false,
  symptomsTouched: false,
  currentSupplements: '',
  currentSymptoms: {} as Record<string, number>,
}

describe('resolveEmptyDayDefaults', () => {
  it('returns saved defaults once settings and catalogs are ready', () => {
    expect(resolveEmptyDayDefaults(ready)).toEqual({
      supplements: 'magnesium',
      symptoms: { example_symptom: 4 },
    })
  })

  it('keeps a saved severity of 0', () => {
    expect(
      resolveEmptyDayDefaults({
        ...ready,
        defaultSymptoms: { example_symptom: 0 },
      }).symptoms,
    ).toEqual({ example_symptom: 0 })
  })

  it('returns blanks until defaults are ready', () => {
    expect(
      resolveEmptyDayDefaults({
        ...ready,
        defaultsReady: false,
      }),
    ).toEqual({ supplements: '', symptoms: {} })
  })

  it('returns blanks when the saved defaults are empty', () => {
    expect(
      resolveEmptyDayDefaults({
        defaultsReady: true,
        defaultSupplements: '',
        defaultSymptoms: {},
      }),
    ).toEqual({ supplements: '', symptoms: {} })
  })
})

describe('supplements after the seed and the no-entry reset', () => {
  it('keeps cached defaults when the reset runs after the seed', () => {
    expect(
      supplementsAfterBoardEffects({
        ...ready,
        ...untouched,
      }),
    ).toEqual({
      supplements: 'magnesium',
      symptoms: { example_symptom: 4 },
    })
  })

  it('stays blank until defaults load, then the seed fills them in', () => {
    expect(
      supplementsAfterBoardEffects({
        ...ready,
        ...untouched,
        defaultsReady: false,
      }),
    ).toEqual({ supplements: '', symptoms: {} })

    expect(resolveEmptyDayDefaults(ready)).toEqual({
      supplements: 'magnesium',
      symptoms: { example_symptom: 4 },
    })
  })

  it('puts defaults back when a clean entry is removed', () => {
    expect(
      supplementsAfterBoardEffects({
        ...ready,
        hasEntry: false,
        isDirty: false,
        // Hydration had marked the fields touched, so the seed no-ops this commit.
        supplementsTouched: true,
        symptomsTouched: true,
        currentSupplements: 'zinc',
        currentSymptoms: { example_symptom: 9 },
      }),
    ).toEqual({
      supplements: 'magnesium',
      symptoms: { example_symptom: 4 },
    })
  })

  it('does not overwrite an in-progress edit', () => {
    expect(
      supplementsAfterBoardEffects({
        ...ready,
        hasEntry: false,
        isDirty: true,
        supplementsTouched: true,
        symptomsTouched: true,
        currentSupplements: 'zinc',
        currentSymptoms: { example_symptom: 9 },
      }),
    ).toEqual({
      supplements: 'zinc',
      symptoms: { example_symptom: 9 },
    })
  })

  it('hydrates a saved entry instead of the defaults', () => {
    expect(
      supplementsAfterBoardEffects({
        ...ready,
        hasEntry: true,
        isDirty: false,
        supplementsTouched: true,
        symptomsTouched: true,
        currentSupplements: '',
        currentSymptoms: {},
        entrySupplements: 'zinc',
        entrySymptoms: { example_symptom: 9 },
      }),
    ).toEqual({
      supplements: 'zinc',
      symptoms: { example_symptom: 9 },
    })
  })
})
