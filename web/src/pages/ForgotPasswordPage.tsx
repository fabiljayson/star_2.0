import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '../components/Button'
import { TextField } from '../components/TextField'
import { ApiError, apiFetch } from '../lib/api'
import type { MessageResponse } from '../lib/types'
import { AuthLayout } from './AuthLayout'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault()
    setError(null)
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setError('Enter a valid email address.')
      return
    }
    setBusy(true)
    try {
      await apiFetch<MessageResponse>('/auth/password/forgot/', {
        method: 'POST',
        auth: false,
        body: { email: email.trim() },
      })
      setSent(true)
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Could not reach the server.'
      )
    } finally {
      setBusy(false)
    }
  }

  if (sent) {
    return (
      <AuthLayout
        title="Check your inbox"
        subtitle={`If an account exists for ${email.trim()}, we sent a password reset link. In development, the server console prints the token.`}
        footer={
          <>
            <Link to="/reset-password">Have a reset token?</Link>
            <Link to="/login">Back to sign in</Link>
          </>
        }
      />
    )
  }

  return (
    <AuthLayout
      title="Reset your password"
      subtitle="Enter your account email and we will send you a reset link."
      footer={
        <span>
          Remembered it? <Link to="/login">Back to sign in</Link>
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
          label="Email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Button type="submit" block loading={busy}>
          {busy ? 'Sending…' : 'Send reset link'}
        </Button>
      </form>
    </AuthLayout>
  )
}
