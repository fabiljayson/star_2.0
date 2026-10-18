import { renderHook, waitFor, act } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import type { ReactNode } from 'react'
import { AuthProvider } from './AuthContext'
import { useAuth } from './context'
import { setAccessToken, storeRefreshToken } from '../lib/api'
import type { User } from '../lib/types'
import { jsonResponse, stubFetch } from '../test/helpers'

const testUser: User = {
  id: 'user-1',
  email: 'buyer.demo@example.test',
  first_name: 'Demo',
  last_name: 'Buyer',
  full_name: 'Demo Buyer',
  is_verified: true,
  is_platform_admin: false,
  mfa_enabled: false,
  roles: [
    {
      id: 'role-10',
      role: 'buyer',
      institution: 'inst-1',
      institution_name: 'Demo Hospital',
      department: null,
      department_name: null,
      is_active: true,
    },
  ],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}

describe('AuthProvider', () => {
  beforeEach(() => {
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('starts anonymous when no refresh token exists', async () => {
    const fetcher = stubFetch()
    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.status).toBe('anonymous'))
    expect(fetcher.fn).not.toHaveBeenCalled()
  })

  it('restores the session from a stored refresh token', async () => {
    storeRefreshToken('refresh-1')
    const fetcher = stubFetch()
    fetcher.on('/users/me/', () => jsonResponse(testUser))

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.status).toBe('authenticated'))
    expect(result.current.user?.email).toBe(testUser.email)
  })

  it('login stores the session and the refresh token', async () => {
    const fetcher = stubFetch()
    fetcher.on('/auth/login/', () =>
      jsonResponse({
        mfa_required: false,
        access: 'access-1',
        refresh: 'refresh-1',
        user: testUser,
      }),
    )

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.status).toBe('anonymous'))

    let outcome: string | undefined
    await act(async () => {
      outcome = await result.current.login(testUser.email, 'Demo!Passw0rd2026')
    })

    expect(outcome).toBe('ok')
    expect(result.current.status).toBe('authenticated')
    expect(result.current.user?.email).toBe(testUser.email)
    expect(localStorage.getItem('star.refresh')).toBe('refresh-1')
  })

  it('login with MFA returns "mfa" and verify completes the session', async () => {
    const fetcher = stubFetch()
    fetcher.on('/auth/login/', () =>
      jsonResponse({ mfa_required: true, mfa_token: 'mfa-1', expires_in: 300 }),
    )
    fetcher.on('/auth/mfa/verify/', () =>
      jsonResponse({
        mfa_required: false,
        access: 'access-2',
        refresh: 'refresh-2',
        user: testUser,
      }),
    )

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.status).toBe('anonymous'))

    let outcome: string | undefined
    await act(async () => {
      outcome = await result.current.login(testUser.email, 'Demo!Passw0rd2026')
    })

    expect(outcome).toBe('mfa')
    expect(result.current.pendingMfaToken).toBe('mfa-1')
    expect(result.current.status).toBe('anonymous')

    await act(async () => {
      await result.current.verifyMfa('123456')
    })

    expect(result.current.status).toBe('authenticated')
    expect(result.current.pendingMfaToken).toBeNull()
    const verifyCall = fetcher.calls.find((call) => call.url.includes('/auth/mfa/verify/'))
    const verifyBody = String((verifyCall?.init as RequestInit | undefined)?.body ?? '{}')
    expect(JSON.parse(verifyBody)).toEqual({ mfa_token: 'mfa-1', code: '123456' })
  })

  it('login failure keeps the session anonymous', async () => {
    const fetcher = stubFetch()
    fetcher.on('/auth/login/', () =>
      jsonResponse(
        { error: { code: 'invalid_credentials', message: 'Invalid email or password.' } },
        401,
      ),
    )

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.status).toBe('anonymous'))

    await act(async () => {
      await expect(
        result.current.login(testUser.email, 'wrong-password'),
      ).rejects.toThrow('Invalid email or password.')
    })

    expect(result.current.status).toBe('anonymous')
    expect(result.current.user).toBeNull()
  })

  it('logout revokes the refresh token and clears local state', async () => {
    storeRefreshToken('refresh-1')
    const fetcher = stubFetch()
    fetcher.on('/users/me/', () => jsonResponse(testUser))
    fetcher.on('/auth/logout/', () => jsonResponse(null, 204))

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.status).toBe('authenticated'))

    await act(async () => {
      await result.current.logout()
    })

    expect(result.current.status).toBe('anonymous')
    expect(localStorage.getItem('star.refresh')).toBeNull()
    expect(fetcher.calls.some((call) => call.url.includes('/auth/logout/'))).toBe(true)
  })

  it('hasAnyRole gates by active roles and platform admins', async () => {
    storeRefreshToken('refresh-1')
    const fetcher = stubFetch()
    fetcher.on('/users/me/', () => jsonResponse(testUser))

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.status).toBe('authenticated'))

    expect(result.current.hasRole('buyer')).toBe(true)
    expect(result.current.hasRole('supplier')).toBe(false)
    expect(result.current.hasAnyRole(['supplier', 'buyer'])).toBe(true)
    expect(result.current.hasAnyRole(['institution_admin'])).toBe(false)
    expect(result.current.hasAnyRole()).toBe(true)
  })
})
