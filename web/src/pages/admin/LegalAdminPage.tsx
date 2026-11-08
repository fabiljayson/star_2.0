import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { TextField } from '../../components/TextField'
import { formatDate, formatDateTime, todayIsoDate } from '../../lib/format'
import { policyStatusLabel } from '../../lib/legal'
import type {
  AdminPolicyVersion,
  AdminPrivacyRequestItem,
  Page,
  PolicyLanguage,
  PolicyListItem,
} from '../../lib/types'

type Tab = 'versions' | 'privacy-requests'

const STATUS_FILTERS = ['', 'draft', 'pending_review', 'approved', 'published', 'superseded', 'archived']

// Platform-admin workbench for the Policies & Legal Center. Drafts are
// never published public-facing until walked through review and approval.
export function LegalAdminPage() {
  const [tab, setTab] = useState<Tab>('versions')

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Policies &amp; privacy administration</h1>
          <p className="page__subtitle">
            Draft, review, approve and publish bilingual policy texts; follow up
            privacy requests.
          </p>
        </div>
        <Link to="/admin" className="btn btn--secondary btn--sm">
          Back to admin
        </Link>
      </header>
      <div className="tabs">
        <button
          type="button"
          className={`tab ${tab === 'versions' ? 'tab--active' : ''}`}
          onClick={() => setTab('versions')}
        >
          Policy versions
        </button>
        <button
          type="button"
          className={`tab ${tab === 'privacy-requests' ? 'tab--active' : ''}`}
          onClick={() => setTab('privacy-requests')}
        >
          Privacy requests
        </button>
      </div>
      {tab === 'versions' && <VersionsPanel />}
      {tab === 'privacy-requests' && <PrivacyRequestsPanel />}
    </div>
  )
}

function VersionsPanel() {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('')
  const query = useQuery({
    queryKey: ['legal-admin-versions', statusFilter],
    queryFn: () =>
      apiFetch<Page<AdminPolicyVersion>>(
        `/legal/policy-versions/${statusFilter ? `?status=${statusFilter}` : ''}`,
      ),
  })
  const policiesQuery = useQuery({
    queryKey: ['legal-policies', 'en'],
    queryFn: () =>
      apiFetch<{ results: PolicyListItem[] }>('/legal/policies/?lang=en'),
  })

  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)

  function invalidate(): void {
    void queryClient.invalidateQueries({ queryKey: ['legal-admin-versions'] })
    void queryClient.invalidateQueries({ queryKey: ['legal-policies'] })
  }

  const actionMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      apiFetch<AdminPolicyVersion>(`/legal/policy-versions/${id}/${action}/`, {
        method: 'POST',
        body: {},
      }),
    onSuccess: (_data, variables) => {
      setError(null)
      void variables
      setMessage('Done.')
      invalidate()
    },
    onError: (err) => {
      setMessage(null)
      setError(err instanceof Error ? err : null)
      setMessage(null)
    },
  })

  return (
    <div className="account-grid">
      <Card title="All policy versions">
        <div className="list-filters">
          <label className="field">
            <span className="field__label">Status</span>
            <select
              className="field__control"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              {STATUS_FILTERS.map((status) => (
                <option key={status} value={status}>
                  {status ? policyStatusLabel(status) : 'All statuses'}
                </option>
              ))}
            </select>
          </label>
        </div>
        {query.isPending && !query.data && (
          <div className="page-loading" role="status">
            <Spinner size="sm" />
          </div>
        )}
        {query.isError && !query.data && (
          <ErrorState
            message="Could not load versions."
            onRetry={() => void query.refetch()}
          />
        )}
        {message && !error && (
          <p className="form-alert form-alert--success" role="status">
            {message}
          </p>
        )}
        {error && (
          <p className="form-alert" role="alert">
            {error.message}
          </p>
        )}
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Policy</th>
                <th>Text</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(query.data?.results ?? []).map((version) => (
                <tr key={version.id}>
                  <td>
                    {version.policy_slug}
                    <span className="field__hint">{version.language.toUpperCase()}</span>
                  </td>
                  <td>
                    v{version.version} · {version.title}
                    <span className="field__hint">
                      Effective {formatDate(version.effective_date)}
                    </span>
                  </td>
                  <td>
                    <Badge
                      tone={
                        version.status === 'published'
                          ? 'success'
                          : version.status === 'draft'
                            ? 'warning'
                            : 'neutral'
                      }
                    >
                      {policyStatusLabel(version.status)}
                    </Badge>
                    {version.published_at && (
                      <span className="field__hint">
                        {formatDateTime(version.published_at)}
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="badge-row">
                      {version.status === 'draft' && (
                        <>
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() =>
                              actionMutation.mutate({
                                id: version.id,
                                action: 'submit-review',
                              })
                            }
                          >
                            Submit review
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              actionMutation.mutate({ id: version.id, action: 'archive' })
                            }
                          >
                            Archive
                          </Button>
                        </>
                      )}
                      {version.status === 'pending_review' && (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() =>
                            actionMutation.mutate({ id: version.id, action: 'approve' })
                          }
                        >
                          Approve
                        </Button>
                      )}
                      {version.status === 'approved' && (
                        <Button
                          size="sm"
                          onClick={() =>
                            actionMutation.mutate({ id: version.id, action: 'publish' })
                          }
                        >
                          Publish
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <CreateDraftPanel policies={policiesQuery.data?.results ?? []} onSaved={invalidate} onVersionCreated={(version) => {void version; invalidate()}} />
    </div>
  )
}

function CreateDraftPanel({
  policies,
  onSaved,
  onVersionCreated,
}: {
  policies: PolicyListItem[]
  onSaved: () => void
  onVersionCreated: (version: AdminPolicyVersion) => void
}) {
  const [slug, setSlug] = useState('')
  const [language, setLanguage] = useState<PolicyLanguage>('fr')
  const [version, setVersion] = useState('')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [effectiveDate, setEffectiveDate] = useState(todayIsoDate())
  const [translationOf, setTranslationOf] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [formSuccess, setFormSuccess] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      apiFetch<AdminPolicyVersion>(
        `/legal/policies/${slug}/versions/create/`,
        {
          method: 'POST',
          body: {
            language,
            version,
            title,
            body,
            effective_date: effectiveDate || null,
            ...(translationOf ? { translation_of: translationOf } : {}),
          },
        },
      ),
    onSuccess: (created) => {
      setFormError(null)
      setFormSuccess(`Draft created: v${created.version} (${created.language}).`)
      setVersion('')
      setTitle('')
      setBody('')
      setTranslationOf('')
      onVersionCreated(created)
      onSaved()
    },
    onError: (err) => {
      setFormSuccess(null)
      setFormError(
        err instanceof Error && err.message ? err.message : 'Could not create the draft.',
      )
    },
  })

  return (
    <Card title="New draft">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          if (!slug || !version || !title || !body) {
            setFormError('Fill policy, version, title and text.')
            return
          }
          setFormSuccess(null)
          mutation.mutate()
        }}
        className="form"
      >
        {formError && (
          <p className="form-alert" role="alert">
            {formError}
          </p>
        )}
        {formSuccess && (
          <p className="form-alert form-alert--success" role="status">
            {formSuccess}
          </p>
        )}
        <div className="form-grid">
          <label className="field">
            <span className="field__label">Policy</span>
            <select
              className="field__control"
              value={slug}
              onChange={(event) => setSlug(event.target.value)}
            >
              <option value="">Choose…</option>
              {policies.map((policy) => (
                <option key={policy.slug} value={policy.slug}>
                  {policy.title}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">Language</span>
            <select
              className="field__control"
              value={language}
              onChange={(event) => setLanguage(event.target.value as PolicyLanguage)}
            >
              <option value="en">English</option>
              <option value="fr">Français</option>
            </select>
          </label>
        </div>
        <div className="form-grid">
          <TextField
            label="Version"
            name="version"
            value={version}
            onChange={(event) => setVersion(event.target.value)}
            hint="Example: 1.1"
          />
          <TextField
            label="Effective date"
            name="effective_date"
            type="date"
            value={effectiveDate}
            onChange={(event) => setEffectiveDate(event.target.value)}
          />
        </div>
        <TextField
          label="Title"
          name="title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
        <label className="field">
          <span className="field__label">Body (## headings build the table of contents)</span>
          <textarea
            className="field__control field__control--area"
            rows={6}
            value={body}
            onChange={(event) => setBody(event.target.value)}
          />
        </label>
        <TextField
          label="Translation of (source version)"
          name="translation_of"
          value={translationOf}
          onChange={(event) => setTranslationOf(event.target.value)}
          hint="Optional: EN v1.0 links to FR 1.1"
        />
        <Button type="submit" block loading={mutation.isPending}>
          Create review draft
        </Button>
      </form>
    </Card>
  )
}

function PrivacyRequestsPanel() {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['legal-admin-privacy-requests'],
    queryFn: () =>
      apiFetch<Page<AdminPrivacyRequestItem>>('/legal/privacy-requests/?page_size=50'),
  })
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [inputNote, setInputNote] = useState<Record<string, string>>({})

  const reviewMutation = useMutation({
    mutationFn: (input: { id: string; status: string; note: string }) =>
      apiFetch<AdminPrivacyRequestItem>(
        `/legal/privacy-requests/${input.id}/review/`,
        { method: 'POST', body: { status: input.status, note: input.note } },
      ),
    onSuccess: (_data, input) => {
      setInputNote((prev) => ({ ...prev, [input.id]: '' }))
      setMessage(`Request marked ${input.status.replace('_', ' ')}.`)
      setError(null)
      void queryClient.invalidateQueries({
        queryKey: ['legal-admin-privacy-requests'],
      })
    },
    onError: (err) =>
      setError(err instanceof Error ? err.message : 'Review failed.'),
  })

  return (
    <Card title="Privacy requests">
      {query.isPending && !query.data && (
        <div className="page-loading" role="status">
          <Spinner size="sm" />
        </div>
      )}
      {query.isError && !query.data && (
        <ErrorState message="Could not load requests." onRetry={() => void query.refetch()} />
      )}
      {message && (
        <p className="form-alert form-alert--success" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="form-alert" role="alert">
          {error}
        </p>
      )}
      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Kind</th>
              <th>Message</th>
              <th>Status</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody>
            {(query.data?.results ?? []).map((request) => (
              <tr key={request.id}>
                <td>{request.user_email}</td>
                <td>{request.kind_label}</td>
                <td className="privacy-request__message">
                  {request.message}
                  {request.response_note && (
                    <span className="field__hint">
                      Response: {request.response_note}
                    </span>
                  )}
                </td>
                <td>
                  <Badge
                    tone={
                      request.status === 'completed'
                        ? 'success'
                        : request.status === 'rejected'
                          ? 'danger'
                          : 'warning'
                    }
                  >
                    {policyStatusLabel(request.status)}
                  </Badge>
                </td>
                <td>
                  {['open', 'in_review'].includes(request.status) && (
                    <div className="badge-row">
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={reviewMutation.isPending}
                        onClick={() =>
                          reviewMutation.mutate({
                            id: request.id,
                            status: 'in_review',
                            note: inputNote[request.id] ?? '',
                          })
                        }
                      >
                        In review
                      </Button>
                      <Button
                        size="sm"
                        loading={reviewMutation.isPending}
                        onClick={() =>
                          reviewMutation.mutate({
                            id: request.id,
                            status: 'completed',
                            note: inputNote[request.id] ?? '',
                          })
                        }
                      >
                        Complete
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        loading={reviewMutation.isPending}
                        onClick={() =>
                          reviewMutation.mutate({
                            id: request.id,
                            status: 'rejected',
                            note: inputNote[request.id] ?? '',
                          })
                        }
                      >
                        Reject
                      </Button>
                      <div className="field__control-wrap">
                        <TextField
                          label=""
                          value={inputNote[request.id] ?? ''}
                          onChange={(event) =>
                            setInputNote({
                              ...inputNote,
                              [request.id]: event.target.value,
                            })
                          }
                          placeholder="Note"
                        />
                      </div>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {query.data && query.data.results.length === 0 && (
        <p className="field__hint">No privacy request.</p>
      )}
    </Card>
  )
}
