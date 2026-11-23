import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { jsonResponse, stubFetch } from '../test/helpers'
import { MfaEnrollmentCard } from './MfaEnrollmentCard'

describe('MfaEnrollmentCard', () => {
  it('shows the setup key and enables MFA after a code is confirmed', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    fetcher.on('/auth/mfa/setup/', () =>
      jsonResponse({
        secret: 'JBSWY3DPEHPK3PXP',
        otpauth_url: 'otpauth://totp/STAR?secret=JBSWY3DPEHPK3PXP',
      }),
    )
    fetcher.on('/auth/mfa/enable/', () =>
      jsonResponse({ message: 'Multi-factor authentication enabled.' }),
    )
    const onChanged = vi.fn().mockResolvedValue(undefined)

    render(
      <MfaEnrollmentCard enabled={false} required onChanged={onChanged} />,
    )

    expect(
      screen.getByText(/required for platform administrator actions/i),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Set up two-factor' }))

    expect(await screen.findByText('JBSWY3DPEHPK3PXP')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Six-digit code'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verify and enable' }))

    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1))
    expect(
      screen.getByText('Two-factor authentication is now on.'),
    ).toBeInTheDocument()

    const enableCall = fetcher.calls.find((call) =>
      call.url.includes('/auth/mfa/enable/'),
    )
    expect(JSON.parse(String(enableCall?.init?.body))).toEqual({
      code: '123456',
    })
  })

  it('disables MFA only after confirming a code', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    fetcher.on('/auth/mfa/disable/', () =>
      jsonResponse({ message: 'Multi-factor authentication disabled.' }),
    )
    const onChanged = vi.fn().mockResolvedValue(undefined)

    render(<MfaEnrollmentCard enabled onChanged={onChanged} />)

    await user.click(screen.getByRole('button', { name: 'Disable two-factor' }))
    await user.type(screen.getByLabelText('Six-digit code'), '654321')
    await user.click(screen.getByRole('button', { name: 'Confirm disable' }))

    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1))
    expect(
      screen.getByText('Two-factor authentication is off.'),
    ).toBeInTheDocument()
  })

  it('surfaces a setup failure without leaving the card stuck', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    fetcher.on('/auth/mfa/setup/', () =>
      jsonResponse(
        { error: { code: 'validation_error', message: 'Already enabled.' } },
        400,
      ),
    )

    render(<MfaEnrollmentCard enabled={false} onChanged={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Set up two-factor' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Already enabled.',
    )
    expect(
      screen.getByRole('button', { name: 'Set up two-factor' }),
    ).toBeEnabled()
  })
})
