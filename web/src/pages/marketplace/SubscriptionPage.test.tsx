import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { setAccessToken, storeRefreshToken } from '../../lib/api'
import { jsonResponse, stubFetch } from '../../test/helpers'
import { makeUser, renderPage } from '../../test/render'
import { SubscriptionPage } from './SubscriptionPage'

type Fetcher = ReturnType<typeof stubFetch>

const PLANS = [
  { plan: 'monthly' as const, price_fcfa: 5000, duration_months: 1 },
  { plan: 'semiannual' as const, price_fcfa: 10000, duration_months: 6 },
  { plan: 'annual' as const, price_fcfa: 12000, duration_months: 12 },
]

function activeStatus() {
  return {
    status: 'active',
    plan: 'monthly',
    amount_fcfa: 5000,
    currency: 'XOF',
    starts_at: '2026-10-01T00:00:00Z',
    expires_at: new Date(Date.now() + 2 * 86_400 * 1000).toISOString(),
    server_now: new Date().toISOString(),
    can_publish: true,
    remaining_seconds: 2 * 86_400,
    renewal_available: true,
    visibility_policy: 'visible_while_active',
    plans: PLANS,
  }
}

function expiredStatus() {
  return {
    status: 'expired',
    plan: null,
    amount_fcfa: 2500,
    currency: 'XOF',
    starts_at: null,
    expires_at: null,
    server_now: new Date().toISOString(),
    can_publish: false,
    remaining_seconds: 0,
    renewal_available: true,
    visibility_policy: 'hidden_while_inactive',
    plans: PLANS,
  }
}

function registerSupplier(fetcher: Fetcher, status: object = activeStatus()): void {
  fetcher.on('/users/me/', () =>
    jsonResponse(
      makeUser({
        roles: [
          {
            id: 'role-1',
            role: 'supplier',
            institution: null,
            institution_name: null,
            department: null,
            department_name: null,
            is_active: true,
          },
        ],
      }),
    ),
  )
  fetcher.on('/marketplace/subscription/', () => jsonResponse(status))
}

describe('SubscriptionPage', () => {
  beforeEach(() => {
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('shows the active status with a server-derived countdown and plans', async () => {
    const fetcher = stubFetch()
    storeRefreshToken('refresh-1')
    registerSupplier(fetcher)
    renderPage(<SubscriptionPage />, { route: '/marketplace/subscription' })

    expect(await screen.findByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Expiring soon')).toBeInTheDocument()
    expect(screen.getByText(/remaining 1d 23h/)).toBeInTheDocument()
    // Plans come from the server payload, never a client-side table.
    expect(screen.getByText('5,000 FCFA')).toBeInTheDocument()
    expect(screen.getByText('12,000 FCFA')).toBeInTheDocument()
  })

  it('shows the expired state with the hidden-listings explanation', async () => {
    const fetcher = stubFetch()
    storeRefreshToken('refresh-1')
    registerSupplier(fetcher, expiredStatus())
    renderPage(<SubscriptionPage />, { route: '/marketplace/subscription' })

    expect(
      await screen.findByText('Your seller subscription has expired'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/hidden from public buyers until you renew/i),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Subscribe' }).length).toBe(3)
  })

  it('starts a checkout but does not claim success before the server verifies', async () => {
    const fetcher = stubFetch()
    storeRefreshToken('refresh-1')
    registerSupplier(fetcher)
    fetcher.on('/marketplace/subscription/checkout/', () =>
      jsonResponse(
        {
          id: 'pay-1',
          subscription: 'sub-1',
          provider: 'sandbox',
          status: 'pending',
          amount: '5000',
          currency: 'XOF',
          provider_reference: null,
          failure_reason: '',
          paid_at: null,
          created_at: new Date().toISOString(),
        },
        201,
      ),
    )
    renderPage(<SubscriptionPage />, { route: '/marketplace/subscription' })

    const user = userEvent.setup()
    const renewButton = await screen.findByRole('button', { name: 'Renew this plan' })
    await user.click(renewButton)

    await waitFor(() => {
      const checkout = fetcher.calls.find((call) =>
        call.url.includes('/marketplace/subscription/checkout/'),
      )
      const body = JSON.parse(String(checkout?.init?.body ?? '{}'))
      expect(body.plan).toBe('monthly')
    })
    expect(screen.getByText(/server confirms the outcome/i)).toBeInTheDocument()
    // No fake success message for an unresolved payment.
    expect(screen.queryByText(/Payment confirmed/i)).not.toBeInTheDocument()
  })

  it('rejects non-supplier users with an explanatory state', async () => {
    const fetcher = stubFetch()
    storeRefreshToken('refresh-1')
    fetcher.on('/users/me/', () => jsonResponse(makeUser()))
    fetcher.on('/marketplace/subscription/', () => jsonResponse(activeStatus()))
    renderPage(<SubscriptionPage />, { route: '/marketplace/subscription' })

    expect(
      await screen.findByText('Become a seller on STAR Marketplace'),
    ).toBeInTheDocument()
  })
})
