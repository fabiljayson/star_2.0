import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { Badge } from '../components/Badge'
import { Card } from '../components/Card'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { Spinner } from '../components/Spinner'
import { apiFetch } from '../lib/api'
import { formatDate, formatDateTime, formatMoney } from '../lib/format'
import { roleLabel } from '../lib/roles'
import { statusMeta } from '../lib/status'
import type {
  Assessment,
  Notification,
  Order,
  Page,
  SurgicalProcedure,
  TrainingPlacement,
} from '../lib/types'

function StatCard({
  label,
  value,
  hint,
  to,
}: {
  label: string
  value: number | string
  hint?: string
  to: string
}) {
  return (
    <Link to={to} className="stat-card glass">
      <span className="stat-card__label">{label}</span>
      <span className="stat-card__value">{value}</span>
      {hint && <span className="stat-card__hint">{hint}</span>}
    </Link>
  )
}

export function DashboardPage() {
  const { user, hasRole, hasAnyRole } = useAuth()

  const isClinical = hasAnyRole([
    'independent_surgeon',
    'trainee',
    'supervisor',
    'examiner',
    'department_manager',
    'institution_admin',
  ])
  const isMarketplace = hasRole('buyer') || hasRole('supplier')
  const canReview = hasRole('examiner') || hasRole('supervisor')
  const canManageTraining =
    hasRole('supervisor') || hasRole('department_manager') || hasRole('institution_admin')

  const mineQuery = useQuery({
    queryKey: ['dashboard-procedures-mine'],
    queryFn: () =>
      apiFetch<Page<SurgicalProcedure>>('/procedures/?mine=1&page_size=5&ordering=-procedure_date'),
    enabled: isClinical,
  })
  const approvedQuery = useQuery({
    queryKey: ['dashboard-procedures-approved'],
    queryFn: () => apiFetch<Page<SurgicalProcedure>>('/procedures/?mine=1&status=approved&page_size=1'),
    enabled: isClinical,
  })
  const submittedQuery = useQuery({
    queryKey: ['dashboard-procedures-submitted'],
    queryFn: () => apiFetch<Page<SurgicalProcedure>>('/procedures/?status=submitted&page_size=1'),
    enabled: isClinical,
  })
  const placementQuery = useQuery({
    queryKey: ['dashboard-active-placement'],
    queryFn: () => apiFetch<Page<TrainingPlacement>>('/training/placements/?status=active&page_size=1'),
    enabled: isClinical,
  })
  const assessmentQueueQuery = useQuery({
    queryKey: ['dashboard-assessment-queue'],
    queryFn: () => apiFetch<Page<Assessment>>('/assessments/?status=submitted&page_size=1'),
    enabled: canReview,
  })
  const unreadQuery = useQuery({
    queryKey: ['dashboard-unread'],
    queryFn: () => apiFetch<{ count: number }>('/notifications/unread-count/'),
  })
  const recentNotificationsQuery = useQuery({
    queryKey: ['dashboard-notifications'],
    queryFn: () => apiFetch<Page<Notification>>('/notifications/?page_size=3'),
  })
  const ordersQuery = useQuery({
    queryKey: ['dashboard-orders'],
    queryFn: () => apiFetch<Page<Order>>('/marketplace/orders/?page_size=5'),
    enabled: isMarketplace,
  })

  if (!user) return null

  const activeRole = user.roles.find((assignment) => assignment.is_active)
  const firstName = user.first_name || user.full_name
  const mine = mineQuery.data?.results ?? []
  const activePlacement = placementQuery.data?.results?.[0]
  const recentOrders = ordersQuery.data?.results ?? []
  const unread = unreadQuery.data?.count ?? 0
  const notifications = recentNotificationsQuery.data?.results ?? []

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Welcome back, {firstName}</h1>
          <p className="page__subtitle">
            {activeRole ? roleLabel(activeRole.role) : 'Signed in'}
            {unread > 0 ? ` · ${unread} unread notification${unread === 1 ? '' : 's'}` : ''}
          </p>
        </div>
        <div className="badge-row">
          {isClinical && (
            <Link to="/logbook/new" className="btn btn--primary btn--sm">
              New surgical record
            </Link>
          )}
          {isClinical && (
            <Link to="/logbook" className="btn btn--ghost btn--sm">
              Open logbook
            </Link>
          )}
          {isMarketplace && (
            <Link to="/marketplace" className="btn btn--secondary btn--sm">
              Browse marketplace
            </Link>
          )}
        </div>
      </header>

      {isClinical && (
        <section className="stat-grid" aria-label="Logbook summary">
          <StatCard
            label="My records"
            value={mineQuery.data?.count ?? (mineQuery.isPending ? '—' : 0)}
            hint="All statuses"
            to="/logbook"
          />
          <StatCard
            label="Approved"
            value={approvedQuery.data?.count ?? (approvedQuery.isPending ? '—' : 0)}
            hint="Your approved records"
            to="/logbook?status=approved"
          />
          <StatCard
            label="Awaiting review"
            value={submittedQuery.data?.count ?? (submittedQuery.isPending ? '—' : 0)}
            hint="Submitted records in scope"
            to="/logbook?status=submitted"
          />
          <StatCard
            label="Unread notifications"
            value={unreadQuery.isPending ? '—' : unread}
            hint="Review and correction updates"
            to="/notifications"
          />
        </section>
      )}

      {isClinical && (
        <div className="account-grid">
          <Card
            title="Recent records"
            actions={
              <Link to="/logbook" className="btn btn--ghost btn--sm">
                View all
              </Link>
            }
          >
            {mineQuery.isPending ? (
              <div className="page-loading" role="status">
                <Spinner size="md" />
                <span>Loading records…</span>
              </div>
            ) : mineQuery.isError ? (
              <ErrorState
                message={
                  mineQuery.error instanceof Error
                    ? mineQuery.error.message
                    : 'Could not load your records.'
                }
                onRetry={() => void mineQuery.refetch()}
              />
            ) : mine.length === 0 ? (
              <EmptyState
                title="No records yet"
                message="Start your logbook with a draft surgical record."
                action={
                  <Link to="/logbook/new" className="btn btn--primary btn--sm">
                    New record
                  </Link>
                }
              />
            ) : (
              <ul className="role-list">
                {mine.map((procedure) => {
                  const meta = statusMeta('procedure', procedure.status)
                  return (
                    <li key={procedure.id}>
                      <Link to={`/logbook/${procedure.id}`} className="record-inline">
                        <span>
                          <strong>{procedure.procedure_name}</strong>
                          <span className="field__hint">
                            {procedure.reference} · {formatDate(procedure.procedure_date)}
                          </span>
                        </span>
                        <Badge tone={meta.tone}>{meta.label}</Badge>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            )}
          </Card>

          <div className="dashboard-aside">
            <Card title="Training">
              {placementQuery.isPending ? (
                <div className="page-loading" role="status">
                  <Spinner size="md" />
                </div>
              ) : activePlacement ? (
                <div className="dashboard-focus">
                  <strong>{activePlacement.title}</strong>
                  <span className="field__hint">
                    {activePlacement.trainee_detail.full_name} ·{' '}
                    {activePlacement.institution_name}
                  </span>
                  <div className="badge-row">
                    <Badge tone="info">Active placement</Badge>
                    <Link
                      to={`/training/placements/${activePlacement.id}`}
                      className="btn btn--secondary btn--sm"
                    >
                      Open progress
                    </Link>
                  </div>
                </div>
              ) : (
                <p className="field__hint">
                  No active placement is visible for your account.
                </p>
              )}
              <div className="badge-row">
                <Link to="/training" className="btn btn--ghost btn--sm">
                  Placements
                </Link>
                <Link to="/training/assessments" className="btn btn--ghost btn--sm">
                  Assessments
                </Link>
                {canReview && (
                  <Link
                    to="/training/assessments?status=submitted"
                    className="btn btn--secondary btn--sm"
                  >
                    Review queue
                    {assessmentQueueQuery.data ? ` (${assessmentQueueQuery.data.count})` : ''}
                  </Link>
                )}
                {canManageTraining && (
                  <Link to="/training/placements/new" className="btn btn--ghost btn--sm">
                    New placement
                  </Link>
                )}
              </div>
            </Card>

            <Card
              title="Notifications"
              actions={
                <Link to="/notifications" className="btn btn--ghost btn--sm">
                  View all
                </Link>
              }
            >
              {recentNotificationsQuery.isPending ? (
                <div className="page-loading" role="status">
                  <Spinner size="md" />
                </div>
              ) : notifications.length === 0 ? (
                <p className="field__hint">Nothing new. Updates about reviews and orders appear here.</p>
              ) : (
                <ul className="role-list">
                  {notifications.map((notification) => (
                    <li key={notification.id}>
                      <strong>{notification.title}</strong>
                      <span className="field__hint">
                        {notification.is_read ? '' : 'Unread · '}
                        {formatDateTime(notification.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </div>
      )}

      {isMarketplace && (
        <Card
          title="Marketplace activity"
          actions={
            <Link to="/marketplace/orders" className="btn btn--ghost btn--sm">
              All orders
            </Link>
          }
        >
          {ordersQuery.isPending ? (
            <div className="page-loading" role="status">
              <Spinner size="md" />
            </div>
          ) : ordersQuery.isError ? (
            <ErrorState
              message={
                ordersQuery.error instanceof Error
                  ? ordersQuery.error.message
                  : 'Could not load orders.'
              }
              onRetry={() => void ordersQuery.refetch()}
            />
          ) : recentOrders.length === 0 ? (
            <EmptyState
              title="No marketplace orders"
              message="Orders appear here after checkout, for buyers and suppliers alike."
              action={
                <Link to="/marketplace" className="btn btn--primary btn--sm">
                  Browse catalog
                </Link>
              }
            />
          ) : (
            <ul className="role-list">
              {recentOrders.map((order) => {
                const meta = statusMeta('order', order.status)
                return (
                  <li key={order.id}>
                    <Link to={`/marketplace/orders/${order.id}`} className="record-inline">
                      <span>
                        <strong>{order.reference}</strong>
                        <span className="field__hint">
                          {order.supplier_name} · {formatDateTime(order.placed_at)} ·{' '}
                          {formatMoney(order.total, order.currency)}
                        </span>
                      </span>
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </Card>
      )}
    </div>
  )
}
