import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Button } from '../components/Button'
import { TextField } from '../components/TextField'
import { ApiError, apiFetch } from '../lib/api'
import type { MessageResponse } from '../lib/types'
import { AuthLayout } from './AuthLayout'

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const [token, setToken] = useState(searchParams.get('token') ?? '')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault()
    setError(null)
    if (!token.trim()) {
      setError('The verification token is missing. Use the link from your email.')
      return
    }
    setBusy(true)
    try {
      await apiFetch<MessageResponse>('/auth/verify/', {
        method: 'POST',
        auth: false,
        body: { token: token.trim() },
      })
      setDone(true)
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Verification failed. Please try again.',
      )
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <AuthLayout
        title="Email verified"
        subtitle="Your email address is confirmed. You can sign in now."
        footer={<Link to="/login">Go to sign in</Link>}
      />
    )
  }

  return (
    <AuthLayout
      title="Verify your email"
      subtitle="Paste the token from your verification email to activate your account. In development, the server console prints the token."
      footer={
        <span>
          Wrong page? <Link to="/login">Back to sign in</Link>
        </span>
      }
    >
      <form className="form" onSubmit={(event) => void onSubmit(event)} noValidate>
        {error && (
          <p className="form-alert" role="alert">
            {error}
          </p>
        )}
        <TextField
          label="Verification token"
          name="token"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="paste-the-token-here"
          hint="Delivered by email; shown in the server console during development."
        />
        <Button type="submit" block loading={busy}>
          {busy ? 'Verifying…' : 'Verify email'}
        </Button>
      </form>
    </AuthLayout>
  )
}
