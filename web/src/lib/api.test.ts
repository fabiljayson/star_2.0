import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  UNAUTHENTICATED_EVENT,
  apiFetch,
  getStoredRefreshToken,
  setAccessToken,
  storeRefreshToken,
} from './api'
import { emptyResponse, jsonResponse, stubFetch } from '../test/helpers'

describe('apiFetch', () => {
  beforeEach(() => {
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('parses the error envelope into an ApiError', async () => {
    const fetcher = stubFetch()
    fetcher.on('/auth/login/', () =>
      jsonResponse(
        {
          error: {
            code: 'invalid_credentials',
            message: 'Invalid email or password.',
            details: { field: 'email' },
          },
        },
        401,
      ),
    )

    await expect(
      apiFetch('/auth/login/', { method: 'POST', auth: false, body: {} }),
    ).rejects.toMatchObject({
      name: 'ApiError',
      code: 'invalid_credentials',
      status: 401,
      message: 'Invalid email or password.',
    })
  })

  it('attaches the bearer token when a session exists', async () => {
    setAccessToken('access-1')
    const fetcher = stubFetch()
    fetcher.on('/users/me/', () => jsonResponse({ id: 1 }))

    await apiFetch('/users/me/')

    const init = fetcher.calls[0]?.init as RequestInit
    expect((init.headers as Record<string, string>).Authorization).toBe(
      'Bearer access-1',
    )
  })

  it('refreshes once on 401 and retries with the fresh token', async () => {
    setAccessToken('stale')
    storeRefreshToken('refresh-1')
    const fetcher = stubFetch()
    let meCalls = 0
    fetcher.on('/users/me/', () => {
      meCalls += 1
      if (meCalls === 1) {
        return jsonResponse({ error: { code: 'token_expired', message: 'Expired' } }, 401)
      }
      return jsonResponse({ id: 7 })
    })
    fetcher.on('/auth/token/refresh/', () =>
      jsonResponse({ access: 'fresh', refresh: 'refresh-2' }),
    )

    const data = await apiFetch<{ id: number }>('/users/me/')

    expect(data).toEqual({ id: 7 })
    expect(fetcher.calls).toHaveLength(3)
    const retryInit = fetcher.calls[2]?.init as RequestInit
    expect((retryInit.headers as Record<string, string>).Authorization).toBe(
      'Bearer fresh',
    )
    expect(getStoredRefreshToken()).toBe('refresh-2')
  })

  it('dispatches star:unauthenticated when the refresh fails', async () => {
    setAccessToken('stale')
    storeRefreshToken('refresh-1')
    const listener = vi.fn()
    window.addEventListener(UNAUTHENTICATED_EVENT, listener)

    const fetcher = stubFetch()
    fetcher.on('/users/me/', () =>
      jsonResponse({ error: { code: 'token_invalid', message: 'Nope' } }, 401),
    )
    fetcher.on('/auth/token/refresh/', () =>
      jsonResponse({ error: { code: 'token_revoked', message: 'Revoked' } }, 401),
    )

    await expect(apiFetch('/users/me/')).rejects.toBeInstanceOf(ApiError)

    expect(listener).toHaveBeenCalledTimes(1)
    expect(getStoredRefreshToken()).toBeNull()
    window.removeEventListener(UNAUTHENTICATED_EVENT, listener)
  })

  it('returns undefined on 204 responses', async () => {
    const fetcher = stubFetch()
    fetcher.on('/auth/logout/', () => emptyResponse(204))

    await expect(apiFetch('/auth/logout/', { method: 'POST' })).resolves.toBeUndefined()
  })

  it('sends FormData without a JSON content type', async () => {
    setAccessToken('access-1')
    const fetcher = stubFetch()
    fetcher.on('/upload/', () => jsonResponse({ id: 1 }))
    const form = new FormData()
    form.append('body', 'hello')

    await apiFetch('/upload/', { method: 'POST', body: form })

    const init = fetcher.calls[0]?.init as RequestInit
    expect((init.headers as Record<string, string>)['Content-Type']).toBeUndefined()
    expect(init.body).toBe(form)
  })

  it('wraps network failures as a network_error ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))

    await expect(apiFetch('/users/me/', { auth: false })).rejects.toMatchObject({
      name: 'ApiError',
      code: 'network_error',
    })
  })

  it('does not attach credentials or refresh when auth is false', async () => {
    storeRefreshToken('refresh-1')
    const fetcher = stubFetch()
    fetcher.on('/auth/login/', () => jsonResponse({ mfa_required: false }))

    await apiFetch('/auth/login/', { method: 'POST', auth: false, body: {} })

    expect(fetcher.calls).toHaveLength(1)
    const init = fetcher.calls[0]?.init as RequestInit
    expect((init.headers as Record<string, string>)['Authorization']).toBeUndefined()
  })
})
