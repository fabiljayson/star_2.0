import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import type { PolicyDetail, RegisterResponse } from '../lib/types'
import { setAccessToken, storeRefreshToken } from '../lib/api'
import { emptyResponse, jsonResponse, stubFetch } from '../test/helpers'
import { makeUser, renderPage } from '../test/render'
import { RegisterPage } from './RegisterPage'

const termsV100: PolicyDetail = {
  id: 'pv-terms-en',
  policy_slug: 'terms-of-service',
  policy_summary: 'Rules for using the STAR platform.',
  language: 'en',
  version: '1.0',
  status: 'published',
  title: 'Terms of Service',
  body: '## 1. Acceptance\nYou accept by using STAR.',
  effective_date: '2026-10-20',
  published_at: '2026-10-20T09:00:00Z',
  last_reviewed_at: null,
  translation_of: null,
}

const registerResponse: RegisterResponse = {
  message: 'Account created. Check your inbox to verify the address.',
  user: makeUser({
    email: 'newcomer@example.test',
    is_verified: false,
  }),
}

function fillRegistrationForm(): Promise<void> {
  return userEvent.type(screen.getByLabelText('First name'), 'Ada')
    .then(() => userEvent.type(screen.getByLabelText('Last name'), 'Kaya'))
    .then(() => userEvent.selectOptions(screen.getByLabelText('I am registering as'), 'buyer'))
    .then(() => userEvent.type(screen.getByLabelText('Email'), 'newcomer@example.test'))
    .then(() => userEvent.type(screen.getByLabelText('Password'), 'Str0ngP@ss'))
    .then(() => userEvent.type(screen.getByLabelText('Confirm password'), 'Str0ngP@ss'))
}

beforeEach(() => {
  setAccessToken(null)
  storeRefreshToken(null)
})

describe('RegisterPage terms acceptance', () => {
  it('shows the terms checkbox from the published version and blocks submission while unchecked', async () => {
    const fetcher = stubFetch()
    fetcher.on('/legal/policies/terms-of-service/', () => jsonResponse(termsV100))
    fetcher.on('/auth/register/', () => jsonResponse(registerResponse))

    renderPage(<RegisterPage />, {
      route: '/register',
      extraRoutes: <Route path="/verify-email" element={<div>verify</div>} />,
    })

    const checkbox = await screen.findByRole('checkbox', { name: /terms of service/i })
    expect(checkbox).not.toBeChecked()
    expect(screen.getByText(/version 1\.0/i)).toBeInTheDocument()

    await fillRegistrationForm()
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByText(/accept the current terms of service/i)).toBeInTheDocument()
    expect(fetcher.calls.some((call) => call.url.includes('/auth/register/'))).toBe(false)
  })

  it('records the exact accepted version in the submission', async () => {
    const fetcher = stubFetch()
    fetcher.on('/legal/policies/terms-of-service/', () => jsonResponse(termsV100))
    fetcher.on('/auth/register/', () => jsonResponse(registerResponse, 201))

    renderPage(<RegisterPage />, {
      route: '/register',
      extraRoutes: <Route path="/verify-email" element={<div>verify</div>} />,
    })

    await screen.findByRole('checkbox', { name: /terms of service/i })
    await fillRegistrationForm()
    await userEvent.click(screen.getByRole('checkbox', { name: /terms of service/i }))
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    await screen.findAllByText(/account created/i)
    const registerCall = fetcher.calls.find((call) => call.url.includes('/auth/register/'))
    expect(registerCall).toBeTruthy()
    const body = JSON.parse(String(registerCall?.init?.body ?? '{}'))
    expect(body.accepted_terms_version).toBe('1.0')
    expect(body.email).toBe('newcomer@example.test')
  })

  it('still allows registration when no terms are published (demo mode)', async () => {
    const fetcher = stubFetch()
    fetcher.on('/legal/policies/terms-of-service/', () => emptyResponse(404))
    fetcher.on('/auth/register/', () => jsonResponse(registerResponse, 201))

    renderPage(<RegisterPage />, { route: '/register' })

    await screen.findByText('First name')
    expect(screen.queryByRole('checkbox', { name: /terms of service/i })).not.toBeInTheDocument()
  })
})
