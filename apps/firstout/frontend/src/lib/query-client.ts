import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";

/** A 4xx is the server's answer (denied, missing, invalid); asking again cannot change it. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
  // ponytail: one retry for network/5xx keeps the error state fast; raise if flaky links need more.
  return failureCount < 1;
}

/** The one server-state cache. One per signed-in session and organisation (see StaffProvider). */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      // Back office: staff switch windows constantly; pages reload on mount and after their own writes.
      queries: { retry: shouldRetry, refetchOnWindowFocus: false },
      // Never re-send a write on its own.
      mutations: { retry: false },
    },
  });
}
