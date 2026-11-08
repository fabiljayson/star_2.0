import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import { Badge } from '../../components/Badge'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { formatDate } from '../../lib/format'
import { pickLanguage, POLICY_CATEGORY_LABELS } from '../../lib/legal'
import type { PolicyListItem } from '../../lib/types'

// Public route: the overview of the Policies & Legal Center. Drafts exist
// only in the admin workbench; everything here is published content.
export function PolicyCenterPage() {
  const [params] = useSearchParams()
  const language = pickLanguage(params.get('lang'))
  const { isPending, isError, error, data, refetch } = useQuery({
    queryKey: ['legal-policies', language],
    queryFn: () =>
      apiFetch<{ count: number; results: PolicyListItem[] }>(
        `/legal/policies/?lang=${language}`,
      ),
  })

  return (
    <div className="page policy-page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Policies &amp; Legal Center</h1>
          <p className="page__subtitle">
            How STAR handles your data, your consent, the marketplace and your
            subscriptions. Only published documents appear here.
          </p>
        </div>
        <div className="badge-row">
          <Link
            to={`/legal?lang=${language === 'fr' ? 'en' : 'fr'}`}
            className="btn btn--secondary btn--sm"
          >
            {language === 'fr' ? 'English' : 'Français'}
          </Link>
        </div>
      </header>

      {isError && !data && (
        <ErrorState message={error instanceof Error ? error.message : 'Could not load policies.'} onRetry={() => void refetch()} />
      )}
      {isPending && !data && (
        <div className="page-loading" role="status">
          <Spinner size="md" label="Loading policies…" />
        </div>
      )}
      <div className="policy-grid">
        {(data?.results ?? []).map((policy) => (
          <Card key={policy.slug} title={policy.title}>
            <div className="badge-row">
              <Badge tone="neutral">
                {POLICY_CATEGORY_LABELS[policy.category] ?? policy.category}
              </Badge>
              {policy.published_versions
                .filter((version) => version.language === language)
                .concat(
                  policy.published_versions.filter(
                    (version) => version.language !== language,
                  ),
                )
                .slice(0, 2)
                .map((version) => (
                  <Badge
                    key={version.id}
                    tone={version.language === language ? 'success' : 'neutral'}
                  >
                    v{version.version} ·{' '}
                    {version.language === language ? 'current' : version.language}
                  </Badge>
                ))}
            </div>
            <p className="field__hint">{policy.summary}</p>
            {(() => {
              const current = policy.published_versions.find(
                (version) => version.language === language,
              )
              return (
                current && (
                  <p className="field__hint">
                    Effective {formatDate(current.effective_date)} · published{' '}
                    {formatDate(current.published_at)}
                  </p>
                )
              )
            })()}
            <div className="badge-row">
              <Link
                to={`/legal/policies/${policy.slug}?lang=${language}`}
                className="btn btn--primary btn--sm"
              >
                Read
              </Link>
              <Link
                to={`/legal/policies/${policy.slug}/history?lang=${language}`}
                className="btn btn--ghost btn--sm"
              >
                Version history
              </Link>
            </div>
          </Card>
        ))}
      </div>
      {data && data.results.length === 0 && (
        <Card title="Nothing published yet">
          <p className="field__hint">
            The operator has not published any policy in this language yet.
          </p>
        </Card>
      )}
    </div>
  )
}
