import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { setAccessToken, storeRefreshToken } from '../../lib/api'
import { jsonResponse, stubFetch } from '../../test/helpers'
import { makeUser, renderPage } from '../../test/render'
import type { SupplierProfileValue } from '../../lib/types'
import { PlatformAdminPage } from './PlatformAdminPage'

type Fetcher = ReturnType<typeof stubFetch>

const supplier: SupplierProfileValue = {
  id: 'sup-1',
  user: 'user-55',
  company_name: 'Demo Surgical Supplies',
  contact_email: 'supplier.demo@example.test',
  contact_phone: '+221 77 000 00 00',
  address: '',
  commercial_notes: '',
  verification_status: 'pending',
  verified_at: null,
  suspension_reason: '',
  created_at: '2026-10-01T08:00:00Z',
}

function registerAdmin(fetcher: Fetcher): void {
  fetcher.on('/marketplace/admin/suppliers/', () => jsonResponse([supplier]))
  fetcher.on(/\/marketplace\/admin\/suppliers\/[^/]+\/(verify|reject|suspend)\//, () =>
    jsonResponse({ ...supplier, verification_status: 'verified' }),
  )
}

describe('PlatformAdminPage', () => {
  beforeEach(() => {
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('verifies a pending supplier from the moderation queue', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    storeRefreshToken('refresh-1')
    fetcher.on('/users/me/', () =>
      jsonResponse(makeUser({ is_platform_admin: true })),
    )
    registerAdmin(fetcher)

    renderPage(<PlatformAdminPage />, { route: '/admin' })

    expect(await screen.findByText('Demo Surgical Supplies')).toBeInTheDocument()
    expect(screen.getByText('pending')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Verify' }))

    await waitFor(() =>
      expect(
        fetcher.calls.some(
          (call) =>
            call.url.includes('/marketplace/admin/suppliers/sup-1/verify/') &&
            call.init?.method === 'POST',
        ),
      ).toBe(true),
    )
  })

  it('refuses the workspace for accounts without platform administrator rights', async () => {
    const fetcher = stubFetch()
    storeRefreshToken('refresh-1')
    fetcher.on('/users/me/', () => jsonResponse(makeUser()))

    renderPage(<PlatformAdminPage />, { route: '/admin' })

    expect(
      await screen.findByText('Platform administrator access required'),
    ).toBeInTheDocument()
  })
})
