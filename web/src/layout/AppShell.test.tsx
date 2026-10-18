import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from '../auth/AuthContext'
import { setAccessToken, storeRefreshToken } from '../lib/api'
import type { User } from '../lib/types'
import { jsonResponse, stubFetch } from '../test/helpers'
import { AppShell } from './AppShell'
import { NAV_ITEMS, filterNavItems, type NavItem } from './nav'

const baseUser: User = {
  id: 5,
  email: 'buyer.demo@example.test',
  first_name: 'Demo',
  last_name: 'Buyer',
  full_name: 'Demo Buyer',
  is_verified: true,
  is_platform_admin: false,
  mfa_enabled: false,
  roles: [
    {
      id: 3,
      role: 'buyer',
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

function renderShell(userOverrides: Partial<User> = {}) {
  storeRefreshToken('refresh-1')
  const fetcher = stubFetch()
  fetcher.on('/users/me/', () =>
    jsonResponse({ ...baseUser, ...userOverrides }),
  )
  fetcher.on('/auth/logout/', () => jsonResponse(null, 204))

  render(
    <MemoryRouter initialEntries={['/account']}>
      <AuthProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/account" element={<div>Account content</div>} />
          </Route>
          <Route path="/login" element={<div data-testid="login">Login</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
  return fetcher
}

describe('filterNavItems', () => {
  const items: NavItem[] = [
    { to: '/account', label: 'Account', icon: '◍' },
    { to: '/admin', label: 'Admin', icon: '◆', roles: ['platform_admin'] },
    { to: '/orders', label: 'Orders', icon: '▤', roles: ['buyer', 'supplier'] },
  ]

  it('keeps items without roles for everyone', () => {
    const visible = filterNavItems(items, () => true)
    expect(visible.map((item) => item.to)).toEqual(['/account', '/admin', '/orders'])
  })

  it('drops items whose roles the user lacks', () => {
    const visible = filterNavItems(items, (roles) => roles?.includes('buyer') ?? true)
    expect(visible.map((item) => item.to)).toEqual(['/account', '/orders'])
  })
})

describe('AppShell', () => {
  beforeEach(() => {
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('renders the brand, the user chip and the registered navigation', async () => {
    renderShell()

    expect(await screen.findByText('Demo Buyer')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /account/i }),
    ).toHaveAttribute('aria-current', 'page')
    expect(NAV_ITEMS.map((item) => item.to)).toEqual(['/account'])
  })

  it('signs out and returns to the login page', async () => {
    const user = userEvent.setup()
    const fetcher = renderShell()

    await user.click(await screen.findByRole('button', { name: 'Sign out' }))

    expect(await screen.findByTestId('login')).toBeInTheDocument()
    expect(
      fetcher.calls.some((call) => call.url.includes('/auth/logout/')),
    ).toBe(true)
  })

  it('closes the mobile drawer with the Escape key', async () => {
    const user = userEvent.setup()
    renderShell()

    const toggle = await screen.findByRole('button', { name: 'Open menu' })
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')

    await user.keyboard('{Escape}')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
  })
})
