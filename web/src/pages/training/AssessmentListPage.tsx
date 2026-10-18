import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { apiFetch } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import type { Assessment, Page } from '../../lib/types'
import { statusMeta } from '../../lib/status'

function buildQuery(status: string, search: string, page: number): string {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (search.trim()) params.set('search', search.trim())
  if (page > 1) params.set('page', String(page))
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export function AssessmentListPage() {
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState(() => searchParams.get('status') ?? '')
  const [search, setSearch] = useState('')
  const [appliedSearch, setAppliedSearch] = useState('')
  const [page, setPage] = useState(1)

  const query = useQuery({
    queryKey: ['assessments', status, appliedSearch, page],
    queryFn: () =>
      apiFetch<Page<Assessment>>(`/assessments/${buildQuery(status, appliedSearch, page)}`),
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

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Assessments</h1>
          <p className="page__subtitle">
            {query.isPending ? 'Loading assessments…' : `${count} assessment${count === 1 ? '' : 's'}`}
          </p>
        </div>
        <Link to="/training/assessments/new" className="btn btn--primary">
          New assessment
        </Link>
      </header>

      <form className="list-filters" role="search" onSubmit={onSubmit}>
        <label className="field list-filters__search">
          <span className="field__label">Search</span>
          <input
            className="field__control"
            type="search"
            placeholder="Competency or trainee"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label className="field">
          <span className="field__label">Status</span>
          <select
            className="field__control"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value)
              setPage(1)
            }}
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="submitted">Submitted</option>
            <option value="approved">Approved</option>
            <option value="needs_correction">Needs correction</option>
            <option value="rejected">Rejected</option>
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
            query.error instanceof Error ? query.error.message : 'Could not load assessments.'
          }
          onRetry={() => void query.refetch()}
        />
      ) : results.length === 0 ? (
        <EmptyState
          title="No assessments yet"
          message="Create your first assessment to get started."
          action={
            <Link to="/training/assessments/new" className="btn btn--primary btn--sm">
              New assessment
            </Link>
          }
        />
      ) : (
        <div className="record-list">
          {results.map((assessment) => {
            const meta = statusMeta('assessment', assessment.status)
            return (
              <Link
                key={assessment.id}
                to={`/training/assessments/${assessment.id}`}
                className="record-row glass"
              >
                <span className="record-row__main">
                  <span className="record-row__ref">{assessment.competency_code}</span>
                  <span className="record-row__name">
                    {assessment.trainee_detail.full_name}
                  </span>
                  <span className="record-row__meta">
                    {formatDateTime(assessment.created_at)} · Rubric v{assessment.rubric_version_number}
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
        <nav className="pagination" aria-label="Assessment pages">
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
