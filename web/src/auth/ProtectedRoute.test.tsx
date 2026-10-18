import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './AuthContext'
import { ProtectedRoute } from './ProtectedRoute'
import { setAccessToken, storeRefreshToken } from '../lib/api'
import type { User } from '../lib/types'
import { jsonResponse, stubFetch } from '../test/helpers'

function makeUser(role: string): User {
  return {
    id: 2,
    email: 'someone@example.test',
    first_name: 'Some',
    last_name: 'One',
    full_name: 'Some One',
    is_verified: true,
    is_platform_admin: false,
    mfa_enabled: false,
    roles: [
      {
        id: 1,
        role,
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
}

function renderGuarded(roles?: string[]) {
  return render(
    <MemoryRouter initialEntries={['/private']}>
      <AuthProvider>
        <Routes>
          <Route
            path="/private"
            element={
              <ProtectedRoute roles={roles}>
                <div data-testid="secret">Secret workspace</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div data-testid="login">Login</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('redirects anonymous visitors to the login page', async () => {
    stubFetch()
    renderGuarded()

    expect(await screen.findByTestId('login')).toBeInTheDocument()
    expect(screen.queryByTestId('secret')).not.toBeInTheDocument()
  })

  it('shows a session-restore placeholder while booting', () => {
    storeRefreshToken('refresh-1')
    const fetcher = stubFetch()
    fetcher.on('/users/me/', () => new Promise<Response>(() => {}))

    renderGuarded()

    expect(screen.getByText('Restoring your session…')).toBeInTheDocument()
  })

  it('renders the guarded content when the role matches', async () => {
    storeRefreshToken('refresh-1')
    const fetcher = stubFetch()
    fetcher.on('/users/me/', () => jsonResponse(makeUser('institution_admin')))

    renderGuarded(['institution_admin'])

    expect(await screen.findByTestId('secret')).toBeInTheDocument()
  })

  it('shows the access-denied page when the role is missing', async () => {
    storeRefreshToken('refresh-1')
    const fetcher = stubFetch()
    fetcher.on('/users/me/', () => jsonResponse(makeUser('buyer')))

    renderGuarded(['institution_admin'])

    expect(
      await screen.findByRole('heading', { name: /don't have access/i }),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('secret')).not.toBeInTheDocument()
  })
})
