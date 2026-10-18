import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  ApiError,
  UNAUTHENTICATED_EVENT,
  apiFetch,
  getStoredRefreshToken,
  setAccessToken,
  storeRefreshToken,
} from '../lib/api'
import type { LoginResponse, User } from '../lib/types'
import { AuthContext, type AuthStatus, type LoginOutcome } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [pendingMfaToken, setPendingMfaToken] = useState<string | null>(null)

  const startSession = useCallback(
    (data: { access: string; refresh?: string; user: User }) => {
      setAccessToken(data.access)
      if (data.refresh) storeRefreshToken(data.refresh)
      setUser(data.user)
      setStatus('authenticated')
      setPendingMfaToken(null)
    },
    [],
  )

  const clearSession = useCallback(() => {
    setAccessToken(null)
    storeRefreshToken(null)
    setUser(null)
    setStatus('anonymous')
    setPendingMfaToken(null)
  }, [])

  useEffect(() => {
    const onUnauthenticated = () => {
      setAccessToken(null)
      storeRefreshToken(null)
      setUser(null)
      setStatus('anonymous')
      setPendingMfaToken(null)
    }
    window.addEventListener(UNAUTHENTICATED_EVENT, onUnauthenticated)
    return () => window.removeEventListener(UNAUTHENTICATED_EVENT, onUnauthenticated)
  }, [])

  useEffect(() => {
    let cancelled = false

    async function restore(): Promise<void> {
      if (!getStoredRefreshToken()) {
        if (!cancelled) setStatus('anonymous')
        return
      }
      try {
        const me = await apiFetch<User>('/users/me/')
        if (!cancelled) {
          setUser(me)
          setStatus('authenticated')
        }
      } catch {
        if (!cancelled) setStatus('anonymous')
      }
    }

    void restore()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(
    async (email: string, password: string): Promise<LoginOutcome> => {
      const data = await apiFetch<LoginResponse>('/auth/login/', {
        method: 'POST',
        auth: false,
        body: { email, password },
      })
      if (data.mfa_required) {
        if (!data.mfa_token) {
          throw new ApiError('MFA session missing. Please try again.', {
            code: 'mfa_token_missing',
          })
        }
        setPendingMfaToken(data.mfa_token)
        return 'mfa'
      }
      if (!data.access || !data.user) {
        throw new ApiError('Malformed login response.', { code: 'invalid_response' })
      }
      startSession({ access: data.access, refresh: data.refresh, user: data.user })
      return 'ok'
    },
    [startSession],
  )

  const verifyMfa = useCallback(
    async (code: string): Promise<void> => {
      if (!pendingMfaToken) {
        throw new ApiError('MFA session expired. Please sign in again.', {
          code: 'mfa_session_missing',
        })
      }
      const data = await apiFetch<LoginResponse>('/auth/mfa/verify/', {
        method: 'POST',
        auth: false,
        body: { mfa_token: pendingMfaToken, code },
      })
      if (!data.access || !data.user) {
        throw new ApiError('Malformed MFA response.', { code: 'invalid_response' })
      }
      startSession({ access: data.access, refresh: data.refresh, user: data.user })
    },
    [pendingMfaToken, startSession],
  )

  const cancelMfa = useCallback(() => {
    setPendingMfaToken(null)
  }, [])

  const logout = useCallback(async (): Promise<void> => {
    const refresh = getStoredRefreshToken()
    if (refresh) {
      try {
        await apiFetch<void>('/auth/logout/', { method: 'POST', body: { refresh } })
      } catch {
        // Best effort: local session is cleared either way.
      }
    }
    clearSession()
  }, [clearSession])

  const logoutAll = useCallback(async (): Promise<void> => {
    try {
      await apiFetch<void>('/auth/logout-all/', { method: 'POST' })
    } catch {
      // Best effort: the local session is cleared below regardless.
    }
    clearSession()
  }, [clearSession])

  const hasRole = useCallback(
    (role: string): boolean => {
      if (!user) return false
      if (role === 'platform_admin' && user.is_platform_admin) return true
      return user.roles.some((assignment) => assignment.is_active && assignment.role === role)
    },
    [user],
  )

  const hasAnyRole = useCallback(
    (roles?: string[]): boolean => {
      if (!roles || roles.length === 0) return true
      return roles.some((role) => hasRole(role))
    },
    [hasRole],
  )

  const value = useMemo(
    () => ({
      user,
      status,
      pendingMfaToken,
      login,
      verifyMfa,
      cancelMfa,
      logout,
      logoutAll,
      hasRole,
      hasAnyRole,
    }),
    [
      user,
      status,
      pendingMfaToken,
      login,
      verifyMfa,
      cancelMfa,
      logout,
      logoutAll,
      hasRole,
      hasAnyRole,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
