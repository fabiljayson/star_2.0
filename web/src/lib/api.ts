// ── API client — envelope: {"error": {code, message, details}} ──

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details?: unknown

  constructor(
    message: string,
    options: { code?: string; status?: number; details?: unknown } = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = options.code ?? 'unknown_error'
    this.status = options.status ?? 0
    this.details = options.details
  }
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export type ApiRequestOptions = {
  method?: HttpMethod
  body?: unknown
  auth?: boolean
  signal?: AbortSignal
  headers?: Record<string, string>
}

type ErrorEnvelope = {
  error?: { code?: string; message?: string; details?: unknown }
}

type TokenResponse = { access: string; refresh?: string }

const API_BASE = '/api/v1'
const REFRESH_STORAGE_KEY = 'star.refresh'

export const UNAUTHENTICATED_EVENT = 'star:unauthenticated'

let accessToken: string | null = null
let refreshInFlight: Promise<string | null> | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getStoredRefreshToken(): string | null {
  try {
    return window.localStorage.getItem(REFRESH_STORAGE_KEY)
  } catch {
    return null
  }
}

export function storeRefreshToken(token: string | null): void {
  try {
    if (token) {
      window.localStorage.setItem(REFRESH_STORAGE_KEY, token)
    } else {
      window.localStorage.removeItem(REFRESH_STORAGE_KEY)
    }
  } catch {
    // Storage unavailable (private mode): the session stays in memory only.
  }
}

function notifyUnauthenticated(): void {
  accessToken = null
  storeRefreshToken(null)
  window.dispatchEvent(new Event(UNAUTHENTICATED_EVENT))
}

async function requestRefresh(): Promise<string | null> {
  const stored = getStoredRefreshToken()
  if (!stored) return null
  try {
    const response = await fetch(`${API_BASE}/auth/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: stored }),
    })
    if (!response.ok) return null
    const data = (await response.json()) as TokenResponse
    accessToken = data.access
    if (data.refresh) storeRefreshToken(data.refresh)
    return data.access
  } catch {
    return null
  }
}

function getRefreshedAccess(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = requestRefresh().finally(() => {
      refreshInFlight = null
    })
  }
  return refreshInFlight
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return null
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

export async function apiFetch<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { method = 'GET', body, auth = true, headers = {}, signal } = options
  const hadSession = accessToken !== null || getStoredRefreshToken() !== null

  const doFetch = (token: string | null): Promise<Response> => {
    const finalHeaders: Record<string, string> = { ...headers }
    let payload: BodyInit | undefined
    if (body instanceof FormData) {
      payload = body
    } else if (body !== undefined) {
      finalHeaders['Content-Type'] = 'application/json'
      payload = JSON.stringify(body)
    }
    if (auth && token) {
      finalHeaders['Authorization'] = `Bearer ${token}`
    }
    return fetch(`${API_BASE}${path}`, {
      method,
      headers: finalHeaders,
      body: payload,
      signal,
    })
  }

  let response: Response
  try {
    response = await doFetch(auth ? accessToken : null)
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('Network error. Check your connection and try again.', {
      code: 'network_error',
    })
  }

  if (response.status === 401 && auth && hadSession) {
    const fresh = await getRefreshedAccess()
    if (fresh) {
      response = await doFetch(fresh)
    }
  }

  if (response.status === 204) return undefined as T

  const data = await parseBody(response)

  if (!response.ok) {
    if (response.status === 401 && auth && hadSession) {
      notifyUnauthenticated()
    }
    const envelope = data as ErrorEnvelope | null
    throw new ApiError(
      envelope?.error?.message ?? `Request failed with status ${response.status}.`,
      {
        code: envelope?.error?.code ?? `http_${response.status}`,
        status: response.status,
        details: envelope?.error?.details,
      },
    )
  }

  return data as T
}
