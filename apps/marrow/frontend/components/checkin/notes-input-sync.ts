/** Whether to copy parent `value` into the notes textarea draft. */
export function shouldHydrateNotesDraft(
  hasStartedTyping: boolean,
  draft: string,
  nextParentValue: string,
  prevParentValue: string,
): boolean {
  if (nextParentValue === prevParentValue) return false
  if (!hasStartedTyping) return draft !== nextParentValue
  return nextParentValue !== draft
}
