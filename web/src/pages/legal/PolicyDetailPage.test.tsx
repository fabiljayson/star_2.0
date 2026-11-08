import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import type { PolicyDetail } from '../../lib/types'
import { setAccessToken, storeRefreshToken } from '../../lib/api'
import { jsonResponse, stubFetch } from '../../test/helpers'
import { renderPage } from '../../test/render'
import { PolicyDetailPage } from './PolicyDetailPage'

const englishPolicy: PolicyDetail = {
  id: 'pv-en',
  policy_slug: 'terms-of-service',
  policy_summary: 'Rules for using the STAR platform.',
  language: 'en',
  version: '1.0',
  status: 'published',
  title: 'Terms of Service',
  body: [
    'Intro sentence.',
    '',
    '## 1. Acceptance',
    'You accept by using STAR.',
    '',
    '## 2. Accounts',
    'Keep your credentials safe.',
  ].join('\n'),
  effective_date: '2026-10-20',
  published_at: '2026-10-20T09:00:00Z',
  last_reviewed_at: '2026-10-19',
  translation_of: null,
  related: [{ slug: 'privacy-policy', title: 'Privacy Policy' }],
}

const frenchPolicy: PolicyDetail = {
  ...englishPolicy,
  id: 'pv-fr',
  language: 'fr',
  title: "Conditions d'utilisation",
  body: 'Intro.\n\n## 1. Acceptation\nVos conditions.',
  translation_of: { id: 'pv-en', language: 'en', version: '1.0' },
}

function registerPolicies(fetcher: ReturnType<typeof stubFetch>): void {
  fetcher.on('/legal/policies/terms-of-service/?lang=en', () =>
    jsonResponse(englishPolicy),
  )
  fetcher.on('/legal/policies/terms-of-service/?lang=fr', () =>
    jsonResponse(frenchPolicy),
  )
}

beforeEach(() => {
  setAccessToken(null)
  storeRefreshToken(null)
})

describe('PolicyDetailPage', () => {
  it('renders title, version metadata and the section links', async () => {
    const fetcher = stubFetch()
    registerPolicies(fetcher)

    renderPage(<PolicyDetailPage />, {
      route: '/legal/policies/terms-of-service?lang=en',
      path: '/legal/policies/:slug',
    })

    expect(await screen.findByText('Terms of Service')).toBeInTheDocument()
    expect(screen.getByText('Version 1.0')).toBeInTheDocument()
    expect(screen.getByText('Language: EN')).toBeInTheDocument()
    const tocLink = screen.getByRole('link', { name: '2. Accounts' })
    expect(tocLink.getAttribute('href')).toBe('#2-accounts')
    expect(screen.getByText('Keep your credentials safe.')).toBeInTheDocument()
  })

  it('links to the French translation and related policies', async () => {
    const fetcher = stubFetch()
    registerPolicies(fetcher)

    renderPage(<PolicyDetailPage />, {
      route: '/legal/policies/terms-of-service?lang=en',
      path: '/legal/policies/:slug',
    })

    const languageLink = await screen.findByRole('link', { name: 'Français' })
    expect(languageLink.getAttribute('href')).toContain('lang=fr')
    expect(screen.getByRole('link', { name: 'Privacy Policy' })).toBeInTheDocument()
  })

  it('shows a friendly error for an unknown policy slug', async () => {
    const fetcher = stubFetch()
    fetcher.on('/legal/policies/', () =>
      jsonResponse({ detail: 'No published version.' }, 404),
    )

    renderPage(<PolicyDetailPage />, {
      route: '/legal/policies/does-not-exist?lang=en',
      path: '/legal/policies/:slug',
    })

    expect(await screen.findByText('Not available')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /back to the policy center/i }),
    ).toBeInTheDocument()
  })
})
