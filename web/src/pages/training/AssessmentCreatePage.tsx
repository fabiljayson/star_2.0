import { useMutation, useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { ApiError, apiFetch } from '../../lib/api'
import type { Assessment, Competency, Page, TrainingPlacement } from '../../lib/types'

type FieldErrors = Record<string, string>

export function AssessmentCreatePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [placementId, setPlacementId] = useState(() => searchParams.get('placement') ?? '')
  const [competencyId, setCompetencyId] = useState('')
  const [scores, setScores] = useState<Record<string, string>>({})
  const [overallLevel, setOverallLevel] = useState('')
  const [feedback, setFeedback] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)

  const placementsQuery = useQuery({
    queryKey: ['assessments-placement-options'],
    queryFn: () => apiFetch<Page<TrainingPlacement>>('/training/placements/?page_size=100'),
  })
  const competenciesQuery = useQuery({
    queryKey: ['assessments-competency-options'],
    queryFn: () => apiFetch<Page<Competency>>('/competencies/?page_size=100'),
  })

  const placements = placementsQuery.data?.results ?? []
  const selectedPlacement = placements.find((placement) => placement.id === placementId)
  const competencies = (competenciesQuery.data?.results ?? []).filter(
    (competency) =>
      competency.is_active &&
      (!selectedPlacement || competency.institution === selectedPlacement.institution),
  )
  const selectedCompetency = competencies.find((competency) => competency.id === competencyId)
  const rubric = selectedCompetency?.current_rubric ?? null
  const scale = rubric?.levels.scale ?? []
  const criteria = rubric?.levels.criteria ?? []

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<Assessment>('/assessments/', { method: 'POST', body: payload }),
    onSuccess: (assessment) => navigate(`/training/assessments/${assessment.id}`, { replace: true }),
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
        setFormError(error instanceof Error ? error.message : 'Could not create the assessment.')
      }
    },
  })

  function onPlacementChange(value: string): void {
    setPlacementId(value)
    setCompetencyId('')
    setScores({})
    setOverallLevel('')
  }

  function onCompetencyChange(value: string): void {
    setCompetencyId(value)
    setScores({})
    setOverallLevel('')
  }

  function onSubmit(event: FormEvent): void {
    event.preventDefault()
    setFormError(null)
    const next: FieldErrors = {}
    if (!placementId) next.placement = 'Choose the training placement.'
    if (!competencyId) next.competency = 'Choose the competency being assessed.'
    if (!rubric) next.competency = 'This competency has no current rubric version.'
    if (Object.values(scores).filter(Boolean).length === 0) {
      next.scores = 'Rate at least one criterion.'
    }
    if (!overallLevel) next.overall_level = 'Choose an overall level.'
    setErrors(next)
    if (Object.keys(next).length > 0) return

    createMutation.mutate({
      placement: placementId,
      competency: competencyId,
      scores: Object.fromEntries(Object.entries(scores).filter(([, value]) => value)),
      overall_level: overallLevel,
      feedback: feedback.trim(),
    })
  }

  if (placementsQuery.isError) {
    return (
      <ErrorState
        message={
          placementsQuery.error instanceof Error
            ? placementsQuery.error.message
            : 'Could not load placements.'
        }
        onRetry={() => void placementsQuery.refetch()}
      />
    )
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <Link to="/training/assessments" className="page__backlink">
            ← Assessments
          </Link>
          <h1 className="page__title">New competency assessment</h1>
          <p className="page__subtitle">
            A numeric procedure count never implies competence — rate the rubric explicitly.
          </p>
        </div>
      </header>

      <form className="form" onSubmit={onSubmit} noValidate>
        {formError && (
          <p className="form-alert" role="alert">
            {formError}
          </p>
        )}

        <Card title="Trainee and competency">
          <div className="form-grid">
            <label className="field">
              <span className="field__label">Placement *</span>
              <select
                className="field__control"
                value={placementId}
                aria-invalid={errors.placement ? true : undefined}
                onChange={(event) => onPlacementChange(event.target.value)}
              >
                <option value="">
                  {placementsQuery.isPending ? 'Loading…' : 'Choose a placement'}
                </option>
                {placements.map((placement) => (
                  <option key={placement.id} value={placement.id}>
                    {placement.trainee_detail.full_name} — {placement.title} ({placement.status})
                  </option>
                ))}
              </select>
              {errors.placement && (
                <span className="field__error" role="alert">
                  {errors.placement}
                </span>
              )}
            </label>

            <label className="field">
              <span className="field__label">Competency *</span>
              <select
                className="field__control"
                value={competencyId}
                disabled={!placementId || competenciesQuery.isPending}
                aria-invalid={errors.competency ? true : undefined}
                onChange={(event) => onCompetencyChange(event.target.value)}
              >
                <option value="">
                  {!placementId
                    ? 'Choose a placement first'
                    : competenciesQuery.isPending
                      ? 'Loading…'
                      : competencies.length === 0
                        ? 'No competencies for this institution'
                        : 'Choose a competency'}
                </option>
                {competencies.map((competency) => (
                  <option key={competency.id} value={competency.id}>
                    {competency.code} — {competency.title}
                  </option>
                ))}
              </select>
              {errors.competency && (
                <span className="field__error" role="alert">
                  {errors.competency}
                </span>
              )}
            </label>
          </div>

          {selectedPlacement && (
            <p className="field__hint">
              {selectedPlacement.trainee_detail.full_name} ·{' '}
              {selectedPlacement.institution_name}
              {selectedPlacement.supervisor_detail
                ? ` · Supervisor ${selectedPlacement.supervisor_detail.full_name}`
                : ''}
            </p>
          )}
          {selectedCompetency && !rubric && (
            <p className="form-alert" role="alert">
              {selectedCompetency.code} has no rubric version. An institution manager must publish
              one before an assessment can be scored.
            </p>
          )}
        </Card>

        {rubric && (
          <Card title={`Scoring — rubric v${rubric.version}`}>
            {criteria.length === 0 ? (
              <p className="field__hint">This rubric defines no criteria; set the overall level.</p>
            ) : (
              <div className="form-grid">
                {criteria.map((criterion) => (
                  <label className="field" key={criterion.key}>
                    <span className="field__label">{criterion.label}</span>
                    <select
                      className="field__control"
                      value={scores[criterion.key] ?? ''}
                      onChange={(event) =>
                        setScores((current) => ({
                          ...current,
                          [criterion.key]: event.target.value,
                        }))
                      }
                    >
                      <option value="">Not rated</option>
                      {scale.map((level) => (
                        <option key={level.key} value={level.key}>
                          {level.label}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
            )}
            {errors.scores && (
              <p className="field__error" role="alert">
                {errors.scores}
              </p>
            )}

            <label className="field">
              <span className="field__label">Overall level *</span>
              <select
                className="field__control"
                value={overallLevel}
                aria-invalid={errors.overall_level ? true : undefined}
                onChange={(event) => setOverallLevel(event.target.value)}
              >
                <option value="">Choose a level</option>
                {scale.map((level) => (
                  <option key={level.key} value={level.key}>
                    {level.label}
                  </option>
                ))}
              </select>
              {errors.overall_level && (
                <span className="field__error" role="alert">
                  {errors.overall_level}
                </span>
              )}
            </label>
          </Card>
        )}

        <Card title="Feedback">
          <label className="field">
            <span className="field__label">Written feedback</span>
            <textarea
              className="field__control"
              rows={5}
              value={feedback}
              onChange={(event) => setFeedback(event.target.value)}
            />
          </label>
        </Card>

        <div className="badge-row">
          <Button type="submit" loading={createMutation.isPending} disabled={!rubric}>
            Save draft assessment
          </Button>
          <Link to="/training/assessments" className="btn btn--ghost">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
