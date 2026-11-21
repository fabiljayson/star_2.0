import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { setAccessToken, storeRefreshToken } from '../../lib/api'
import { jsonResponse, stubFetch } from '../../test/helpers'
import { renderPage } from '../../test/render'
import { ConsentsPage } from './ConsentsPage'

function stubLegalAccount(fetcher: ReturnType<typeof stubFetch>): void {
  fetcher.on('/legal/consents/status/', () =>
    jsonResponse({
      results: [
        {
          policy: 'terms-of-service',
          title: 'Terms of Service',
          current_version: '3',
          consent_current: false,
          latest_withdrawn_at: null,
        },
        {
          policy: 'privacy-policy',
          title: 'Privacy Policy',
          current_version: '2',
          consent_current: true,
          latest_withdrawn_at: null,
        },
      ],
    }),
  )
  fetcher.on('/legal/consents/mine/', () =>
    jsonResponse({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 'consent-1',
          policy_slug: 'privacy-policy',
          policy_title: 'Privacy Policy',
          version: '2',
          context: 'account',
          withdrawn_at: null,
          withdrawn_reason: '',
          created_at: '2026-10-01T10:00:00Z',
        },
      ],
    }),
  )
  fetcher.on('/legal/privacy-requests/mine/', () =>
    jsonResponse({ count: 0, next: null, previous: null, results: [] }),
  )
  fetcher.on('/legal/privacy-requests/', () =>
    jsonResponse(
      {
        id: 'pr-1',
        kind: 'access',
        kind_label: 'Access my data',
        status: 'open',
        response_note: '',
        handled_at: null,
        created_at: '2026-11-20T10:00:00Z',
      },
      201,
    ),
  )
  fetcher.on('/legal/consents/withdraw/', () =>
    jsonResponse({ message: 'Consent withdrawn.', consent_id: 'consent-1' }),
  )
  fetcher.on('/legal/consents/', () =>
    jsonResponse(
      {
        id: 'consent-2',
        policy_slug: 'terms-of-service',
        policy_title: 'Terms of Service',
        version: '3',
        context: 'account',
        withdrawn_at: null,
        withdrawn_reason: '',
        created_at: '2026-11-20T10:00:00Z',
      },
      201,
    ),
  )
}

function renderConsents() {
  return renderPage(<ConsentsPage />, { route: '/account/consents', path: '/account/consents' })
}

beforeEach(() => {
  setAccessToken(null)
  storeRefreshToken(null)
})

describe('ConsentsPage', () => {
  it('shows current agreements, history and an empty privacy-request state', async () => {
    const fetcher = stubFetch()
    stubLegalAccount(fetcher)

    renderConsents()

    expect(await screen.findByText('Terms of Service')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Accept v3' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Withdraw' })).toBeInTheDocument()
    expect(screen.getByText('Privacy Policy — v2')).toBeInTheDocument()

    await waitFor(() =>
      expect(screen.getByText('No privacy request so far.')).toBeInTheDocument(),
    )
  })

  it('records acceptance of the published version', async () => {
    const browser = userEvent.setup()
    const fetcher = stubFetch()
    stubLegalAccount(fetcher)
    renderConsents()

    await browser.click(await screen.findByRole('button', { name: 'Accept v3' }))

    await waitFor(() =>
      expect(
        screen.getByText('Consent recorded for “Terms of Service”.'),
      ).toBeInTheDocument(),
    )
    const call = fetcher.calls.find(
      (item) => item.url.includes('/legal/consents/') && item.init?.method === 'POST',
    )
    expect(JSON.parse(String(call?.init?.body))).toEqual({
      policy_slug: 'terms-of-service',
      version: '3',
      language: 'en',
      context: 'account',
    })
  })

  it('withdraws an existing consent', async () => {
    const browser = userEvent.setup()
    const fetcher = stubFetch()
    stubLegalAccount(fetcher)
    renderConsents()

    await browser.click(await screen.findByRole('button', { name: 'Withdraw' }))

    await waitFor(() =>
      expect(screen.getByText('Consent withdrawn.')).toBeInTheDocument(),
    )
    const call = fetcher.calls.find((item) =>
      item.url.includes('/legal/consents/withdraw/'),
    )
    expect(JSON.parse(String(call?.init?.body))).toEqual({ policy: 'privacy-policy' })
  })

  it('opens a privacy request with the chosen type and message', async () => {
    const browser = userEvent.setup()
    const fetcher = stubFetch()
    stubLegalAccount(fetcher)
    renderConsents()

    await screen.findByText('Terms of Service')
    await browser.selectOptions(
      screen.getByLabelText('Request type'),
      'deletion',
    )
    await browser.type(
      screen.getByLabelText('Message'),
      'Please delete my account data after export.',
    )
    await browser.click(screen.getByRole('button', { name: 'Submit request' }))

    await waitFor(() =>
      expect(
        screen.getByText('Privacy request opened. The operator will follow up.'),
      ).toBeInTheDocument(),
    )
    const call = fetcher.calls.find(
      (item) =>
        item.url.endsWith('/legal/privacy-requests/') && item.init?.method === 'POST',
    )
    expect(JSON.parse(String(call?.init?.body))).toEqual({
      kind: 'deletion',
      message: 'Please delete my account data after export.',
    })
  })
})
