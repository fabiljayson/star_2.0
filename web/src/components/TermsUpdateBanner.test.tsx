import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '../auth/AuthContext'
import { setAccessToken, storeRefreshToken } from '../lib/api'
import type { PolicyDetail, User } from '../lib/types'
import { jsonResponse, stubFetch } from '../test/helpers'
import { AppShell } from '../layout/AppShell'

const user: User = {
  id: 'user-7',
  email: 'surgeon@example.test',
  first_name: 'Demo',
  last_name: 'Surgeon',
  full_name: 'Demo Surgeon',
  is_verified: true,
  is_platform_admin: false,
  mfa_enabled: false,
  roles: [
    {
      id: 'role-1',
      role: 'surgeon',
      institution: null,
      institution_name: null,
      department: null,
      department_name: null,
      is_active: true,
    },
  ],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const terms: PolicyDetail = {
  id: 'ver-terms-3',
  policy_slug: 'terms-of-service',
  policy_summary: 'Rules for using STAR.',
  language: 'en',
  version: '3',
  status: 'published',
  title: 'Terms of Service',
  body: '## 1. Acceptance\n\nBy using STAR you agree to these terms.',
  effective_date: '2026-11-01',
  published_at: '2026-10-20T10:00:00Z',
  last_reviewed_at: null,
  translation_of: null,
}

let requiresTerms = true

function renderBanner() {
  storeRefreshToken('refresh-1')
  const fetcher = stubFetch()
  fetcher.on('/users/me/', () =>
    jsonResponse({ ...user, requires_terms_acceptance: requiresTerms }),
  )
  fetcher.on('/legal/policies/terms-of-service/', () => jsonResponse(terms))
  fetcher.on('/legal/consents/', () => {
    requiresTerms = false
    return jsonResponse({ id: 'consent-1', version: '3' }, 201)
  })
  fetcher.on('/notifications/unread-count/', () => jsonResponse({ count: 0 }))
  fetcher.on('/auth/logout/', () => jsonResponse(null, 204))

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })

  render(
    <MemoryRouter initialEntries={['/account']}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/account" element={<div>Account content</div>} />
            </Route>
          </Routes>
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
  return fetcher
}

describe('TermsUpdateBanner', () => {
  beforeEach(() => {
    requiresTerms = true
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('stays hidden when the session has accepted the current version', async () => {
    requiresTerms = false
    renderBanner()

    expect(await screen.findByText('Demo Surgeon')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: /terms of service/i })).not.toBeInTheDocument()
  })

  it('accepts the published version and disappears once the server agrees', async () => {
    const browser = userEvent.setup()
    const fetcher = renderBanner()

    const banner = await screen.findByRole('region', {
      name: /terms of service have changed/i,
    })
    await waitFor(() => expect(banner).toHaveTextContent('version 3'))

    await browser.click(
      screen.getByRole('button', { name: 'I accept the new Terms' }),
    )

    const consentCall = fetcher.calls.find(
      (call) => call.url.includes('/legal/consents/') && call.init?.method === 'POST',
    )
    expect(consentCall).toBeDefined()
    expect(JSON.parse(String(consentCall?.init?.body))).toMatchObject({
      policy_slug: 'terms-of-service',
      version: '3',
      language: 'en',
      context: 'account',
    })

    expect(
      await screen.findByText('Account content'),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('region', { name: /terms of service have changed/i }),
    ).not.toBeInTheDocument()
  })

  it('can be dismissed for the session without recording consent', async () => {
    const browser = userEvent.setup()
    const fetcher = renderBanner()

    await screen.findByRole('region', { name: /terms of service have changed/i })
    await browser.click(screen.getByRole('button', { name: 'Ask me later' }))

    expect(
      screen.queryByRole('region', { name: /terms of service have changed/i }),
    ).not.toBeInTheDocument()
    expect(
      fetcher.calls.some(
        (call) => call.url.includes('/legal/consents/') && call.init?.method === 'POST',
      ),
    ).toBe(false)
  })
})
