const SCHEME_RE = /^[a-zA-Z][a-zA-Z0-9+.-]*:/

/** Same-origin relative path only (single leading slash, not protocol-relative or absolute URL). */
export function resolvePostLoginRedirect(redirectParam: string | null | undefined): string {
  if (!redirectParam) return '/checkin'
  const path = redirectParam.trim()
  if (!path.startsWith('/') || path.startsWith('//')) return '/checkin'
  if (SCHEME_RE.test(path)) return '/checkin'
  return path
}
