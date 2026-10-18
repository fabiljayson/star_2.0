import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { ApiError, apiFetch } from '../../lib/api'
import type { Competency, Page } from '../../lib/types'

function buildQuery(search: string, page: number): string {
  const params = new URLSearchParams()
  if (search.trim()) params.set('search', search.trim())
  if (page > 1) params.set('page', String(page))
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export function CompetencyCatalogPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [appliedSearch, setAppliedSearch] = useState('')
  const [page, setPage] = useState(1)
  const [formError, setFormError] = useState<string | null>(null)
  const [newCode, setNewCode] = useState('')
  const [newTitle, setNewTitle] = useState('')

  const query = useQuery({
    queryKey: ['competencies', appliedSearch, page],
    queryFn: () =>
      apiFetch<Page<Competency>>(`/competencies/${buildQuery(appliedSearch, page)}`),
  })

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<Competency>('/competencies/', { method: 'POST', body: payload }),
    onSuccess: () => {
      setFormError(null)
      setNewCode('')
      setNewTitle('')
      void queryClient.invalidateQueries({ queryKey: ['competencies'] })
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : 'Could not create competency.')
    },
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
  function onCreateCompetency(event: FormEvent): void {
    event.preventDefault()
    setFormError(null)
    if (!newCode.trim() || !newTitle.trim()) {
      setFormError('Code and title are required.')
      return
    }
    createMutation.mutate({ code: newCode.trim(), title: newTitle.trim() })
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Competency catalog</h1>
          <p className="page__subtitle">
            {query.isPending ? 'Loading competencies…' : `${count} competency${count === 1 ? '' : 's'} in the catalog`}
          </p>
        </div>
      </header>

      <form className="list-filters" role="search" onSubmit={onSubmit}>
        <label className="field list-filters__search">
          <span className="field__label">Search</span>
          <input
            className="field__control"
            type="search"
            placeholder="Code or title"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <Button type="submit" variant="secondary" size="sm">
          Search
        </Button>
      </form>

      {query.isPending ? (
        <div className="page-loading" role="status">
          <Spinner size="md" />
        </div>
      ) : query.isError ? (
        <ErrorState
          message={
            query.error instanceof Error ? query.error.message : 'Could not load competencies.'
          }
          onRetry={() => void query.refetch()}
        />
      ) : results.length === 0 ? (
        <EmptyState
          title="No competencies yet"
          message="The competency catalog is empty. Add your first competency below."
        />
      ) : (
        <div className="record-list">
          {results.map((competency) => (
            <Link
              key={competency.id}
              to={`/training/competencies/${competency.id}`}
              className="record-row glass"
            >
              <span className="record-row__main">
                <span className="record-row__ref">{competency.code}</span>
                <span className="record-row__name">{competency.title}</span>
                <span className="record-row__meta">
                  {competency.specialty_name || 'No specialty'}
                  {competency.institution_name ? ` · ${competency.institution_name}` : ''}
                </span>
              </span>
              <span className="record-row__side">
                <Badge tone={competency.is_active ? 'success' : 'neutral'}>
                  {competency.is_active ? 'Active' : 'Inactive'}
                </Badge>
                <span className="record-row__chevron" aria-hidden="true">
                  ›
                </span>
              </span>
            </Link>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <nav className="pagination" aria-label="Competency pages">
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

      <Card title="Add competency">
        <form className="form" onSubmit={onCreateCompetency} noValidate>
          {formError && (
            <p className="form-alert" role="alert">{formError}</p>
          )}
          <div className="form-grid">
            <label className="field">
              <span className="field__label">Code *</span>
              <input
                className="field__control"
                value={newCode}
                onChange={(event) => setNewCode(event.target.value)}
                placeholder="e.g. SURG-01"
              />
            </label>
            <label className="field">
              <span className="field__label">Title *</span>
              <input
                className="field__control"
                value={newTitle}
                onChange={(event) => setNewTitle(event.target.value)}
                placeholder="e.g. Laparoscopic cholecystectomy"
              />
            </label>
          </div>
          <div className="badge-row">
            <Button type="submit" loading={createMutation.isPending}>
              Add competency
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}
