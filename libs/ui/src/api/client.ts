import { toast } from 'sonner'

interface ApiConfig {
  base: string
  publicPaths: string[]
  loginPath: string
}

// ponytail: module-level config, not a client class — one API per app is the
// reality until an app needs two backends.
let config: ApiConfig = {
  base: '/api/v1',
  publicPaths: ['/login', '/signup'],
  loginPath: '/login',
}

/** Override the API defaults. Apps whose behavior matches the defaults need not call this. */
export function configureApi(overrides: Partial<ApiConfig>) {
  config = { ...config, ...overrides }
}

function isPublicAuthPath() {
  if (typeof window === 'undefined') return false
  return config.publicPaths.some((path) => window.location.pathname.startsWith(path))
}

class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

async function handleResponse(res: Response) {
  if (res.status === 401) {
    // Session expired — redirect to login with return URL
    if (typeof window !== 'undefined' && !isPublicAuthPath()) {
      const returnTo = encodeURIComponent(window.location.pathname)
      window.location.href = `${config.loginPath}?redirect=${returnTo}`
    }
    throw new ApiError('Session expired', 401)
  }
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new ApiError(text, res.status)
  }
  // 204 No Content — no body to parse
  if (res.status === 204) {
    return null
  }
  const contentType = res.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    return res.json()
  }
  return res.text()
}

export async function apiGetRaw(path: string): Promise<Response> {
  const res = await fetch(`${config.base}${path}`, {
    method: 'GET',
    credentials: 'include',
  })
  if (res.status === 401) {
    if (typeof window !== 'undefined' && !isPublicAuthPath()) {
      const returnTo = encodeURIComponent(window.location.pathname)
      window.location.href = `${config.loginPath}?redirect=${returnTo}`
    }
    throw new ApiError('Session expired', 401)
  }
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new ApiError(text, res.status)
  }
  return res
}

export async function apiGet(path: string) {
  const res = await fetch(`${config.base}${path}`, {
    method: 'GET',
    credentials: 'include',
  })
  return handleResponse(res)
}

export async function apiPost(path: string, body: unknown) {
  const res = await fetch(`${config.base}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handleResponse(res)
}

export async function apiPut(path: string, body: unknown) {
  const res = await fetch(`${config.base}${path}`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handleResponse(res)
}

export async function apiPatch(path: string, body: unknown) {
  const res = await fetch(`${config.base}${path}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handleResponse(res)
}

export async function apiDelete(path: string, body?: unknown) {
  const res = await fetch(`${config.base}${path}`, {
    method: 'DELETE',
    credentials: 'include',
    ...(body !== undefined
      ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
      : {}),
  })
  return handleResponse(res)
}

export async function apiPostForm(path: string, formData: FormData) {
  const res = await fetch(`${config.base}${path}`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })
  return handleResponse(res)
}

export { ApiError }

/**
 * Extract a user-facing message from a caught error, preferring the
 * server's `detail` message (FastAPI's HTTPException body) over a generic
 * fallback. `ApiError.message` is the raw response body text, so a FastAPI
 * error is `{"detail": "..."}` as a JSON string that needs parsing.
 */
export function getErrorDetail(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    try {
      const parsed = JSON.parse(err.message) as { detail?: string }
      if (typeof parsed.detail === 'string') return parsed.detail
    } catch {
      // err.message wasn't JSON — keep the fallback
    }
  }
  return fallback
}

/**
 * Show a toast for a caught mutation error. See `getErrorDetail`.
 */
export function handleMutationError(err: unknown, fallback: string) {
  toast.error(getErrorDetail(err, fallback))
}
