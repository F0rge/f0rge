const DEFAULT_POST_LOGIN_PATH = '/checkin'

/**
 * Accept only same-origin relative paths: a single leading `/`, not `//`, no URL scheme.
 */
export function safePostLoginRedirect(
  redirect: string | null | undefined,
  fallback = DEFAULT_POST_LOGIN_PATH,
): string {
  if (redirect == null || redirect === '') {
    return fallback
  }
  if (!redirect.startsWith('/') || redirect.startsWith('//')) {
    return fallback
  }
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(redirect)) {
    return fallback
  }
  return redirect
}
