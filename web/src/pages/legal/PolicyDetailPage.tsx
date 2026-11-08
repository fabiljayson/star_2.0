import { useQuery } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import { Badge } from '../../components/Badge'
import { Card } from '../../components/Card'
import { Spinner } from '../../components/Spinner'
import { formatDate, formatDateTime } from '../../lib/format'
import { policySections, pickLanguage } from '../../lib/legal'
import type { PolicyDetail, PolicyLanguage } from '../../lib/types'

// Public route. The server only serves published versions here — a draft can
// never appear as a binding document.
export function PolicyDetailPage() {
  const [params] = useSearchParams()
  const language = pickLanguage(params.get('lang'))
  const { slug = '' } = useParams()
  const { isPending, isError, error, data } = useQuery({
    queryKey: ['legal-policy', slug, language],
    queryFn: () => apiFetch<PolicyDetail>(`/legal/policies/${slug}/?lang=${language}`),
    retry: false,
  })
  const relatedLanguage: PolicyLanguage =
    data?.translation_of?.language ?? (data?.language === 'fr' ? 'en' : 'fr')
  const { data: otherLanguage } = useQuery({
    queryKey: ['legal-policy', slug, relatedLanguage],
    queryFn: () =>
      apiFetch<PolicyDetail>(`/legal/policies/${slug}/?lang=${relatedLanguage}`),
    enabled: data !== undefined,
    retry: false,
  })
  const sections = data ? policySections(data) : []

  return (
    <div className="page policy-detail">
      {isError && (
        <Card title="Not available">
          <p className="field__hint">
            {error instanceof Error && error.message
              ? error.message
              : 'There is no published version of this policy yet.'}
          </p>
          <Link to="/legal" className="btn btn--secondary btn--sm">
            Back to the Policy Center
          </Link>
        </Card>
      )}
      {isPending && !data && !isError && (
        <div className="page-loading" role="status">
          <Spinner size="md" label="Loading policy…" />
        </div>
      )}
      {data && !isError && (
        <>
          <header className="page__header">
            <div>
              <h1 className="page__title">{data.title}</h1>
              <p className="page__subtitle">
                Published document · effective {formatDate(data.effective_date)}
              </p>
            </div>
            <div className="badge-row">
              {otherLanguage && (
                <Link
                  to={`/legal/policies/${data.policy_slug}?lang=${relatedLanguage}`}
                  className="btn btn--secondary btn--sm"
                >
                  {data.language === 'en' ? 'Français' : 'English'}
                </Link>
              )}
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => window.print()}
              >
                Print-friendly
              </button>
              <Link to="/legal" className="btn btn--secondary btn--sm">
                Back to the Policy Center
              </Link>
            </div>
          </header>

          <div className="badge-row">
            <Badge tone="info">Language: {data.language.toUpperCase()}</Badge>
            <Badge tone="success">Version {data.version}</Badge>
            <Badge tone="neutral">Published {formatDateTime(data.published_at)}</Badge>
            {data.last_reviewed_at && (
              <Badge tone="neutral">Last reviewed {formatDate(data.last_reviewed_at)}</Badge>
            )}
            {data.translation_of && (
              <Badge tone="neutral">
                Translation of {data.translation_of.language.toUpperCase()}{' '}
                {data.translation_of.version}
              </Badge>
            )}
          </div>

          <div className="policy-detail__body">
            <Card title="Contents">
              <ul className="policy-toc">
                {sections.map((section) => (
                  <li key={section.id}>
                    <a href={`#${section.id}`}>{section.heading}</a>
                  </li>
                ))}
              </ul>
            </Card>
            <Card title="Text">
              {sections.map((section) => (
                <section key={section.id} className="policy-section" id={section.id}>
                  <h3>{section.heading}</h3>
                  {section.body.split('\n\n').map((block, index) => (
                    <p key={index}>{block}</p>
                  ))}
                </section>
              ))}
              {Array.isArray(data.related) && data.related.length > 0 && (
                <div className="badge-row">
                  <strong>Related:</strong>
                  {data.related.map((item) => (
                    <Link
                      key={item.slug}
                      to={`/legal/policies/${item.slug}?lang=${data.language}`}
                      className="btn btn--ghost btn--sm"
                    >
                      {item.title}
                    </Link>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </>
      )}
      
    </div>
  )
}
