import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { apiFetch } from '../lib/api'
import { formatDate } from '../lib/format'
import { pickLanguage } from '../lib/legal'
import type { PolicyDetail } from '../lib/types'
import { Button } from './Button'

// The Terms of Service changed and this session has not accepted the new text.
// Acceptance is confirmed by the server before the banner disappears: the
// user object is refetched, so a failed POST keeps the notice visible.
export function TermsUpdateBanner() {
  const { user, refreshUser } = useAuth()
  const queryClient = useQueryClient()
  const [hidden, setHidden] = useState(false)

  const required = Boolean(user?.requires_terms_acceptance)
  const language = pickLanguage(typeof navigator === 'undefined' ? 'en' : navigator.language)

  const termsQuery = useQuery({
    queryKey: ['legal-current-terms', language],
    queryFn: () =>
      apiFetch<PolicyDetail>(`/legal/policies/terms-of-service/?lang=${language}`),
    enabled: required,
    retry: false,
  })

  const acceptMutation = useMutation({
    mutationFn: (detail: PolicyDetail) =>
      apiFetch('/legal/consents/', {
        method: 'POST',
        body: {
          policy_slug: 'terms-of-service',
          version: detail.version,
          language: detail.language,
          context: 'account',
        },
      }),
    onSuccess: async () => {
      await refreshUser()
      void queryClient.invalidateQueries({ queryKey: ['legal-consent-status'] })
      void queryClient.invalidateQueries({ queryKey: ['legal-consents-mine'] })
    },
  })

  if (!required || hidden) return null

  const detail = termsQuery.data
  const versionLabel = detail ? `version ${detail.version}` : 'a new version'
  const effective = detail?.effective_date ? ` (effective ${formatDate(detail.effective_date)})` : ''

  return (
    <section
      className="terms-banner"
      aria-labelledby="terms-banner-title"
      role="region"
    >
      <div className="terms-banner__body">
        <h2 className="terms-banner__title" id="terms-banner-title">
          Our Terms of Service have changed
        </h2>
        <p className="terms-banner__text">
          You need to accept {versionLabel}
          {effective} to keep publishing listings, checking out or renewing a
          seller subscription. Your earlier acceptances stay on record.
        </p>
        {termsQuery.isError && (
          <p className="form-alert" role="alert">
            Could not load the new Terms. Please try again.
          </p>
        )}
        {acceptMutation.isError && (
          <p className="form-alert" role="alert">
            {acceptMutation.error instanceof Error
              ? acceptMutation.error.message
              : 'Could not record your acceptance.'}
          </p>
        )}
        <div className="terms-banner__actions">
          <Button
            loading={acceptMutation.isPending}
            disabled={!detail}
            onClick={() => {
              if (detail) acceptMutation.mutate(detail)
            }}
          >
            I accept the new Terms
          </Button>
          <Link className="btn btn--secondary btn--sm" to="/legal/policies/terms-of-service">
            Read the full text
          </Link>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setHidden(true)}
          >
            Ask me later
          </Button>
        </div>
      </div>
    </section>
  )
}
