import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { useAuth } from '../../auth/context'
import { apiFetch } from '../../lib/api'
import { formatDate } from '../../lib/format'
import type { Page, TrainingPlacement } from '../../lib/types'
import { PLACEMENT_STATUSES, statusMeta } from '../../lib/status'

function buildQuery(status: string, search: string, page: number): string {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (search.trim()) params.set('search', search.trim())
  if (page > 1) params.set('page', String(page))
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export function PlacementListPage() {
  const navigate = useNavigate()
  const { user, hasRole } = useAuth()
  const canCreate = hasRole('institution_admin') || Boolean(user?.is_platform_admin)
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [appliedSearch, setAppliedSearch] = useState('')
  const [page, setPage] = useState(1)

  const query = useQuery({
    queryKey: ['placements', status, appliedSearch, page],
    queryFn: () =>
      apiFetch<Page<TrainingPlacement>>(`/training/placements/${buildQuery(status, appliedSearch, page)}`),
  })

  const results = query.data?.results ?? []
  const count = query.data?.count ?? 0
  const pageSize = 20
  const totalPages = Math.max(1, Math.ceil(count / pageSize))

  function onSubmit(event: FormEvent): void {
    event.preventDefault()
    setPage(1)
    setAppliedSearch(search)
  }

  function onCreate(): void {
    navigate('/training/placements/new', { replace: true })
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Training placements</h1>
          <p className="page__subtitle">
            {query.isPending ? 'Loading placements…' : `${count} placement${count === 1 ? '' : 's'}`}
          </p>
        </div>
        {canCreate && (
          <Button variant="primary" onClick={onCreate}>
            New placement
          </Button>
        )}
      </header>

      <form className="list-filters" role="search" onSubmit={onSubmit}>
        <label className="field list-filters__search">
          <span className="field__label">Search</span>
          <input
            className="field__control"
            type="search"
            placeholder="Title or trainee"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label className="field">
          <span className="field__label">Status</span>
          <select
            className="field__control"
            value={status}
            onChange={(event: React.ChangeEvent<HTMLSelectElement>) => {
              setStatus(event.target.value)
              setPage(1)
            }}
          >
            <option value="">All statuses</option>
            {PLACEMENT_STATUSES.map((value: string) => (
              <option key={value} value={value}>
                {statusMeta('placement', value).label}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" variant="secondary" size="sm">
          Apply
        </Button>
      </form>

      {query.isPending ? (
        <div className="page-loading" role="status">
          <Spinner size="md" />
        </div>
      ) : query.isError ? (
        <ErrorState
          message={
            query.error instanceof Error ? query.error.message : 'Could not load placements.'
          }
          onRetry={() => void query.refetch()}
        />
      ) : results.length === 0 ? (
        <EmptyState
          title="No placements yet"
          message="Create your first training placement to get started."
          action={
            canCreate ? (
              <Button variant="primary" size="sm" onClick={onCreate}>
                New placement
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="record-list">
          {results.map((placement) => {
            const meta = statusMeta('placement', placement.status)
            return (
              <Link
                key={placement.id}
                to={`/training/placements/${placement.id}`}
                className="record-row glass"
              >
                <span className="record-row__main">
                  <span className="record-row__ref">{placement.title}</span>
                  <span className="record-row__name">
                    {placement.trainee_detail.full_name}
                  </span>
                  <span className="record-row__meta">
                    {formatDate(placement.start_date)} · {placement.institution_name}
                    {placement.department_name ? ` · ${placement.department_name}` : ''}
                  </span>
                </span>
                <span className="record-row__side">
                  <Badge tone={meta.tone} title={meta.label}>
                    {meta.label}
                  </Badge>
                  <span className="record-row__chevron" aria-hidden="true">
                    ›
                  </span>
                </span>
              </Link>
            )
          })}
        </div>
      )}

      {totalPages > 1 && (
        <nav className="pagination" aria-label="Placement pages">
          <Button
            variant="secondary"
            size="sm"
            disabled={page <= 1 || query.isFetching}
            onClick={() => setPage((current) => current - 1)}
          >
            ← Previous
          </Button>
          <span className="pagination__status">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={page >= totalPages || query.isFetching}
            onClick={() => setPage((current) => current + 1)}
          >
            Next →
          </Button>
        </nav>
      )}
    </div>
  )
}
