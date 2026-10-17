/**
 * Day-entry cache policy.
 *
 * The app client keeps queries fresh for 60s and disables refetch on window
 * focus. A check-in left open therefore misses meals logged elsewhere (MCP)
 * until a full reload. These overrides apply only to `useEntry`.
 */
export const dayEntryRefetchOptions = {
  // Refetch when a mounted observer attaches and the cached day is stale.
  refetchOnMount: true,
  // Refetch when the document becomes visible again and the cached day is stale.
  refetchOnWindowFocus: true,
} as const

type EventTargetLike = {
  addEventListener: (type: string, listener: () => void) => void
  removeEventListener: (type: string, listener: () => void) => void
}

/**
 * TanStack Query 5's focus manager listens only for `visibilitychange`.
 * Also listen for `window` `focus`, so returning to an already-visible window
 * refreshes a stale day. The listener does not choose which queries refetch.
 */
export function bindDocumentReturnEvents(
  onReturn: () => void,
  target: EventTargetLike = window,
): () => void {
  target.addEventListener('visibilitychange', onReturn)
  target.addEventListener('focus', onReturn)
  return () => {
    target.removeEventListener('visibilitychange', onReturn)
    target.removeEventListener('focus', onReturn)
  }
}
