import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ApiError, apiFetch } from '../../lib/api'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { formatDate, formatDateTime } from '../../lib/format'
import { policyStatusLabel } from '../../lib/legal'
import type {
  ConsentRecord,
  ConsentStatusItem,
  Page,
  PrivacyRequestItem,
} from '../../lib/types'

const PRIVACY_KINDS = [
  { value: 'access', label: 'Access my data' },
  { value: 'export', label: 'Export my data' },
  { value: 'deletion', label: 'Delete my account data' },
  { value: 'correction', label: 'Correct my data' },
  { value: 'other', label: 'Other request' },
] as const

// Account area: what you accepted, accept again, withdraw, and open a
// privacy request. Consents are immutable — withdrawal keeps the record.
export function ConsentsPage() {
  const queryClient = useQueryClient()
  const [formError, setFormError] = useState<string | null>(null)
  const [formSuccess, setFormSuccess] = useState<string | null>(null)
  const [kind, setKind] = useState<string>('access')
  const [message, setMessage] = useState('')

  const statusQuery = useQuery({
    queryKey: ['legal-consent-status'],
    queryFn: () =>
      apiFetch<{ results: ConsentStatusItem[] }>('/legal/consents/status/'),
  })
  const historyQuery = useQuery({
    queryKey: ['legal-consent-history'],
    queryFn: () =>
      apiFetch<Page<ConsentRecord>>('/legal/consents/mine/?page_size=50'),
  })
  const requestsQuery = useQuery({
    queryKey: ['legal-privacy-requests-mine'],
    queryFn: () =>
      apiFetch<Page<PrivacyRequestItem>>('/legal/privacy-requests/mine/?page_size=20'),
  })

  function invalidate(): void {
    void queryClient.invalidateQueries({ queryKey: ['legal-consent-status'] })
    void queryClient.invalidateQueries({ queryKey: ['legal-consent-history'] })
    void queryClient.invalidateQueries({ queryKey: ['legal-privacy-requests-mine'] })
  }

  const acceptMutation = useMutation({
    mutationFn: (item: ConsentStatusItem) =>
      apiFetch<ConsentRecord>('/legal/consents/', {
        method: 'POST',
        body: {
          policy_slug: item.policy,
          version: item.current_version,
          language: 'en',
          context: 'account',
        },
      }),
    onSuccess: (_data, item) => {
      setFormError(null)
      setFormSuccess(`Consent recorded for “${item.title}”.`)
      invalidate()
    },
    onError: (error) => {
      setFormSuccess(null)
      setFormError(
        error instanceof Error && error.message
          ? error.message
          : 'Could not record the consent.',
      )
    },
  })

  const withdrawMutation = useMutation({
    mutationFn: (policy: string) =>
      apiFetch<{ message: string }>('/legal/consents/withdraw/', {
        method: 'POST',
        body: { policy },
      }),
    onSuccess: (data) => {
      setFormError(null)
      setFormSuccess(data.message)
      invalidate()
    },
    onError: (error) => {
      setFormSuccess(null)
      setFormError(
        error instanceof Error && error.message ? error.message : 'Withdrawal failed.',
      )
    },
  })

  const requestMutation = useMutation({
    mutationFn: () =>
      apiFetch<PrivacyRequestItem>('/legal/privacy-requests/', {
        method: 'POST',
        body: { kind, message },
      }),
    onSuccess: () => {
      setFormError(null)
      setFormSuccess('Privacy request opened. The operator will follow up.')
      setMessage('')
      invalidate()
    },
    onError: (error) => {
      setFormSuccess(null)
      setFormError(
        error instanceof ApiError && error.message ? error.message : 'Request failed.',
      )
    },
  })

  const loading =
    statusQuery.isPending && historyQuery.isPending && requestsQuery.isPending

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Consents &amp; privacy</h1>
          <p className="page__subtitle">
            What you agreed to, when, and how to exercise your data rights.
            Policies are readable in the{' '}
            <Link to="/legal">Policy Center</Link>.
          </p>
        </div>
        <Link to="/account" className="btn btn--secondary btn--sm">
          Back to account
        </Link>
      </header>

      {(formError || formSuccess) && (
        <p
          className={formSuccess ? 'form-alert form-alert--success' : 'form-alert'}
          role="alert"
        >
          {formSuccess || formError}
        </p>
      )}

      {loading && (
        <div className="page-loading" role="status">
          <Spinner size="md" label="Loading your consents…" />
        </div>
      )}

      <div className="account-grid">
        <Card title="Current agreements">
          {statusQuery.isError && !statusQuery.data && (
            <ErrorState
              message="Could not load consent status."
              onRetry={() => void statusQuery.refetch()}
            />
          )}
          <ul className="role-list">
            {(statusQuery.data?.results ?? []).map((item) => (
              <li key={item.policy} className="consent-row">
                <div className="consent-row__main">
                  <strong>{item.title}</strong>
                  <span className="field__hint">
                    Current version v{item.current_version}
                    {item.latest_withdrawn_at && (
                      <>
                        {' '}
                        · withdrawn {formatDate(item.latest_withdrawn_at)}
                      </>
                    )}
                  </span>
                </div>
                <div className="badge-row">
                  <Badge tone={item.consent_current ? 'success' : 'warning'}>
                    {item.consent_current ? 'Accepted' : 'Not accepted'}
                  </Badge>
                  {item.consent_current ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={withdrawMutation.isPending}
                      onClick={() => withdrawMutation.mutate(item.policy)}
                    >
                      Withdraw
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      loading={acceptMutation.isPending}
                      onClick={() => acceptMutation.mutate(item)}
                    >
                      Accept v{item.current_version}
                    </Button>
                  )}
                  <Link
                    to={`/legal/policies/${item.policy}`}
                    className="btn btn--ghost btn--sm"
                  >
                    Read
                  </Link>
                </div>
              </li>
            ))}
          </ul>
          {statusQuery.data && statusQuery.data.results.length === 0 && (
            <p className="field__hint">No published policy yet.</p>
          )}
        </Card>

        <Card title="Your consent history">
          <ul className="role-list">
            {(historyQuery.data?.results ?? []).map((record) => (
              <li key={record.id}>
                <div className="consent-row__main">
                  <strong>
                    {record.policy_title} — v{record.version}
                  </strong>
                  <span className="field__hint">
                    {formatDateTime(record.created_at)} · contextual:{' '}
                    {record.context}
                  </span>
                </div>
                <Badge
                  tone={record.withdrawn_at ? 'neutral' : 'success'}
                >
                  {record.withdrawn_at
                    ? `Withdrawn ${formatDate(record.withdrawn_at)}`
                    : 'Active'}
                </Badge>
              </li>
            ))}
          </ul>
          {historyQuery.data && historyQuery.data.results.length === 0 && (
            <p className="field__hint">
              Nothing recorded yet — accept the terms from the cards on the left.
            </p>
          )}
        </Card>

        <Card title="Open a privacy request">
          <p className="field__hint">
            Ask to access, export, correct or delete your personal data. Your
            request is logged and handled by the operator.
          </p>
          <div className="form-grid">
            <label className="field">
              <span className="field__label">Request type</span>
              <select
                className="field__input"
                value={kind}
                onChange={(event) => setKind(event.target.value)}
              >
                {PRIVACY_KINDS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <span />
          </div>
          <label className="field">
            <span className="field__label">Message</span>
            <textarea
              className="field__control field__control--area"
              rows={3}
              value={message}
              onChange={(event) => setMessage(event.target.value)}
            />
          </label>
          <Button
            block
            loading={requestMutation.isPending}
            disabled={message.trim().length === 0}
            onClick={() => requestMutation.mutate()}
          >
            Submit request
          </Button>
          <ul className="role-list">
            {(requestsQuery.data?.results ?? []).map((request) => (
              <li key={request.id} className="consent-row">
                <div className="consent-row__main">
                  <strong>{request.kind_label}</strong>
                  <span className="field__hint">
                    Opened {formatDateTime(request.created_at)}
                    {request.handled_at && ` · handled ${formatDateTime(request.handled_at)}`}
                  </span>
                  {request.response_note && (
                    <span className="field__hint">Response: {request.response_note}</span>
                  )}
                </div>
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
              </li>
            ))}
          </ul>
          {requestsQuery.data && requestsQuery.data.results.length === 0 && (
            <p className="field__hint">No privacy request so far.</p>
          )}
        </Card>
      </div>
    </div>
  )
}
