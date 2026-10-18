import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
import { downloadFile } from '../../lib/download'
import { formatBytes, formatDateTime } from '../../lib/format'
import type {
  Page,
  ProcedureAttachment,
  ProcedureReview,
  ProcedureVersion,
  SurgicalProcedure,
  TranscriptionResult,
  UserSummary,
} from '../../lib/types'
import { statusMeta } from '../../lib/status'

const EDITABLE_STATUSES = new Set(['draft', 'returned', 'approved'])

const REVIEWER_ROLES = new Set(['supervisor', 'examiner', 'institution_admin'])
const REVIEW_DECISIONS: { value: string; label: string; needsReason: boolean }[] = [
  { value: 'start_review', label: 'Start review', needsReason: false },
  { value: 'approve', label: 'Approve', needsReason: false },
  { value: 'request_correction', label: 'Request correction', needsReason: true },
  { value: 'reject', label: 'Reject', needsReason: true },
]

export function ProcedureDetailPage() {
  const { id = '' } = useParams()
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    procedure_date: '',
    category: 'elective',
    procedure_name: '',
    indication: '',
    summary: '',
    complications: '',
    postoperative: '',
    training_objectives: '',
  })
  const [editError, setEditError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [reviewModal, setReviewModal] = useState<string | null>(null)
  const [reviewReason, setReviewReason] = useState('')
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [transcript, setTranscript] = useState<TranscriptionResult | null>(null)
  const [transcribeError, setTranscribeError] = useState<string | null>(null)
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [language, setLanguage] = useState('en')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [userSearch, setUserSearch] = useState('')
  const [participantRole, setParticipantRole] = useState('observer')

  const procedureQuery = useQuery({
    queryKey: ['procedure', id],
    queryFn: () => apiFetch<SurgicalProcedure>(`/procedures/${id}/`),
    enabled: Boolean(id),
  })
  const attachmentsQuery = useQuery({
    queryKey: ['procedure-attachments', id],
    queryFn: () => apiFetch<ProcedureAttachment[]>(`/procedures/${id}/attachments/`),
    enabled: Boolean(id),
  })
  const reviewsQuery = useQuery({
    queryKey: ['procedure-reviews', id],
    queryFn: () => apiFetch<ProcedureReview[]>(`/procedures/${id}/reviews/`),
    enabled: Boolean(id),
  })
  const versionsQuery = useQuery({
    queryKey: ['procedure-versions', id],
    queryFn: () => apiFetch<ProcedureVersion[]>(`/procedures/${id}/versions/`),
    enabled: Boolean(id),
  })
  const userSearchQuery = useQuery({
    queryKey: ['users-search', userSearch],
    queryFn: () => apiFetch<Page<UserSummary>>(`/users/?search=${encodeURIComponent(userSearch)}`),
    enabled: userSearch.trim().length >= 2,
  })

  const invalidate = (): void => {
    void queryClient.invalidateQueries({ queryKey: ['procedure', id] })
    void queryClient.invalidateQueries({ queryKey: ['procedures'] })
    void queryClient.invalidateQueries({ queryKey: ['procedure-attachments', id] })
    void queryClient.invalidateQueries({ queryKey: ['procedure-reviews', id] })
    void queryClient.invalidateQueries({ queryKey: ['procedure-versions', id] })
  }

  const actionErrorOf = (error: unknown): string =>
    error instanceof ApiError ? error.message : 'The request failed. Please retry.'

  const submitMutation = useMutation({
    mutationFn: () => apiFetch<SurgicalProcedure>(`/procedures/${id}/submit/`, { method: 'POST' }),
    onSuccess: invalidate,
    onError: (error) => setActionError(actionErrorOf(error)),
  })

  const saveMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<SurgicalProcedure>(`/procedures/${id}/`, { method: 'PATCH', body: payload }),
    onSuccess: () => {
      setEditing(false)
      setEditError(null)
      invalidate()
    },
    onError: (error) => setEditError(actionErrorOf(error)),
  })

  const archiveMutation = useMutation({
    mutationFn: () => apiFetch<SurgicalProcedure>(`/procedures/${id}/archive/`, { method: 'POST' }),
    onSuccess: invalidate,
    onError: (error) => setActionError(actionErrorOf(error)),
  })

  const reviewMutation = useMutation({
    mutationFn: (payload: { decision: string; reason?: string }) =>
      apiFetch<{ procedure: SurgicalProcedure }>(`/procedures/${id}/reviews/`, {
        method: 'POST',
        body: payload,
      }),
    onSuccess: () => {
      setReviewModal(null)
      setReviewReason('')
      setReviewError(null)
      invalidate()
    },
    onError: (error) => setReviewError(actionErrorOf(error)),
  })

  const transcribeMutation = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData()
      body.append('audio', file)
      body.append('language', language)
      return apiFetch<TranscriptionResult>(`/procedures/${id}/transcribe/`, {
        method: 'POST',
        body,
      })
    },
    onSuccess: (result) => {
      setTranscript(result)
      setTranscribeError(null)
    },
    onError: (error) => {
      setTranscript(null)
      setTranscribeError(actionErrorOf(error))
    },
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData()
      body.append('file', file)
      return apiFetch<ProcedureAttachment>(`/procedures/${id}/attachments/`, {
        method: 'POST',
        body,
      })
    },
    onSuccess: () => {
      setUploadFile(null)
      invalidate()
    },
    onError: (error) => setActionError(actionErrorOf(error)),
  })

  const deleteAttachmentMutation = useMutation({
    mutationFn: (attachmentId: string) =>
      apiFetch<void>(`/procedures/${id}/attachments/${attachmentId}/`, { method: 'DELETE' }),
    onSuccess: invalidate,
    onError: (error) => setActionError(actionErrorOf(error)),
  })

  const addParticipantMutation = useMutation({
    mutationFn: (payload: { user: string; role: string }) =>
      apiFetch(`/procedures/${id}/participants/`, { method: 'POST', body: payload }),
    onSuccess: () => {
      setUserSearch('')
      setActionError(null)
      invalidate()
    },
    onError: (error) => setActionError(actionErrorOf(error)),
  })

  const removeParticipantMutation = useMutation({
    mutationFn: (participantId: string) =>
      apiFetch<void>(`/procedures/${id}/participants/${participantId}/`, { method: 'DELETE' }),
    onSuccess: invalidate,
    onError: (error) => setActionError(actionErrorOf(error)),
  })

  if (procedureQuery.isPending) {
    return (
      <div className="page-loading" role="status">
        <Spinner size="md" label="Loading record…" />
      </div>
    )
  }

  if (procedureQuery.isError) {
    const error = procedureQuery.error
    if (error instanceof ApiError && error.status === 404) {
      // Scenario C: never disclose anything about out-of-scope records.
      return (
        <div className="page">
          <div className="state-block state-block--error" role="alert">
            <h3 className="state-block__title">Record not found</h3>
            <p className="state-block__message">
              This record does not exist, or it belongs to an institution outside your
              access — STAR never discloses whether a foreign record exists.
            </p>
            <Link to="/logbook" className="btn btn--secondary btn--sm">
              Back to logbook
            </Link>
          </div>
        </div>
      )
    }
    return (
      <ErrorState
        message={actionErrorOf(error)}
        onRetry={() => void procedureQuery.refetch()}
      />
    )
  }

  const procedure = procedureQuery.data
  const meta = statusMeta('procedure', procedure.status)
  const isAuthor = user?.id === procedure.author
  const editable = EDITABLE_STATUSES.has(procedure.status)
  const canEdit = Boolean(isAuthor && editable)
  const canSubmit = Boolean(isAuthor && ['draft', 'returned'].includes(procedure.status))
  const canAttach = Boolean(isAuthor && procedure.status !== 'archived')
  const canTranscribe = Boolean(isAuthor && editable)
  const canManageParticipants = Boolean(isAuthor && editable)
  const canArchive = Boolean(
    !isAuthor &&
      procedure.status === 'approved' &&
      user?.roles.some(
        (assignment) =>
          assignment.is_active &&
          assignment.institution === procedure.institution &&
          REVIEWER_ROLES.has(assignment.role),
      ),
  )
  const canReview = Boolean(
    !isAuthor &&
      ['submitted', 'under_review'].includes(procedure.status) &&
      user?.roles.some(
        (assignment) =>
          assignment.is_active &&
          assignment.institution === procedure.institution &&
          REVIEWER_ROLES.has(assignment.role),
      ),
  )
  const canUseDirectory = Boolean(
    user?.is_platform_admin ||
      user?.roles.some(
        (assignment) =>
          assignment.is_active &&
          ['institution_admin', 'department_manager'].includes(assignment.role),
      ),
  )

  function startEditing(): void {
    setForm({
      procedure_date: procedure.procedure_date,
      category: procedure.category,
      procedure_name: procedure.procedure_name,
      indication: procedure.indication,
      summary: procedure.summary,
      complications: procedure.complications,
      postoperative: procedure.postoperative,
      training_objectives: procedure.training_objectives,
    })
    setEditError(null)
    setEditing(true)
  }

  function onSave(event: FormEvent): void {
    event.preventDefault()
    if (!form.procedure_name.trim()) {
      setEditError('The procedure name is required.')
      return
    }
    saveMutation.mutate({ ...form, procedure_name: form.procedure_name.trim() })
  }

  function onSubmitReview(event: FormEvent): void {
    event.preventDefault()
    if (!reviewModal) return
    const decision = reviewModal
    const needsReasonNow = decision === 'request_correction' || decision === 'reject'
    if (needsReasonNow && !reviewReason.trim()) {
      setReviewError('A reason is required when a record is not approved.')
      return
    }
    reviewMutation.mutate(
      needsReasonNow ? { decision, reason: reviewReason.trim() } : { decision },
    )
  }

  function onTranscribe(event: FormEvent): void {
    event.preventDefault()
    if (!audioFile) {
      setTranscribeError('Choose an audio file first.')
      return
    }
    transcribeMutation.mutate(audioFile)
  }

  function useTranscriptAsSummary(): void {
    if (!transcript) return
    if (!editing) startEditing()
    setForm((current) => ({ ...current, summary: transcript.text }))
  }

  const attachments = attachmentsQuery.data ?? []
  const reviews = reviewsQuery.data ?? []
  const versions = versionsQuery.data ?? []
  const searchResults = userSearchQuery.data?.results ?? []
  const needsReason = reviewModal === 'request_correction' || reviewModal === 'reject'

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <Link to="/logbook" className="page__backlink">
            ← Logbook
          </Link>
          <h1 className="page__title">{procedure.procedure_name}</h1>
          <p className="page__subtitle">
            {procedure.reference} · {formatDateTime(procedure.procedure_date)}
            {procedure.institution_name ? ` · ${procedure.institution_name}` : ''}
          </p>
        </div>
        <div className="badge-row">
          <Badge tone={meta.tone}>{meta.label}</Badge>
          <Badge tone="neutral">v{procedure.version}</Badge>
        </div>
      </header>

      {actionError && (
        <p className="form-alert" role="alert">
          {actionError}
        </p>
      )}

      <div className="badge-row detail-actions">
        {canSubmit && (
          <Button
            variant="primary"
            loading={submitMutation.isPending}
            onClick={() => submitMutation.mutate()}
          >
            Submit for review
          </Button>
        )}
        {canEdit && !editing && (
          <Button variant="secondary" onClick={startEditing}>
            Edit record
          </Button>
        )}
        {canArchive && (
          <Button
            variant="secondary"
            loading={archiveMutation.isPending}
            onClick={() => archiveMutation.mutate()}
          >
            Archive
          </Button>
        )}
        {canReview && (
          <Button
            variant="primary"
            onClick={() => {
              setReviewModal('approve')
              setReviewReason('')
              setReviewError(null)
            }}
          >
            Review…
          </Button>
        )}
      </div>

      {canReview && (
        <Card title="Reviewer actions">
          <p className="field__hint">
            You review records authored by others in your institution. Corrections and
            rejections require a reason; every decision is recorded in the audit history.
          </p>
          <div className="badge-row">
            {['submitted', 'under_review'].includes(procedure.status) && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setReviewModal('start_review')
                  setReviewReason('')
                  setReviewError(null)
                }}
              >
                Start review
              </Button>
            )}
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setReviewModal('approve')
                setReviewReason('')
                setReviewError(null)
              }}
            >
              Approve
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setReviewModal('request_correction')
                setReviewReason('')
                setReviewError(null)
              }}
            >
              Request correction
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => {
                setReviewModal('reject')
                setReviewReason('')
                setReviewError(null)
              }}
            >
              Reject
            </Button>
          </div>
        </Card>
      )}

      {editing ? (
        <form className="form" onSubmit={onSave} noValidate>
          <Card title="Edit record">
            {editError && (
              <p className="form-alert" role="alert">
                {editError}
              </p>
            )}
            <div className="form-grid">
              <label className="field">
                <span className="field__label">Procedure date *</span>
                <input
                  className="field__control"
                  type="date"
                  value={form.procedure_date}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, procedure_date: event.target.value }))
                  }
                />
              </label>
              <label className="field">
                <span className="field__label">Category</span>
                <select
                  className="field__control"
                  value={form.category}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, category: event.target.value }))
                  }
                >
                  {['elective', 'emergency', 'trauma', 'diagnostic', 'other'].map((value) => (
                    <option key={value} value={value}>
                      {value.charAt(0).toUpperCase() + value.slice(1)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="field">
              <span className="field__label">Procedure name *</span>
              <input
                className="field__control"
                value={form.procedure_name}
                onChange={(event) =>
                  setForm((current) => ({ ...current, procedure_name: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span className="field__label">Indication</span>
              <textarea
                className="field__control"
                rows={3}
                value={form.indication}
                onChange={(event) =>
                  setForm((current) => ({ ...current, indication: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span className="field__label">Operative summary</span>
              <textarea
                className="field__control"
                rows={5}
                value={form.summary}
                onChange={(event) =>
                  setForm((current) => ({ ...current, summary: event.target.value }))
                }
              />
            </label>
            <div className="form-grid">
              <label className="field">
                <span className="field__label">Complications</span>
                <textarea
                  className="field__control"
                  rows={3}
                  value={form.complications}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, complications: event.target.value }))
                  }
                />
              </label>
              <label className="field">
                <span className="field__label">Postoperative course</span>
                <textarea
                  className="field__control"
                  rows={3}
                  value={form.postoperative}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, postoperative: event.target.value }))
                  }
                />
              </label>
            </div>
            <label className="field">
              <span className="field__label">Training objectives</span>
              <textarea
                className="field__control"
                rows={3}
                value={form.training_objectives}
                onChange={(event) =>
                  setForm((current) => ({ ...current, training_objectives: event.target.value }))
                }
              />
            </label>
            <div className="badge-row">
              <Button type="submit" loading={saveMutation.isPending}>
                Save changes
              </Button>
              <Button variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          </Card>
        </form>
      ) : (
        <Card title="Record details">
          <dl className="definition-list">
            <dt>Status</dt>
            <dd>{meta.label}</dd>
            <dt>Date</dt>
            <dd>{formatDateTime(procedure.procedure_date)}</dd>
            <dt>Category</dt>
            <dd>{procedure.category}</dd>
            <dt>Author</dt>
            <dd>{procedure.author_detail.full_name}</dd>
            <dt>Institution</dt>
            <dd>{procedure.institution_name}</dd>
            {procedure.department_name && (
              <>
                <dt>Department</dt>
                <dd>{procedure.department_name}</dd>
              </>
            )}
            {procedure.specialty_name && (
              <>
                <dt>Specialty</dt>
                <dd>{procedure.specialty_name}</dd>
              </>
            )}
            {procedure.patient_reference_code && (
              <>
                <dt>Patient ref.</dt>
                <dd>{procedure.patient_reference_code}</dd>
              </>
            )}
            <dt>Indication</dt>
            <dd>{procedure.indication || '—'}</dd>
            <dt>Summary</dt>
            <dd>{procedure.summary || '—'}</dd>
            <dt>Complications</dt>
            <dd>{procedure.complications || '—'}</dd>
            <dt>Postoperative</dt>
            <dd>{procedure.postoperative || '—'}</dd>
            <dt>Objectives</dt>
            <dd>{procedure.training_objectives || '—'}</dd>
          </dl>
        </Card>
      )}

      {canTranscribe && (
        <Card title="Voice dictation">
          <p className="field__hint">
            Record a dictation and generate a draft transcript. Audio is validated then
            discarded — never stored. The transcript never replaces your text: you review it
            and save explicitly.
          </p>
          {transcribeError && (
            <p className="form-alert" role="alert">
              {transcribeError} Your draft is untouched — you can keep writing the summary
              manually.
            </p>
          )}
          <form className="form" onSubmit={onTranscribe}>
            <div className="form-grid">
              <label className="field">
                <span className="field__label">Audio file</span>
                <input
                  className="field__control"
                  type="file"
                  accept=".wav,.ogg,.webm,.mp3,.m4a,audio/*"
                  onChange={(event) => setAudioFile(event.target.files?.[0] ?? null)}
                />
              </label>
              <label className="field">
                <span className="field__label">Language</span>
                <select
                  className="field__control"
                  value={language}
                  onChange={(event) => setLanguage(event.target.value)}
                >
                  <option value="en">English</option>
                  <option value="fr">Français</option>
                </select>
              </label>
            </div>
            <div className="badge-row">
              <Button
                type="submit"
                variant="secondary"
                loading={transcribeMutation.isPending}
              >
                Generate transcript
              </Button>
            </div>
          </form>
          {transcript && (
            <div className="transcript-block">
              <div className="badge-row">
                <Badge tone={transcript.simulated ? 'warning' : 'info'}>
                  {transcript.simulated ? 'SIMULATED' : transcript.provider}
                </Badge>
                {transcript.uncertain && <Badge tone="warning">Uncertain</Badge>}
              </div>
              <textarea
                className="field__control"
                rows={5}
                readOnly
                value={transcript.text}
                aria-label="Draft transcript"
              />
              <div className="badge-row">
                <Button variant="secondary" size="sm" onClick={useTranscriptAsSummary}>
                  Use as operative summary
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}

      <div className="account-grid">
        <Card title="Participants">
          {procedure.participants.length === 0 ? (
            <p className="field__hint">No participants recorded yet.</p>
          ) : (
            <ul className="role-list">
              {procedure.participants.map((participant) => (
                <li key={participant.id} className="participant-row">
                  <span>
                    <strong>{participant.user_detail.full_name}</strong>{' '}
                    <Badge tone="info">{participant.role.replaceAll('_', ' ')}</Badge>
                  </span>
                  {canManageParticipants && (
                    <Button
                      variant="ghost"
                      size="sm"
                      loading={removeParticipantMutation.isPending}
                      onClick={() => removeParticipantMutation.mutate(participant.id)}
                    >
                      Remove
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {canManageParticipants && (
            <div className="participant-add">
              {canUseDirectory ? (
                <form
                  className="form"
                  onSubmit={(event) => {
                    event.preventDefault()
                    const pick = searchResults[0]
                    if (!pick) {
                      setActionError('Search for a user and pick them first.')
                      return
                    }
                    addParticipantMutation.mutate({ user: pick.id, role: participantRole })
                  }}
                >
                  <div className="form-grid">
                    <label className="field">
                      <span className="field__label">Find a colleague</span>
                      <input
                        className="field__control"
                        type="search"
                        placeholder="Name or email"
                        value={userSearch}
                        onChange={(event) => setUserSearch(event.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span className="field__label">Role</span>
                      <select
                        className="field__control"
                        value={participantRole}
                        onChange={(event) => setParticipantRole(event.target.value)}
                      >
                        <option value="primary_operator">Primary operator</option>
                        <option value="assistant">Assistant</option>
                        <option value="observer">Observer</option>
                      </select>
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
              ) : (
                <p className="field__hint">
                  Participants are added through the institution directory by your
                  administrators.
                </p>
              )}
            </div>
          )}
        </Card>

        <Card title="Attachments">
          {attachments.length === 0 ? (
            <p className="field__hint">No files attached.</p>
          ) : (
            <ul className="attachment-list">
              {attachments.map((attachment) => (
                <li key={attachment.id} className="attachment-row">
                  <span className="attachment-row__meta">
                    <strong>{attachment.original_name}</strong>
                    <span className="field__hint">
                      {formatBytes(attachment.size_bytes)} ·{' '}
                      {formatDateTime(attachment.created_at)} ·{' '}
                      {attachment.uploaded_by_detail.full_name}
                    </span>
                  </span>
                  <span className="badge-row">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        void downloadFile(
                          `/procedures/${id}/attachments/${attachment.id}/download/`,
                          attachment.original_name,
                        ).catch((error: unknown) =>
                          setActionError(actionErrorOf(error)),
                        )
                      }
                    >
                      Download
                    </Button>
                    {canAttach && (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => deleteAttachmentMutation.mutate(attachment.id)}
                      >
                        Delete
                      </Button>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {canAttach && (
            <form
              className="form"
              onSubmit={(event) => {
                event.preventDefault()
                if (uploadFile) uploadMutation.mutate(uploadFile)
              }}
            >
              <label className="field">
                <span className="field__label">Add a file</span>
                <input
                  className="field__control"
                  type="file"
                  onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
                />
              </label>
              <div className="badge-row">
                <Button
                  type="submit"
                  variant="secondary"
                  size="sm"
                  disabled={!uploadFile}
                  loading={uploadMutation.isPending}
                >
                  Upload
                </Button>
              </div>
            </form>
          )}
        </Card>
      </div>

      <div className="account-grid">
        <Card title="Review history">
          {reviews.length === 0 ? (
            <p className="field__hint">No review decisions yet.</p>
          ) : (
            <ul className="role-list">
              {reviews.map((review) => (
                <li key={review.id}>
                  <span className="badge-row">
                    <Badge
                      tone={
                        review.decision === 'approve'
                          ? 'success'
                          : review.decision === 'reject'
                            ? 'danger'
                            : review.decision === 'request_correction'
                              ? 'warning'
                              : 'info'
                      }
                    >
                      {review.decision.replaceAll('_', ' ')}
                    </Badge>
                    <span className="field__hint">
                      {review.reviewer_detail?.full_name ?? 'System'} ·{' '}
                      {formatDateTime(review.created_at)}
                    </span>
                  </span>
                  {review.reason && <span className="field__hint">{review.reason}</span>}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Version history">
          {versions.length === 0 ? (
            <p className="field__hint">No snapshots yet.</p>
          ) : (
            <ul className="role-list">
              {versions.map((version) => (
                <li key={version.id}>
                  <span className="badge-row">
                    <Badge tone="neutral">v{version.version}</Badge>
                    <span className="field__hint">
                      {version.change_kind} · {formatDateTime(version.created_at)}
                    </span>
                  </span>
                  <span className="role-list__org">
                    {version.changed_by_detail?.full_name ?? 'System'}
                    {version.change_summary ? ` — ${version.change_summary}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Modal
        open={reviewModal !== null}
        onClose={() => setReviewModal(null)}
        title={
          REVIEW_DECISIONS.find((item) => item.value === reviewModal)?.label ?? 'Review'
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setReviewModal(null)}>
              Cancel
            </Button>
            <Button
              variant={reviewModal === 'reject' ? 'danger' : 'primary'}
              loading={reviewMutation.isPending}
              form="review-form"
              type="submit"
            >
              Confirm
            </Button>
          </>
        }
      >
        <form id="review-form" className="form" onSubmit={onSubmitReview}>
          {reviewError && (
            <p className="form-alert" role="alert">
              {reviewError}
            </p>
          )}
          <p className="field__hint">
            Record {procedure.reference} — decision:{' '}
            <strong>
              {REVIEW_DECISIONS.find((item) => item.value === reviewModal)?.label}
            </strong>
            .
          </p>
          {needsReason && (
            <label className="field">
              <span className="field__label">Reason (required)</span>
              <textarea
                className="field__control"
                rows={4}
                value={reviewReason}
                onChange={(event) => setReviewReason(event.target.value)}
              />
            </label>
          )}
        </form>
      </Modal>
    </div>
  )
}
