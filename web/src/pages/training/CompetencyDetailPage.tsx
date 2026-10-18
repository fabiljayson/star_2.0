import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/context'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { ApiError, apiFetch } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import type { Competency, CompetencyRubricVersion, RubricContent } from '../../lib/types'

export function CompetencyDetailPage() {
  const { id = '' } = useParams()
  const { hasRole } = useAuth()
  const queryClient = useQueryClient()

  const canManage = hasRole('department_manager') || hasRole('institution_admin')

  const [notes, setNotes] = useState('')
  const [levelsText, setLevelsText] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const competencyQuery = useQuery({
    queryKey: ['competency', id],
    queryFn: () => apiFetch<Competency>(`/competencies/${id}/`),
    enabled: Boolean(id),
  })
  const versionsQuery = useQuery({
    queryKey: ['competency-rubrics', id],
    queryFn: () => apiFetch<CompetencyRubricVersion[]>(`/competencies/${id}/rubric-versions/`),
    enabled: Boolean(id),
  })

  const createRubric = useMutation({
    mutationFn: (payload: { levels: RubricContent; notes: string }) =>
      apiFetch<CompetencyRubricVersion>(`/competencies/${id}/rubric-versions/`, {
        method: 'POST',
        body: payload,
      }),
    onSuccess: () => {
      setNotes('')
      setLevelsText('')
      setFormError(null)
      void queryClient.invalidateQueries({ queryKey: ['competency', id] })
      void queryClient.invalidateQueries({ queryKey: ['competency-rubrics', id] })
      void queryClient.invalidateQueries({ queryKey: ['competencies'] })
    },
    onError: (error) =>
      setFormError(error instanceof ApiError ? error.message : 'Could not publish the rubric.'),
  })

  if (competencyQuery.isPending) {
    return (
      <div className="page-loading" role="status">
        <Spinner size="md" label="Loading competency…" />
      </div>
    )
  }
  if (competencyQuery.isError) {
    const error = competencyQuery.error
    if (error instanceof ApiError && error.status === 404) {
      return (
        <div className="page">
          <div className="state-block state-block--error" role="alert">
            <h3 className="state-block__title">Competency not found</h3>
            <p className="state-block__message">
              This competency does not exist or is outside your access.
            </p>
            <Link to="/training/competencies" className="btn btn--secondary btn--sm">
              Back to catalog
            </Link>
          </div>
        </div>
      )
    }
    return (
      <ErrorState
        message={error instanceof Error ? error.message : 'Could not load the competency.'}
        onRetry={() => void competencyQuery.refetch()}
      />
    )
  }

  const competency = competencyQuery.data
  const versions = versionsQuery.data ?? []
  const current = competency.current_rubric

  function onPublish(event: FormEvent): void {
    event.preventDefault()
    setFormError(null)
    let parsed: RubricContent
    try {
      parsed = JSON.parse(levelsText) as RubricContent
    } catch {
      setFormError('The rubric definition must be valid JSON.')
      return
    }
    if (!parsed.scale || parsed.scale.length === 0) {
      setFormError('A rubric needs at least one rating level in "scale".')
      return
    }
    createRubric.mutate({ levels: parsed, notes: notes.trim() })
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <Link to="/training/competencies" className="page__backlink">
            ← Competency catalog
          </Link>
          <h1 className="page__title">
            {competency.code} — {competency.title}
          </h1>
          <p className="page__subtitle">
            {competency.institution_name}
            {competency.specialty_name ? ` · ${competency.specialty_name}` : ''}
          </p>
        </div>
        <div className="badge-row">
          <Badge tone={competency.is_active ? 'success' : 'neutral'}>
            {competency.is_active ? 'Active' : 'Inactive'}
          </Badge>
          {current && <Badge tone="info">Rubric v{current.version}</Badge>}
        </div>
      </header>

      <div className="account-grid">
        <Card title="Description">
          {competency.description ? (
            <p>{competency.description}</p>
          ) : (
            <p className="field__hint">No description recorded.</p>
          )}
        </Card>

        <Card title="Current rubric">
          {!current ? (
            <p className="field__hint">
              No rubric version exists yet. Assessments cannot be scored until one is published.
            </p>
          ) : (
            <>
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Rating scale</th>
                      <th className="num">Rank</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(current.levels.scale ?? []).map((level) => (
                      <tr key={level.key}>
                        <td>
                          {level.label} <span className="field__hint">({level.key})</span>
                        </td>
                        <td className="num">{level.rank ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {(current.levels.criteria ?? []).length > 0 && (
                <ul className="role-list">
                  {(current.levels.criteria ?? []).map((criterion) => (
                    <li key={criterion.key}>
                      <strong>{criterion.label}</strong>
                      <span className="field__hint">key: {criterion.key}</span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </Card>
      </div>

      <Card title="Rubric version history">
        {versionsQuery.isPending ? (
          <div className="page-loading" role="status">
            <Spinner size="md" />
          </div>
        ) : versionsQuery.isError ? (
          <ErrorState
            message={
              versionsQuery.error instanceof Error
                ? versionsQuery.error.message
                : 'Could not load rubric versions.'
            }
            onRetry={() => void versionsQuery.refetch()}
          />
        ) : versions.length === 0 ? (
          <p className="field__hint">No versions published yet.</p>
        ) : (
          <ul className="role-list">
            {versions.map((version) => (
              <li key={version.id}>
                <span className="badge-row">
                  <strong>v{version.version}</strong>
                  {version.is_current && <Badge tone="info">Current</Badge>}
                  <span className="field__hint">{formatDateTime(version.created_at)}</span>
                </span>
                {version.notes && <span className="field__hint">{version.notes}</span>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {canManage && (
        <Card title="Publish a new rubric version">
          <form className="form" onSubmit={onPublish} noValidate>
            {formError && (
              <p className="form-alert" role="alert">
                {formError}
              </p>
            )}
            <p className="field__hint">
              Published versions are immutable; existing assessments keep the version they were
              scored against.
            </p>
            <label className="field">
              <span className="field__label">Change notes</span>
              <textarea
                className="field__control"
                rows={3}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field__label">Rubric definition (JSON) *</span>
              <textarea
                className="field__control field__control--code"
                rows={10}
                value={levelsText}
                placeholder='{"scale": [{"key": "novice", "label": "Novice", "rank": 1}], "criteria": [{"key": "technique", "label": "Operative technique"}]}'
                onChange={(event) => setLevelsText(event.target.value)}
              />
            </label>
            <div className="badge-row">
              <Button
                type="button"
                variant="secondary"
                onClick={() =>
                  setLevelsText(
                    JSON.stringify(
                      current?.levels ?? {
                        scale: [
                          { key: 'novice', label: 'Novice', rank: 1 },
                          { key: 'competent', label: 'Competent', rank: 2 },
                          { key: 'expert', label: 'Expert', rank: 3 },
                        ],
                        criteria: [{ key: 'technique', label: 'Operative technique' }],
                      },
                      null,
                      2,
                    ),
                  )
                }
              >
                Load {current ? 'current' : 'starter'} rubric
              </Button>
              <Button type="submit" loading={createRubric.isPending}>
                Publish version
              </Button>
            </div>
          </form>
        </Card>
      )}
    </div>
  )
}
