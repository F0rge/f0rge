/** Skip copying scalar entry fields into local board state while the user has unsaved edits. */
export function shouldApplyEntryHydration(isDirty: boolean): boolean {
  return !isDirty
}

/** Server meal photos always sync — new uploads must appear without wiping in-progress scores. */
export function shouldSyncEntryPhotos(): boolean {
  return true
}
