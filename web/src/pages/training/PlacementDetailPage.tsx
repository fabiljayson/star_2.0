import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/context'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { ApiError, apiFetch } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { initialsOf } from '../../lib/roles'
import type {
  ExaminerAssignment,
  Page,
  TrainingPlacement,
  UserSummary,
} from '../../lib/types'
import { statusMeta } from '../../lib/status'

export function PlacementDetailPage() {
  const { id = '' } = useParams()
  const { user, hasRole } = useAuth()
  const queryClient = useQueryClient()

  const [editError, setEditError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [examinerSearch, setExaminerSearch] = useState('')
  const [editTitle, setEditTitle] = useState('')
  const [editObjectives, setEditObjectives] = useState('')

  const isTrainee = hasRole('trainee')
  const isSupervisor = hasRole('supervisor')
  const isAdmin = hasRole('institution_admin') || hasRole('department_manager') || user?.is_platform_admin

  const placementQuery = useQuery({
    queryKey: ['placement', id],
    queryFn: () => apiFetch<TrainingPlacement>(`/training/placements/${id}/`),
    enabled: Boolean(id),
  })
  const examinersQuery = useQuery({
    queryKey: ['placement-examiners', id],
    queryFn: () => apiFetch<ExaminerAssignment[]>(`/training/placements/${id}/examiners/`),
    enabled: Boolean(id),
  })
  const progressQuery = useQuery({
    queryKey: ['placement-progress', id],
    queryFn: () => apiFetch<Record<string, unknown>>(`/training/placements/${id}/progress/`),
    enabled: Boolean(id),
  })
  const userSearchQuery = useQuery({
    queryKey: ['users-search', examinerSearch],
    queryFn: () =>
      apiFetch<Page<UserSummary>>(`/users/?search=${encodeURIComponent(examinerSearch)}`),
    enabled: examinerSearch.trim().length >= 2,
  })

  const invalidate = (): void => {
    void queryClient.invalidateQueries({ queryKey: ['placement', id] })
    void queryClient.invalidateQueries({ queryKey: ['placements'] })
    void queryClient.invalidateQueries({ queryKey: ['placement-examiners', id] })
    void queryClient.invalidateQueries({ queryKey: ['placement-progress', id] })
  }

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<TrainingPlacement>(`/training/placements/${id}/`, {
        method: 'PATCH',
        body: payload,
      }),
    onSuccess: () => {
      setEditTitle('')
      setEditObjectives('')
      setEditError(null)
      invalidate()
    },
    onError: (error) => setEditError(error instanceof ApiError ? error.message : 'Update failed.'),
  })
  const completeMutation = useMutation({
    mutationFn: () =>
      apiFetch<TrainingPlacement>(`/training/placements/${id}/complete/`, { method: 'POST' }),
    onSuccess: invalidate,
    onError: (error) => setActionError(error instanceof ApiError ? error.message : 'Complete failed.'),
  })
  const cancelMutation = useMutation({
    mutationFn: (reason: string) =>
      apiFetch<TrainingPlacement>(`/training/placements/${id}/cancel/`, {
        method: 'POST',
        body: { reason },
      }),
    onSuccess: invalidate,
    onError: (error) => setActionError(error instanceof ApiError ? error.message : 'Cancel failed.'),
  })
  const addExaminerMutation = useMutation({
    mutationFn: (examinerId: string) =>
      apiFetch<ExaminerAssignment>(`/training/placements/${id}/examiners/`, {
        method: 'POST',
        body: { examiner: examinerId },
      }),
    onSuccess: () => {
      setExaminerSearch('')
      invalidate()
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : 'Could not assign examiner.'),
  })
  const removeExaminerMutation = useMutation({
    mutationFn: (assignmentId: string) =>
      apiFetch<void>(`/training/placements/${id}/examiners/${assignmentId}/`, { method: 'DELETE' }),
    onSuccess: invalidate,
    onError: (error) => setActionError(error instanceof ApiError ? error.message : 'Could not remove examiner.'),
  })

  if (placementQuery.isPending) {
    return (
      <div className="page-loading" role="status">
        <Spinner size="md" label="Loading placement…" />
      </div>
    )
  }
  if (placementQuery.isError) {
    const error = placementQuery.error
    if (error instanceof ApiError && error.status === 404) {
      return (
        <div className="page">
          <div className="state-block state-block--error" role="alert">
            <h3 className="state-block__title">Placement not found</h3>
            <p className="state-block__message">
              This placement does not exist or is outside your access.
            </p>
            <Link to="/training" className="btn btn--secondary btn--sm">
              Back to placements
            </Link>
          </div>
        </div>
      )
    }
    return (
      <ErrorState
        message={error instanceof Error ? error.message : 'Could not load the placement.'}
        onRetry={() => void placementQuery.refetch()}
      />
    )
  }

  const placement = placementQuery.data
  const examiners = examinersQuery.data ?? []
  const progress = progressQuery.data ?? {}
  const meta = statusMeta('placement', placement.status)
  const isTraineeOwner = Boolean(user && isTrainee && placement.trainee === user.id)
  const isSupervisorOf = Boolean(
    user && isSupervisor && placement.supervisor === user.id && placement.institution === user.roles.find((r) => r.is_active)?.institution,
  )
  const canEdit = isTraineeOwner && placement.status === 'active'
  const canComplete = isSupervisorOf && placement.status === 'active'
  const canCancel = (isTraineeOwner || isSupervisorOf || isAdmin) && placement.status === 'active'
  const canManageExaminers = isSupervisorOf || isAdmin
  const canAssess =
    placement.status === 'active' &&
    (isAdmin || isSupervisor || hasRole('examiner')) &&
    placement.trainee !== user?.id

  const searchResults = userSearchQuery.data?.results ?? []

  function onSave(event: FormEvent): void {
    event.preventDefault()
    const payload: Record<string, unknown> = {}
    if (editTitle.trim()) payload.title = editTitle.trim()
    if (editObjectives.trim()) payload.objectives = editObjectives.trim()
    if (Object.keys(payload).length === 0) return
    updateMutation.mutate(payload)
  }

  function onAssignExaminer(event: FormEvent): void {
    event.preventDefault()
    const pick = searchResults[0]
    if (!pick) {
      setActionError('Search for an examiner and pick them first.')
      return
    }
    addExaminerMutation.mutate(pick.id)
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <Link to="/training" className="page__backlink">
            ← Placements
          </Link>
          <h1 className="page__title">{placement.title}</h1>
          <p className="page__subtitle">
            {placement.institution_name}
            {placement.department_name ? ` · ${placement.department_name}` : ''}
          </p>
        </div>
        <div className="badge-row">
          <Badge tone={meta.tone}>{meta.label}</Badge>
          <Badge tone="neutral">
            {placement.trainee_detail.full_name}
          </Badge>
        </div>
      </header>

      {actionError && (
        <p className="form-alert" role="alert">{actionError}</p>
      )}

      <div className="badge-row detail-actions">
        {canEdit && (
          <Button variant="secondary" onClick={() => {
            setEditTitle(placement.title)
            setEditObjectives(placement.objectives)
            setEditError(null)
          }}>
            Edit placement
          </Button>
        )}
        {canComplete && (
          <Button
            variant="primary"
            loading={completeMutation.isPending}
            onClick={() => completeMutation.mutate()}
          >
            Mark complete
          </Button>
        )}
        {canCancel && (
          <Button variant="secondary" loading={cancelMutation.isPending} onClick={() => {
            const reason = window.prompt('Cancellation reason (optional)')
            if (reason !== null) cancelMutation.mutate(reason)
          }}>
            Cancel placement
          </Button>
        )}
        {canAssess && (
          <Link
            to={`/training/assessments/new?placement=${placement.id}`}
            className="btn btn--secondary btn--sm"
          >
            New assessment
          </Link>
        )}
        {canManageExaminers && (
          <Button variant="secondary" onClick={() => {
            setExaminerSearch('')
            setActionError(null)
          }}>
            Assign examiner
          </Button>
        )}
      </div>

      <div className="account-grid">
        <Card title="Placement details">
          <dl className="definition-list">
            <dt>Trainee</dt>
            <dd>{placement.trainee_detail.full_name}</dd>
            {placement.supervisor_detail && (
              <>
                <dt>Supervisor</dt>
                <dd>{placement.supervisor_detail.full_name}</dd>
              </>
            )}
            <dt>Institution</dt>
            <dd>{placement.institution_name}</dd>
            {placement.department_name && (
              <>
                <dt>Department</dt>
                <dd>{placement.department_name}</dd>
              </>
            )}
            <dt>Start date</dt>
            <dd>{formatDate(placement.start_date)}</dd>
            {placement.end_date && (
              <>
                <dt>End date</dt>
                <dd>{formatDate(placement.end_date)}</dd>
              </>
            )}
            <dt>Status</dt>
            <dd>{meta.label}</dd>
            {placement.objectives && (
              <>
                <dt>Objectives</dt>
                <dd>{placement.objectives}</dd>
              </>
            )}
          </dl>
        </Card>

        <Card title="Expected competencies">
          {placement.expected_competencies.length === 0 ? (
            <p className="field__hint">No competencies linked yet.</p>
          ) : (
            <ul className="role-list">
              {placement.expected_competencies.map((comp) => (
                <li key={comp.id}>
                  <span className="badge-row">
                    <strong>{comp.code}</strong>
                    <Badge tone="info">{comp.title}</Badge>
                  </span>
                  <span className="field__hint">{comp.description || '—'}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {canEdit && (
        <form className="form" onSubmit={onSave} noValidate>
          <Card title="Edit placement">
            {editError && (
              <p className="form-alert" role="alert">{editError}</p>
            )}
            <div className="form-grid">
              <label className="field">
                <span className="field__label">Title</span>
                <input
                  className="field__control"
                  value={editTitle}
                  onChange={(event) => setEditTitle(event.target.value)}
                />
              </label>
            </div>
            <label className="field">
              <span className="field__label">Objectives</span>
              <textarea
                className="field__control"
                rows={4}
                value={editObjectives}
                onChange={(event) => setEditObjectives(event.target.value)}
              />
            </label>
            <div className="badge-row">
              <Button type="submit" loading={updateMutation.isPending}>
                Save changes
              </Button>
              <Button variant="ghost" type="button" onClick={() => {
                setEditTitle('')
                setEditObjectives('')
                setEditError(null)
              }}>
                Cancel
              </Button>
            </div>
          </Card>
        </form>
      )}

      <div className="account-grid">
        <Card title="Examiners">
          {examiners.length === 0 ? (
            <p className="field__hint">No examiners assigned yet.</p>
          ) : (
            <ul className="role-list">
              {examiners.map((assignment) => (
                <li key={assignment.id} className="participant-row">
                  <span>
                    <strong>{assignment.examiner_detail.full_name}</strong>{' '}
                    <Badge tone="info">{initialsOf(assignment.examiner_detail.full_name)}</Badge>
                  </span>
                  {canManageExaminers && (
                    <Button
                      variant="danger"
                      size="sm"
                      loading={removeExaminerMutation.isPending}
                      onClick={() => removeExaminerMutation.mutate(assignment.id)}
                    >
                      Remove
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {canManageExaminers && (
            <div className="participant-add">
              <form className="form" onSubmit={onAssignExaminer}>
                <div className="form-grid">
                  <label className="field">
                    <span className="field__label">Find an examiner</span>
                    <input
                      className="field__control"
                      type="search"
                      placeholder="Name or email"
                      value={examinerSearch}
                      onChange={(event) => setExaminerSearch(event.target.value)}
                    />
                  </label>
                </div>
                {searchResults.length > 0 && (
                  <ul className="search-results">
                    {searchResults.slice(0, 5).map((candidate) => (
                      <li key={candidate.id}>
                        {candidate.full_name} — {candidate.email}
                      </li>
                    ))}
                  </ul>
                )}
                <div className="badge-row">
                  <Button type="submit" variant="secondary" size="sm">
                    Add first result
                  </Button>
                </div>
              </form>
            </div>
          )}
        </Card>

        <Card title="Placement progress">
          <dl className="definition-list">
            <dt>Procedures performed</dt>
            <dd>{String(progress.procedures_performed ?? 0)}</dd>
            <dt>Procedures assisted</dt>
            <dd>{String(progress.procedures_assisted ?? 0)}</dd>
            <dt>Procedures observed</dt>
            <dd>{String(progress.procedures_observed ?? 0)}</dd>
            <dt>Records awaiting review</dt>
            <dd>{String(progress.records_awaiting_review ?? 0)}</dd>
            <dt>Approved records</dt>
            <dd>{String(progress.approved_records ?? 0)}</dd>
            <dt>Rejected records</dt>
            <dd>{String(progress.rejected_records ?? 0)}</dd>
            <dt>Completion</dt>
            <dd>
              {String(progress.placement_completion ?? 0)}%
            </dd>
          </dl>
        </Card>
      </div>
    </div>
  )
}
