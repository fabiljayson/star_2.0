import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { apiFetch } from '../../lib/api'
import { formatDate } from '../../lib/format'
import type { Page, SurgicalProcedure } from '../../lib/types'
import { PROCEDURE_STATUSES, statusMeta } from '../../lib/status'

function buildQuery(status: string, mine: boolean, search: string, page: number): string {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (mine) params.set('mine', '1')
  if (search.trim()) params.set('search', search.trim())
  if (page > 1) params.set('page', String(page))
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export function LogbookListPage() {
  const [status, setStatus] = useState('')
  const [mine, setMine] = useState(false)
  const [search, setSearch] = useState('')
  const [appliedSearch, setAppliedSearch] = useState('')
  const [page, setPage] = useState(1)

  const query = useQuery({
    queryKey: ['procedures', status, mine, appliedSearch, page],
    queryFn: () =>
      apiFetch<Page<SurgicalProcedure>>(`/procedures/${buildQuery(status, mine, appliedSearch, page)}`),
  })

  const results = query.data?.results ?? []
  const count = query.data?.count ?? 0
  const pageSize = 20
  const totalPages = Math.max(1, Math.ceil(count / pageSize))

  function onSearchSubmit(event: React.FormEvent): void {
    event.preventDefault()
    setPage(1)
    setAppliedSearch(search)
  }

  function resetFilters(): void {
    setStatus('')
    setMine(false)
    setSearch('')
    setAppliedSearch('')
    setPage(1)
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Surgical logbook</h1>
          <p className="page__subtitle">
            {query.isPending ? 'Loading records…' : `${count} record${count === 1 ? '' : 's'}`}
          </p>
        </div>
        <Link to="/logbook/new" className="btn btn--primary">
          New record
        </Link>
      </header>

      <form className="list-filters" role="search" onSubmit={onSearchSubmit}>
        <label className="field list-filters__search">
          <span className="field__label">Search</span>
          <input
            className="field__control"
            type="search"
            placeholder="Reference or procedure name"
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
            {PROCEDURE_STATUSES.map((value) => (
              <option key={value} value={value}>
                {statusMeta('procedure', value).label}
              </option>
            ))}
          </select>
        </label>
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={mine}
            onChange={(event) => {
              setMine(event.target.checked)
              setPage(1)
            }}
          />
          Only mine
        </label>
        <Button type="submit" variant="secondary" size="sm">
          Apply
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={resetFilters}>
          Reset
        </Button>
      </form>

      {query.isPending ? (
        <div className="page-loading" role="status">
          <Spinner size="md" />
        </div>
      ) : query.isError ? (
        <ErrorState
          message={query.error instanceof Error ? query.error.message : 'Could not load records.'}
          onRetry={() => void query.refetch()}
        />
      ) : results.length === 0 ? (
        <EmptyState
          title="No procedures yet"
          message="Create your first surgical record to start your logbook."
          action={
            <Link to="/logbook/new" className="btn btn--primary btn--sm">
              New record
            </Link>
          }
        />
      ) : (
        <div className="record-list">
          {results.map((procedure) => {
            const meta = statusMeta('procedure', procedure.status)
            return (
              <Link
                key={procedure.id}
                to={`/logbook/${procedure.id}`}
                className="record-row glass"
              >
                <span className="record-row__main">
                  <span className="record-row__ref">{procedure.reference}</span>
                  <span className="record-row__name">{procedure.procedure_name}</span>
                  <span className="record-row__meta">
                    {formatDate(procedure.procedure_date)} · {procedure.institution_name}
                    {procedure.author_detail.id ? ` · ${procedure.author_detail.full_name}` : ''}
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
        <nav className="pagination" aria-label="Logbook pages">
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
