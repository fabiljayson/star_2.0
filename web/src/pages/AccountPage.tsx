import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { ErrorState } from '../components/ErrorState'
import { Spinner } from '../components/Spinner'
import { apiFetch } from '../lib/api'
import { roleLabel } from '../lib/roles'
import type { User } from '../lib/types'

export function AccountPage() {
  const { user, logout, logoutAll } = useAuth()
  const navigate = useNavigate()

  const query = useQuery({
    queryKey: ['me'],
    queryFn: () => apiFetch<User>('/users/me/'),
    initialData: user ?? undefined,
  })

  const account = query.data ?? user

  async function onSignOut(): Promise<void> {
    await logout()
    navigate('/login', { replace: true })
  }

  async function onSignOutEverywhere(): Promise<void> {
    await logoutAll()
    navigate('/login', { replace: true })
  }

  if (query.isPending && !account) {
    return (
      <div className="page-loading" role="status">
        <Spinner size="md" label="Loading your account…" />
      </div>
    )
  }

  if (query.isError && !account) {
    return (
      <ErrorState
        message={
          query.error instanceof Error
            ? query.error.message
            : 'Could not load your account.'
        }
        onRetry={() => void query.refetch()}
      />
    )
  }

  if (!account) return null

  const activeRoles = account.roles.filter((assignment) => assignment.is_active)

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Account</h1>
          <p className="page__subtitle">Profile, roles and session controls.</p>
        </div>
        <div className="badge-row">
          <Badge tone={account.is_verified ? 'success' : 'warning'}>
            {account.is_verified ? 'Email verified' : 'Email unverified'}
          </Badge>
          <Badge tone={account.mfa_enabled ? 'success' : 'neutral'}>
            {account.mfa_enabled ? 'Two-factor on' : 'Two-factor off'}
          </Badge>
        </div>
      </header>

      <div className="account-grid">
        <Card title="Profile">
          <dl className="definition-list">
            <dt>Name</dt>
            <dd>{account.full_name || '—'}</dd>
            <dt>Email</dt>
            <dd>{account.email}</dd>
            <dt>Member since</dt>
            <dd>{new Date(account.created_at).toLocaleDateString()}</dd>
          </dl>
          {query.isFetching && (
            <p className="field__hint">
              <Spinner size="sm" /> Refreshing…
            </p>
          )}
        </Card>

        <Card title="Roles">
          {activeRoles.length === 0 ? (
            <p className="field__hint">
              No active roles yet. Institution administrators assign roles.
            </p>
          ) : (
            <ul className="role-list">
              {activeRoles.map((assignment) => (
                <li key={assignment.id}>
                  <span className="badge-row">
                    <Badge tone="info">{roleLabel(assignment.role)}</Badge>
                  </span>
                  <span className="role-list__org">
                    {[
                      assignment.institution_name,
                      assignment.department_name,
                    ]
                      .filter(Boolean)
                      .join(' · ') || 'Independent'}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Session">
          <p className="field__hint">
            Signing out everywhere invalidates every device, including this one.
          </p>
          <div className="badge-row">
            <Button variant="secondary" onClick={() => void onSignOut()}>
              Sign out
            </Button>
            <Button variant="danger" onClick={() => void onSignOutEverywhere()}>
              Sign out everywhere
            </Button>
          </div>
        </Card>
      </div>
    </div>
  )
}
