import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../components/Button'
import { TextField } from '../components/TextField'
import { ApiError, apiFetch } from '../lib/api'
import type { RegisterResponse } from '../lib/types'
import { AuthLayout } from './AuthLayout'

const OPEN_ROLES = [
  { value: 'independent_surgeon', label: 'Independent surgeon' },
  { value: 'buyer', label: 'Equipment buyer' },
  { value: 'supplier', label: 'Equipment supplier' },
]

type FieldErrors = {
  first_name?: string
  email?: string
  password?: string
  confirm?: string
}

export function RegisterPage() {
  const navigate = useNavigate()
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [role, setRole] = useState('independent_surgeon')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<RegisterResponse | null>(null)

  function validate(): FieldErrors {
    const next: FieldErrors = {}
    if (email.trim() && !/^\S+@\S+\.\S+$/.test(email.trim())) {
      next.email = 'Enter a valid email address.'
    } else if (!email.trim()) {
      next.email = 'Email is required.'
    }
    if (!password) {
      next.password = 'Password is required.'
    } else if (password.length < 8) {
      next.password = 'Use at least 8 characters.'
    }
    if (confirm !== password) next.confirm = 'Passwords do not match.'
    return next
  }

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault()
    setFormError(null)
    const fieldErrors = validate()
    setErrors(fieldErrors)
    if (Object.keys(fieldErrors).length > 0) return

    setBusy(true)
    try {
      const data = await apiFetch<RegisterResponse>('/auth/register/', {
        method: 'POST',
        auth: false,
        body: {
          email: email.trim(),
          password,
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          role,
        },
      })
      setDone(data)
    } catch (error) {
      setFormError(
        error instanceof ApiError
          ? error.message
          : 'Could not reach the server. Please try again.',
      )
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    const verificationHref = done.verification_token
      ? `/verify-email?token=${encodeURIComponent(done.verification_token)}`
      : null
    return (
      <AuthLayout
        title="Account created"
        subtitle={done.message}
        footer={
          <>
            {verificationHref && (
              <Link to={verificationHref}>Continue to email verification</Link>
            )}
            <Link to="/login">Back to sign in</Link>
          </>
        }
      >
        <Button block onClick={() => navigate('/login')}>
          Go to sign in
        </Button>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Open registration is available to surgeons, buyers and suppliers."
      wide
      footer={
        <span>
          Already registered? <Link to="/login">Sign in</Link>
        </span>
      }
    >
      <form className="form" onSubmit={(event) => void onSubmit(event)} noValidate>
        {formError && (
          <p className="form-alert" role="alert">
            {formError}
          </p>
        )}
        <div className="form-grid">
          <TextField
            label="First name"
            name="first_name"
            autoComplete="given-name"
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
            error={errors.first_name}
          />
          <TextField
            label="Last name"
            name="last_name"
            autoComplete="family-name"
            value={lastName}
            onChange={(event) => setLastName(event.target.value)}
          />
        </div>
        <div className="field">
          <label className="field__label" htmlFor="register-role">
            I am registering as
          </label>
          <select
            id="register-role"
            className="field__control"
            value={role}
            onChange={(event) => setRole(event.target.value)}
          >
            {OPEN_ROLES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <TextField
          label="Email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.test"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={errors.email}
        />
        <div className="form-grid">
          <TextField
            label="Password"
            name="password"
            type="password"
            autoComplete="new-password"
            hint="At least 8 characters."
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={errors.password}
          />
          <TextField
            label="Confirm password"
            name="confirm"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            error={errors.confirm}
          />
        </div>
        <Button type="submit" block loading={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </Button>
      </form>
    </AuthLayout>
  )
}
