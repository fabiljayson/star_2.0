import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Button } from '../components/Button'
import { TextField } from '../components/TextField'
import { ApiError, apiFetch } from '../lib/api'
import type { MessageResponse } from '../lib/types'
import { AuthLayout } from './AuthLayout'

type FieldErrors = { token?: string; password?: string; confirm?: string }

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const [token, setToken] = useState(searchParams.get('token') ?? '')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault()
    setFormError(null)
    const next: FieldErrors = {}
    if (!token.trim()) next.token = 'The reset token is required.'
    if (password.length < 8) next.password = 'Use at least 8 characters.'
    if (confirm !== password) next.confirm = 'Passwords do not match.'
    setErrors(next)
    if (Object.keys(next).length > 0) return

    setBusy(true)
    try {
      await apiFetch<MessageResponse>('/auth/password/reset/', {
        method: 'POST',
        auth: false,
        body: { token: token.trim(), password },
      })
      setDone(true)
    } catch (error) {
      setFormError(
        error instanceof ApiError ? error.message : 'Could not reach the server.'
      )
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <AuthLayout
        title="Password updated"
        subtitle="Your password has been changed. Sign in with the new one."
        footer={<Link to="/login">Go to sign in</Link>}
      />
    )
  }

  return (
    <AuthLayout
      title="Choose a new password"
      subtitle="Paste your reset token and pick a new password."
      footer={
        <span>
          <Link to="/forgot-password">Need a new token?</Link>
        </span>
      }
    >
      <form className="form" onSubmit={(event) => void onSubmit(event)} noValidate>
        {formError && (
          <p className="form-alert" role="alert">
            {formError}
          </p>
        )}
        <TextField
          label="Reset token"
          name="token"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          error={errors.token}
        />
        <TextField
          label="New password"
          name="password"
          type="password"
          autoComplete="new-password"
          hint="At least 8 characters."
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={errors.password}
        />
        <TextField
          label="Confirm new password"
          name="confirm"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          error={errors.confirm}
        />
        <Button type="submit" block loading={busy}>
          {busy ? 'Updating…' : 'Update password'}
        </Button>
      </form>
    </AuthLayout>
  )
}
