/** Skip copying server entry fields into local board state while the user has unsaved edits. */
export function shouldApplyEntryHydration(isDirty: boolean): boolean {
  return !isDirty
}
