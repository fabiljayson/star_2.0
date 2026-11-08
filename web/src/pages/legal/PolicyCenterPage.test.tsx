import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import type { PolicyListItem } from '../../lib/types'
import { setAccessToken, storeRefreshToken } from '../../lib/api'
import { jsonResponse, stubFetch } from '../../test/helpers'
import { renderPage } from '../../test/render'
import { PolicyCenterPage } from './PolicyCenterPage'

function makePolicy(overrides: Partial<PolicyListItem> = {}): PolicyListItem {
  return {
    id: 'pol-1',
    slug: 'terms-of-service',
    title: 'Terms of Service',
    category: 'terms',
    summary: 'Rules for using the STAR platform.',
    published_versions: [
      {
        id: 'pv-1',
        language: 'en',
        version: '1.0',
        status: 'published',
        published_at: '2026-10-20T09:00:00Z',
        effective_date: '2026-10-20',
      },
      {
        id: 'pv-2',
        language: 'fr',
        version: '1.0',
        status: 'published',
        published_at: '2026-10-20T09:00:00Z',
        effective_date: '2026-10-20',
      },
    ],
    ...overrides,
  }
}

beforeEach(() => {
  setAccessToken(null)
  storeRefreshToken(null)
})

describe('PolicyCenterPage', () => {
  it('renders published policies with category badges and links', async () => {
    const fetcher = stubFetch()
    fetcher.on('/legal/policies/', () =>
      jsonResponse({ count: 2, next: null, previous: null, results: [makePolicy(), makePolicy({ id: 'pol-2', slug: 'privacy-policy', title: 'Privacy Policy', category: 'privacy' })] }),
    )

    renderPage(<PolicyCenterPage />, { route: '/legal' })

    expect(await screen.findByText('Privacy Policy')).toBeInTheDocument()
    expect(screen.getByText('Privacy')).toBeInTheDocument()
    expect(screen.getByText('Terms of Service', { selector: 'h2' })).toBeInTheDocument()
    const readLinks = screen.getAllByRole('link', { name: 'Read' })
    expect(readLinks.map((link) => link.getAttribute('href'))).toEqual(
      expect.arrayContaining([
        expect.stringContaining('/legal/policies/terms-of-service'),
        expect.stringContaining('/legal/policies/privacy-policy'),
      ]),
    )
    expect(screen.getAllByRole('link', { name: 'Version history' })).toHaveLength(2)
  })

  it('switches to the French listing when the language button is used', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    fetcher.on('/legal/policies/', () =>
      jsonResponse({ count: 1, next: null, previous: null, results: [] }),
    )

    renderPage(<PolicyCenterPage />, { route: '/legal' })
    await screen.findByText('Nothing published yet')

    await user.click(screen.getByRole('link', { name: 'Français' }))

    expect(await screen.findByText('Nothing published yet')).toBeInTheDocument()
    const policyCalls = fetcher.calls.map((call) => call.url).filter((url) => url.includes('/legal/policies/'))
    expect(policyCalls.some((url) => url.includes('lang=fr'))).toBe(true)
  })

  it('shows the empty state when nothing is published in the language', async () => {
    const fetcher = stubFetch()
    fetcher.on('/legal/policies/', () => jsonResponse({ count: 0, next: null, previous: null, results: [] }))

    renderPage(<PolicyCenterPage />, { route: '/legal' })

    expect(await screen.findByText('Nothing published yet')).toBeInTheDocument()
  })
})
