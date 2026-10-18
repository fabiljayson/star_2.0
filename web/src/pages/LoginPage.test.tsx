import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from '../auth/AuthContext'
import { setAccessToken, storeRefreshToken } from '../lib/api'
import { jsonResponse, stubFetch } from '../test/helpers'
import { LoginPage } from './LoginPage'

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div data-testid="home">Home</div>} />
          <Route path="/mfa" element={<div data-testid="mfa-page">MFA</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('shows field errors and skips the request when the form is empty', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()

    renderLogin()
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(screen.getByText('Email is required.')).toBeInTheDocument()
    expect(screen.getByText('Password is required.')).toBeInTheDocument()
    expect(fetcher.fn).not.toHaveBeenCalled()
  })

  it('rejects a malformed email address', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()

    renderLogin()
    await user.type(screen.getByLabelText('Email'), 'not-an-email')
    await user.type(screen.getByLabelText('Password'), 'whatever12')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument()
    expect(fetcher.fn).not.toHaveBeenCalled()
  })

  it('shows the API error message when credentials are rejected', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    fetcher.on('/auth/login/', () =>
      jsonResponse(
        { error: { code: 'invalid_credentials', message: 'Invalid email or password.' } },
        401,
      ),
    )

    renderLogin()
    await user.type(screen.getByLabelText('Email'), 'buyer.demo@example.test')
    await user.type(screen.getByLabelText('Password'), 'wrong-password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Invalid email or password.',
    )
  })

  it('signs in and navigates to the app on success', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    fetcher.on('/auth/login/', () =>
      jsonResponse({
        mfa_required: false,
        access: 'access-1',
        refresh: 'refresh-1',
        user: {
          id: 1,
          email: 'buyer.demo@example.test',
          first_name: 'Demo',
          last_name: 'Buyer',
          full_name: 'Demo Buyer',
          is_verified: true,
          is_platform_admin: false,
          mfa_enabled: false,
          roles: [],
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      }),
    )

    renderLogin()
    await user.type(screen.getByLabelText('Email'), 'buyer.demo@example.test')
    await user.type(screen.getByLabelText('Password'), 'Demo!Passw0rd2026')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByTestId('home')).toBeInTheDocument()
  })

  it('routes to the MFA step when the account requires a second factor', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    fetcher.on('/auth/login/', () =>
      jsonResponse({ mfa_required: true, mfa_token: 'mfa-1', expires_in: 300 }),
    )

    renderLogin()
    await user.type(screen.getByLabelText('Email'), 'platform-admin@demo.test')
    await user.type(screen.getByLabelText('Password'), 'Demo!Passw0rd2026')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByTestId('mfa-page')).toBeInTheDocument()
    await waitFor(() =>
      expect(
        fetcher.calls.some((call) => call.url.includes('/auth/login/')),
      ).toBe(true),
    )
  })
})
