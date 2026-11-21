import { useQuery } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import { Badge } from '../../components/Badge'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { formatDate } from '../../lib/format'
import { pickLanguage, policyStatusLabel } from '../../lib/legal'
import type { PolicyVersionHistoryItem } from '../../lib/types'

export function PolicyHistoryPage() {
  const [params] = useSearchParams()
  const language = pickLanguage(params.get('lang'))
  const otherLanguage = language === 'en' ? 'fr' : 'en'
  const { slug = '' } = useParams()
  const { isPending, isError, error, data, refetch } = useQuery({
    queryKey: ['legal-policy-history', slug, language],
    queryFn: () =>
      apiFetch<{ results: PolicyVersionHistoryItem[] }>(
        `/legal/policies/${slug}/versions/?lang=${language}`,
      ),
  })

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Version history</h1>
          <p className="page__subtitle">
            Every state of this policy in {language.toUpperCase()}: published,
            superseded, archived. Drafts are only visible in the admin
            workbench.
          </p>
        </div>
        <div className="badge-row">
          <Link
            to={`/legal/policies/${slug}?lang=${otherLanguage}`}
            className="btn btn--secondary btn--sm"
          >
            {otherLanguage === 'fr' ? 'Français' : 'English'}
          </Link>
          <Link to="/legal" className="btn btn--ghost btn--sm">
            Back to the Policy Center
          </Link>
        </div>
      </header>
      {isPending && !data && (
        <div className="page-loading" role="status">
          <Spinner size="md" label="Loading history…" />
        </div>
      )}
      {isError && !data && (
        <ErrorState
          message={error instanceof Error ? error.message : 'Could not load history.'}
          onRetry={() => void refetch()}
        />
      )}
      {data && (
        <Card title="Versions">
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Published</th>
                  <th>Effective</th>
                  <th>Last reviewed</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((version) => (
                  <tr key={version.id}>
                    <td>
                      v{version.version} · {version.language.toUpperCase()}
                    </td>
                    <td>
                      <Badge
                        tone={
                          version.status === 'published'
                            ? 'success'
                            : version.status === 'superseded'
                              ? 'warning'
                              : 'neutral'
                        }
                      >
                        {policyStatusLabel(version.status)}
                      </Badge>
                    </td>
                    <td>{formatDate(version.published_at)}</td>
                    <td>{formatDate(version.effective_date)}</td>
                    <td>{formatDate(version.last_reviewed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.results.length === 0 && (
            <p className="field__hint">
              No published version yet for this language.
            </p>
          )}
        </Card>
      )}
    </div>
  )
}
