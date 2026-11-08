export interface EmptyDayDefaultsInput {
  /** Settings and both catalogs have finished loading. */
  defaultsReady: boolean
  /** Active default supplement keys, comma-separated. */
  defaultSupplements: string
  /** Active default symptom severities. */
  defaultSymptoms: Record<string, number>
}

export interface EmptyDayDefaults {
  supplements: string
  symptoms: Record<string, number>
}

/**
 * Supplements and symptoms for a day with no saved check-in.
 *
 * The board seeds these, then the no-entry reset runs in the same commit.
 * The reset must write this result. Writing blanks used to win whenever
 * settings and catalogs were already cached, so the seed never ran again.
 */
export function resolveEmptyDayDefaults(input: EmptyDayDefaultsInput): EmptyDayDefaults {
  if (!input.defaultsReady) {
    return { supplements: '', symptoms: {} }
  }
  return {
    supplements: input.defaultSupplements,
    symptoms: input.defaultSymptoms,
  }
}
