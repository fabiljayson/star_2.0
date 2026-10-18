import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/context'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { Modal } from '../../components/Modal'
import { Spinner } from '../../components/Spinner'
import { ApiError, apiFetch } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import type { Assessment } from '../../lib/types'
import { statusMeta } from '../../lib/status'

const DECISIONS: { value: string; label: string; needsReason: boolean }[] = [
  { value: 'approved', label: 'Approve', needsReason: false },
  { value: 'needs_correction', label: 'Request correction', needsReason: true },
  { value: 'rejected', label: 'Reject', needsReason: true },
]

export function AssessmentDetailPage() {
  const { id = '' } = useParams()
  const { user, hasRole } = useAuth()
  const queryClient = useQueryClient()

  const [actionError, setActionError] = useState<string | null>(null)
  const [decisionModal, setDecisionModal] = useState<string | null>(null)
  const [decisionReason, setDecisionReason] = useState('')
  const [decisionFeedback, setDecisionFeedback] = useState('')
  const [editFeedback, setEditFeedback] = useState('')

  const isExaminer = hasRole('examiner')
  const isSupervisor = hasRole('supervisor')
  const canDecide = isExaminer || isSupervisor

  const assessmentQuery = useQuery({
    queryKey: ['assessment', id],
    queryFn: () => apiFetch<Assessment>(`/assessments/${id}/`),
    enabled: Boolean(id),
  })

  const invalidate = (): void => {
    void queryClient.invalidateQueries({ queryKey: ['assessment', id] })
    void queryClient.invalidateQueries({ queryKey: ['assessments'] })
  }

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<Assessment>(`/assessments/${id}/`, { method: 'PATCH', body: payload }),
    onSuccess: () => {
      setEditFeedback('')
      invalidate()
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : 'Update failed.'),
  })
  const submitMutation = useMutation({
    mutationFn: () => apiFetch<Assessment>(`/assessments/${id}/submit/`, { method: 'POST' }),
    onSuccess: invalidate,
    onError: (error) => setActionError(error instanceof ApiError ? error.message : 'Submit failed.'),
  })
  const decideMutation = useMutation({
    mutationFn: (payload: { decision: string; reason?: string; feedback?: string }) =>
      apiFetch<Assessment>(`/assessments/${id}/decide/`, {
        method: 'POST',
        body: payload,
      }),
    onSuccess: () => {
      setDecisionModal(null)
      setDecisionReason('')
      setDecisionFeedback('')
      invalidate()
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : 'Decision failed.'),
  })

  if (assessmentQuery.isPending) {
    return (
      <div className="page-loading" role="status">
        <Spinner size="md" label="Loading assessment…" />
      </div>
    )
  }
  if (assessmentQuery.isError) {
    const error = assessmentQuery.error
    if (error instanceof ApiError && error.status === 404) {
      return (
        <div className="page">
          <div className="state-block state-block--error" role="alert">
            <h3 className="state-block__title">Assessment not found</h3>
            <p className="state-block__message">
              This assessment does not exist or is outside your access.
            </p>
            <Link to="/training/assessments" className="btn btn--secondary btn--sm">
              Back to assessments
            </Link>
          </div>
        </div>
      )
    }
    return (
      <ErrorState
        message={error instanceof Error ? error.message : 'Could not load the assessment.'}
        onRetry={() => void assessmentQuery.refetch()}
      />
    )
  }

  const assessment = assessmentQuery.data
  const meta = statusMeta('assessment', assessment.status)
  const isAuthor = Boolean(user && assessment.assessor === user.id)
  const editable = ['draft', 'needs_correction'].includes(assessment.status)
  const canEdit = isAuthor && editable
  const canSubmit = isAuthor && assessment.status === 'draft'
  const canDecideNow = canDecide && assessment.status === 'submitted'

  const scoreKeys = Object.keys(assessment.scores)

  function onSaveFeedback(event: FormEvent): void {
    event.preventDefault()
    updateMutation.mutate({ feedback: editFeedback.trim() })
  }

  function onSubmitAssessment(): void {
    submitMutation.mutate()
  }

  function onDecide(event: FormEvent): void {
    event.preventDefault()
    if (!decisionModal) return
    const decision = DECISIONS.find((d) => d.value === decisionModal)
    if (!decision) return
    if (decision.needsReason && !decisionReason.trim()) {
      setActionError('A reason is required for this decision.')
      return
    }
    decideMutation.mutate({
      decision: decisionModal,
      reason: decisionReason.trim(),
      feedback: decisionFeedback.trim(),
    })
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <Link to="/training/assessments" className="page__backlink">
            ← Assessments
          </Link>
          <h1 className="page__title">{assessment.competency_code}</h1>
          <p className="page__subtitle">
            {assessment.trainee_detail.full_name} · Rubric v{assessment.rubric_version_number}
          </p>
        </div>
        <div className="badge-row">
          <Badge tone={meta.tone}>{meta.label}</Badge>
          <Badge tone="neutral">Assessed by {assessment.assessor_detail.full_name}</Badge>
        </div>
      </header>

      {actionError && (
        <p className="form-alert" role="alert">{actionError}</p>
      )}

      <div className="badge-row detail-actions">
        {canEdit && (
          <Button variant="secondary" loading={updateMutation.isPending} onClick={() => {
            // Inline edit handled below
          }}>
            Edit feedback
          </Button>
        )}
        {canSubmit && (
          <Button variant="primary" loading={submitMutation.isPending} onClick={onSubmitAssessment}>
            Submit for decision
          </Button>
        )}
        {canDecideNow && (
          <Button
            variant="primary"
            onClick={() => {
              setDecisionModal('approved')
              setDecisionReason('')
              setDecisionFeedback('')
              setActionError(null)
            }}
          >
            Approve
          </Button>
        )}
        {canDecideNow && (
          <Button
            variant="secondary"
            onClick={() => {
              setDecisionModal('needs_correction')
              setDecisionReason('')
              setDecisionFeedback('')
              setActionError(null)
            }}
          >
            Request correction
          </Button>
        )}
        {canDecideNow && (
          <Button
            variant="danger"
            onClick={() => {
              setDecisionModal('rejected')
              setDecisionReason('')
              setDecisionFeedback('')
              setActionError(null)
            }}
          >
            Reject
          </Button>
        )}
      </div>

      <div className="account-grid">
        <Card title="Assessment details">
          <dl className="definition-list">
            <dt>Trainee</dt>
            <dd>{assessment.trainee_detail.full_name}</dd>
            <dt>Assessor</dt>
            <dd>{assessment.assessor_detail.full_name}</dd>
            <dt>Competency</dt>
            <dd>{assessment.competency_code}</dd>
            <dt>Rubric version</dt>
            <dd>v{assessment.rubric_version_number}</dd>
            <dt>Status</dt>
            <dd>{meta.label}</dd>
            {assessment.submitted_at && (
              <>
                <dt>Submitted at</dt>
                <dd>{formatDateTime(assessment.submitted_at)}</dd>
              </>
            )}
            {assessment.decided_at && (
              <>
                <dt>Decided at</dt>
                <dd>{formatDateTime(assessment.decided_at)}</dd>
              </>
            )}
            {assessment.decision_reason && (
              <>
                <dt>Decision reason</dt>
                <dd>{assessment.decision_reason}</dd>
              </>
            )}
            {assessment.overall_level && (
              <>
                <dt>Overall level</dt>
                <dd>{assessment.overall_level}</dd>
              </>
            )}
          </dl>
        </Card>

        {scoreKeys.length > 0 && (
          <Card title="Scores by criterion">
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Criterion</th>
                    <th className="num">Level</th>
                  </tr>
                </thead>
                <tbody>
                  {scoreKeys.map((key) => (
                    <tr key={key}>
                      <td>{key.replaceAll('_', ' ')}</td>
                      <td className="num">{assessment.scores[key]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>

      {canEdit && (
        <form className="form" onSubmit={onSaveFeedback} noValidate>
          <Card title="Feedback">
            <label className="field">
              <span className="field__label">Feedback</span>
              <textarea
                className="field__control"
                rows={5}
                value={editFeedback}
                onChange={(event) => setEditFeedback(event.target.value)}
              />
            </label>
            <div className="badge-row">
              <Button type="submit" loading={updateMutation.isPending}>
                Save feedback
              </Button>
            </div>
          </Card>
        </form>
      )}

      <Modal
        open={decisionModal !== null}
        onClose={() => setDecisionModal(null)}
        title={DECISIONS.find((d) => d.value === decisionModal)?.label ?? 'Decision'}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDecisionModal(null)}>
              Cancel
            </Button>
            <Button
              variant={decisionModal === 'rejected' ? 'danger' : 'primary'}
              loading={decideMutation.isPending}
              form="decision-form"
              type="submit"
            >
              Confirm
            </Button>
          </>
        }
      >
        <form id="decision-form" className="form" onSubmit={onDecide}>
          {actionError && (
            <p className="form-alert" role="alert">{actionError}</p>
          )}
          <p className="field__hint">
            Assessment {assessment.competency_code} for {assessment.trainee_detail.full_name} —{' '}
            <strong>{DECISIONS.find((d) => d.value === decisionModal)?.label}</strong>
            .
          </p>
          {DECISIONS.find((d) => d.value === decisionModal)?.needsReason && (
            <label className="field">
              <span className="field__label">Reason (required)</span>
              <textarea
                className="field__control"
                rows={4}
                value={decisionReason}
                onChange={(event) => setDecisionReason(event.target.value)}
              />
            </label>
          )}
          <label className="field">
            <span className="field__label">Feedback</span>
            <textarea
              className="field__control"
              rows={4}
              value={decisionFeedback}
              onChange={(event) => setDecisionFeedback(event.target.value)}
            />
          </label>
        </form>
      </Modal>
    </div>
  )
}
