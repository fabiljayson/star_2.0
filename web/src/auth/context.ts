import { createContext, useContext } from 'react'
import type { User } from '../lib/types'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

export type LoginOutcome = 'ok' | 'mfa'

export type AuthContextValue = {
  user: User | null
  status: AuthStatus
  pendingMfaToken: string | null
  login: (email: string, password: string) => Promise<LoginOutcome>
  verifyMfa: (code: string) => Promise<void>
  cancelMfa: () => void
  logout: () => Promise<void>
  logoutAll: () => Promise<void>
  hasRole: (role: string) => boolean
  hasAnyRole: (roles?: string[]) => boolean
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside an AuthProvider')
  }
  return context
}
