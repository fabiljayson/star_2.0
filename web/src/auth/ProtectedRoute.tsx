import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Spinner } from '../components/Spinner'
import { useAuth } from './context'
import { ForbiddenPage } from '../pages/ForbiddenPage'

type ProtectedRouteProps = {
  children: ReactNode
  roles?: string[]
}

export function ProtectedRoute({ children, roles }: ProtectedRouteProps) {
  const { status, hasAnyRole } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <div className="page-loading" role="status">
        <Spinner size="md" />
        <span>Restoring your session…</span>
      </div>
    )
  }

  if (status === 'anonymous') {
    const from = `${location.pathname}${location.search}`
    return <Navigate to="/login" replace state={{ from }} />
  }

  if (!hasAnyRole(roles)) {
    return <ForbiddenPage />
  }

  return children
}
