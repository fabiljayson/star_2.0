import { useMutation, useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/context'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { TextField } from '../../components/TextField'
import { ApiError, apiFetch } from '../../lib/api'
import { todayIsoDate } from '../../lib/format'
import { roleLabel } from '../../lib/roles'
import type {
  Competency,
  Department,
  Institution,
  Page,
  TrainingPlacement,
  UserSummary,
} from '../../lib/types'

type FieldErrors = Record<string, string>

function hasInstitutionRole(user: UserSummary | null, role: string, institution: string): boolean {
  if (!user) return false
  return user.roles.some(
    (assignment) =>
      assignment.is_active && assignment.role === role && assignment.institution === institution,
  )
}

export function PlacementCreatePage() {
  const navigate = useNavigate()
  const { user, hasRole } = useAuth()

  const isPlatformAdmin = Boolean(user?.is_platform_admin)
  const administeredIds = (user?.roles ?? [])
    .filter((assignment) => assignment.is_active && assignment.role === 'institution_admin')
    .map((assignment) => assignment.institution)
    .filter((value): value is string => Boolean(value))

  const institutionsQuery = useQuery({
    queryKey: ['institutions'],
    queryFn: () => apiFetch<Page<Institution>>('/institutions/?page_size=100'),
    enabled: isPlatformAdmin || administeredIds.length > 0,
  })

  const [institution, setInstitution] = useState('')
  const [department, setDepartment] = useState('')
  const [title, setTitle] = useState('')
  const [trainee, setTrainee] = useState('')
  const [supervisor, setSupervisor] = useState('')
  const [startDate, setStartDate] = useState(todayIsoDate())
  const [endDate, setEndDate] = useState('')
  const [objectives, setObjectives] = useState('')
  const [competencyIds, setCompetencyIds] = useState<string[]>([])
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)

  const departmentsQuery = useQuery({
    queryKey: ['departments', institution],
    queryFn: () => apiFetch<Page<Department>>(`/departments/?institution=${institution}&page_size=100`),
    enabled: Boolean(institution),
  })
  const usersQuery = useQuery({
    queryKey: ['institution-users', institution],
    queryFn: () => apiFetch<Page<UserSummary>>(`/users/?institution=${institution}&page_size=100`),
    enabled: Boolean(institution),
  })
  const competenciesQuery = useQuery({
    queryKey: ['competencies', institution],
    queryFn: () =>
      apiFetch<Page<Competency>>(`/competencies/?institution=${institution}&page_size=100`),
    enabled: Boolean(institution),
  })

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<TrainingPlacement>('/training/placements/', { method: 'POST', body: payload }),
    onSuccess: (placement) => navigate(`/training/placements/${placement.id}`, { replace: true }),
    onError: (error) => {
      if (error instanceof ApiError && typeof error.details === 'object' && error.details) {
        const details = error.details as Record<string, unknown>
        const mapped: FieldErrors = {}
        for (const [key, value] of Object.entries(details)) {
          mapped[key] = Array.isArray(value) ? String(value[0]) : String(value)
        }
        setErrors(mapped)
        setFormError(mapped.non_field_errors ?? (Object.keys(mapped).length === 0 ? error.message : null))
      } else {
        setFormError(error instanceof Error ? error.message : 'Could not create the placement.')
      }
    },
  })

  const canCreate = isPlatformAdmin || administeredIds.length > 0

  if (!hasRole('institution_admin') && !isPlatformAdmin) {
    return (
      <div className="page">
        <div className="state-block state-block--error" role="alert">
          <h3 className="state-block__title">Institution administrator access required</h3>
          <p className="state-block__message">
            Creating a training placement needs the trainee and supervisor directory of an
            institution. Ask an institution administrator to create it, or to grant you that role.
          </p>
          <Link to="/training" className="btn btn--secondary btn--sm">
            Back to placements
          </Link>
        </div>
      </div>
    )
  }

  if (institutionsQuery.isError) {
    return (
      <ErrorState
        message="Could not load institutions. Retry to continue."
        onRetry={() => void institutionsQuery.refetch()}
      />
    )
  }

  const institutions = (institutionsQuery.data?.results ?? []).filter(
    (item) => isPlatformAdmin || administeredIds.includes(item.id),
  )
  const departments = departmentsQuery.data?.results ?? []
  const users = usersQuery.data?.results ?? []
  const traineeOptions = users.filter((candidate) =>
    hasInstitutionRole(candidate, 'trainee', institution),
  )
  const supervisorOptions = users.filter((candidate) =>
    hasInstitutionRole(candidate, 'supervisor', institution),
  )
  const competencies = competenciesQuery.data?.results ?? []

  function onSubmit(event: FormEvent): void {
    event.preventDefault()
    setFormError(null)
    const next: FieldErrors = {}
    if (!institution) next.institution = 'Choose an institution.'
    if (!title.trim()) next.title = 'A short placement title is required.'
    if (!trainee) next.trainee = 'Choose the trainee.'
    if (!startDate) next.start_date = 'A start date is required.'
    if (endDate && endDate < startDate) next.end_date = 'The end date must not precede the start date.'
    setErrors(next)
    if (Object.keys(next).length > 0) return

    const payload: Record<string, unknown> = {
      institution,
      title: title.trim(),
      trainee,
      start_date: startDate,
      objectives: objectives.trim(),
    }
    if (department) payload.department = department
    if (supervisor) payload.supervisor = supervisor
    if (endDate) payload.end_date = endDate
    if (competencyIds.length > 0) payload.expected_competency_ids = competencyIds

    createMutation.mutate(payload)
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <Link to="/training" className="page__backlink">
            ← Placements
          </Link>
          <h1 className="page__title">New training placement</h1>
          <p className="page__subtitle">
            A trainee can hold one active placement at a time; supervisors and examiners are
            institution-scoped.
          </p>
        </div>
      </header>

      <form className="form" onSubmit={onSubmit} noValidate>
        {formError && (
          <p className="form-alert" role="alert">
            {formError}
          </p>
        )}

        <Card title="Placement scope">
          <div className="form-grid">
            <label className="field">
              <span className="field__label">Institution *</span>
              <select
                className="field__control"
                value={institution}
                aria-invalid={errors.institution ? true : undefined}
                onChange={(event) => {
                  setInstitution(event.target.value)
                  setDepartment('')
                  setTrainee('')
                  setSupervisor('')
                  setCompetencyIds([])
                }}
              >
                <option value="">
                  {institutionsQuery.isPending ? 'Loading…' : 'Choose an institution'}
                </option>
                {institutions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
              {errors.institution && (
                <span className="field__error" role="alert">
                  {errors.institution}
                </span>
              )}
            </label>

            <label className="field">
              <span className="field__label">Department</span>
              <select
                className="field__control"
                value={department}
                disabled={!institution || departmentsQuery.isPending}
                onChange={(event) => setDepartment(event.target.value)}
              >
                <option value="">None</option>
                {departments.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>

            <TextField
              label="Title *"
              name="title"
              value={title}
              error={errors.title}
              placeholder="e.g. Upper GI rotation 2026"
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>
        </Card>

        <Card title="People">
          {institution && usersQuery.isError ? (
            <p className="form-alert" role="alert">
              Could not load the institution directory. You need institution administrator access
              for this institution.
            </p>
          ) : null}
          <div className="form-grid">
            <label className="field">
              <span className="field__label">Trainee *</span>
              <select
                className="field__control"
                value={trainee}
                disabled={!institution || usersQuery.isPending}
                aria-invalid={errors.trainee ? true : undefined}
                onChange={(event) => setTrainee(event.target.value)}
              >
                <option value="">
                  {!institution
                    ? 'Choose an institution first'
                    : usersQuery.isPending
                      ? 'Loading…'
                      : traineeOptions.length === 0
                        ? 'No trainee accounts found'
                        : 'Choose the trainee'}
                </option>
                {traineeOptions.map((candidate) => (
                  <option key={candidate.id} value={String(candidate.id)}>
                    {candidate.full_name} — {candidate.email}
                  </option>
                ))}
              </select>
              {errors.trainee && (
                <span className="field__error" role="alert">
                  {errors.trainee}
                </span>
              )}
            </label>

            <label className="field">
              <span className="field__label">Supervisor</span>
              <select
                className="field__control"
                value={supervisor}
                disabled={!institution || usersQuery.isPending}
                onChange={(event) => setSupervisor(event.target.value)}
              >
                <option value="">None</option>
                {supervisorOptions.map((candidate) => (
                  <option key={candidate.id} value={String(candidate.id)}>
                    {candidate.full_name} — {candidate.email}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </Card>

        <Card title="Schedule and objectives">
          <div className="form-grid">
            <TextField
              label="Start date *"
              type="date"
              name="start_date"
              value={startDate}
              error={errors.start_date}
              onChange={(event) => setStartDate(event.target.value)}
            />
            <TextField
              label="End date"
              type="date"
              name="end_date"
              value={endDate}
              error={errors.end_date}
              onChange={(event) => setEndDate(event.target.value)}
            />
          </div>
          <label className="field">
            <span className="field__label">Objectives</span>
            <textarea
              className="field__control"
              rows={4}
              value={objectives}
              onChange={(event) => setObjectives(event.target.value)}
            />
          </label>
        </Card>

        <Card title="Expected competencies">
          {!institution ? (
            <p className="field__hint">Choose an institution to list its competency catalog.</p>
          ) : competenciesQuery.isPending ? (
            <p className="field__hint">Loading competencies…</p>
          ) : competencies.length === 0 ? (
            <p className="field__hint">
              This institution has no active competencies yet. The placement can be saved without
              them.
            </p>
          ) : (
            <ul className="checkbox-list">
              {competencies.map((competency) => (
                <li key={competency.id}>
                  <label className="checkbox-field">
                    <input
                      type="checkbox"
                      checked={competencyIds.includes(competency.id)}
                      onChange={(event) => {
                        setCompetencyIds((current) =>
                          event.target.checked
                            ? [...current, competency.id]
                            : current.filter((value) => value !== competency.id),
                        )
                      }}
                    />
                    <span>
                      <strong>{competency.code}</strong> — {competency.title}
                      <span className="field__hint">
                        {competency.specialty_name ?? 'No specialty'} ·{' '}
                        {competency.current_rubric
                          ? `Rubric v${competency.current_rubric.version}`
                          : 'No rubric yet'}
                      </span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          <p className="field__hint">
            Role labels: {roleLabel('trainee')}, {roleLabel('supervisor')}.
          </p>
        </Card>

        <div className="badge-row">
          <Button type="submit" loading={createMutation.isPending} disabled={!canCreate}>
            Create placement
          </Button>
          <Link to="/training" className="btn btn--ghost">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
