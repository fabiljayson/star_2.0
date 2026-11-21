import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { setAccessToken, storeRefreshToken } from '../../lib/api'
import { jsonResponse, stubFetch } from '../../test/helpers'
import { renderPage } from '../../test/render'
import { PolicyHistoryPage } from './PolicyHistoryPage'

function renderHistory() {
  return renderPage(<PolicyHistoryPage />, {
    route: '/legal/policies/terms-of-service/versions?lang=en',
    path: '/legal/policies/:slug/versions',
  })
}

beforeEach(() => {
  setAccessToken(null)
  storeRefreshToken(null)
})

describe('PolicyHistoryPage', () => {
  it('lists every state of the policy with dates and status', async () => {
    const fetcher = stubFetch()
    fetcher.on('/legal/policies/terms-of-service/versions/?lang=en', () =>
      jsonResponse({
        results: [
          {
            id: 'pv-3',
            language: 'en',
            version: '3.0',
            status: 'published',
            published_at: '2026-11-01T09:00:00Z',
            effective_date: '2026-11-01',
            last_reviewed_at: '2026-10-28',
          },
          {
            id: 'pv-2',
            language: 'en',
            version: '2.0',
            status: 'superseded',
            published_at: '2026-05-01T09:00:00Z',
            effective_date: '2026-05-01',
            last_reviewed_at: '2026-04-20',
          },
        ],
      }),
    )

    renderHistory()

    expect(await screen.findByText('Version history')).toBeInTheDocument()
    await screen.findByText('v3.0 · EN', {}, { timeout: 3000 })
    const rows = screen.getAllByRole('row')
    expect(rows).toHaveLength(3)

    const published = within(rows[1])
    expect(published.getByText('v3.0 · EN')).toBeInTheDocument()
    expect(published.getByText('Published')).toBeInTheDocument()
    expect(published.getAllByText(/Nov 2026/).length).toBeGreaterThan(0)

    const superseded = within(rows[2])
    expect(superseded.getByText('v2.0 · EN')).toBeInTheDocument()
    expect(superseded.getByText('Superseded')).toBeInTheDocument()

    expect(
      screen.getByRole('link', { name: 'Back to the Policy Center' }),
    ).toHaveAttribute('href', '/legal')
    expect(screen.getByRole('link', { name: 'Français' })).toHaveAttribute(
      'href',
      '/legal/policies/terms-of-service?lang=fr',
    )
  })

  it('explains that a language has no published version yet', async () => {
    const fetcher = stubFetch()
    fetcher.on('/legal/policies/privacy-policy/versions/?lang=fr', () =>
      jsonResponse({ results: [] }),
    )

    renderPage(<PolicyHistoryPage />, {
      route: '/legal/policies/privacy-policy/versions?lang=fr',
      path: '/legal/policies/:slug/versions',
    })

    expect(
      await screen.findByText('No published version yet for this language.'),
    ).toBeInTheDocument()
  })

  it('surfaces a retryable error when history fails', async () => {
    const fetcher = stubFetch()
    fetcher.on('/legal/policies/terms-of-service/versions/', () =>
      jsonResponse({ detail: 'Server error.' }, 500),
    )

    renderHistory()

    expect(
      await screen.findByText('Request failed with status 500.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })
})
