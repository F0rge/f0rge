const BASE = '/api/v1'

class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

async function handleResponse(res: Response) {
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new ApiError(text, res.status)
  }
  const contentType = res.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    return res.json()
  }
  return res.text()
}

export async function apiGet(path: string) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'GET',
    credentials: 'include',
  })
  return handleResponse(res)
}

export async function apiPost(path: string, body: unknown) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handleResponse(res)
}

export async function apiPut(path: string, body: unknown) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handleResponse(res)
}

export async function apiDelete(path: string) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  return handleResponse(res)
}

export async function apiPostForm(path: string, formData: FormData) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })
  return handleResponse(res)
}

export { ApiError }
