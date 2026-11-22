import { useCallback, useState } from "react";

const CURRENT = Symbol("current failure");

/**
 * The text of a page's one error notice: the last action's error, else the current load
 * failure unless the user dismissed that same failure. A new failed load is a new Error,
 * so it shows again.
 */
export function pageErrorText(
  actionError: string | null,
  loadFailure: Error | null,
  dismissed: Error | null,
  fallback: string,
): string | null {
  if (actionError) return actionError;
  if (!loadFailure || loadFailure === dismissed) return null;
  return loadFailure.message || fallback;
}

/**
 * One notice for load and action failures. `setError(message)` shows an action error;
 * `setError(null)` (closing the notice, or starting a new action) also hides the current
 * load failure, as a single error state did before queries.
 */
export function usePageError(loadFailure: Error | null, fallback: string) {
  const [actionError, setActionError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<Error | null | typeof CURRENT>(null);
  // Resolve "dismiss whatever is showing" to the failure shown now, so setError stays stable.
  if (dismissed === CURRENT) setDismissed(loadFailure);
  const setError = useCallback((message: string | null) => {
    setActionError(message);
    if (message === null) setDismissed(CURRENT);
  }, []);
  return {
    error: pageErrorText(actionError, loadFailure, dismissed === CURRENT ? loadFailure : dismissed, fallback),
    setError,
  };
}
