import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { Button } from '../components/Button'
import { TextField } from '../components/TextField'
import { ApiError } from '../lib/api'
import { AuthLayout } from './AuthLayout'

type FieldErrors = { email?: string; password?: string }

function validate(email: string, password: string): FieldErrors {
  const errors: FieldErrors = {}
  if (!email.trim()) {
    errors.email = 'Email is required.'
  } else if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
    errors.email = 'Enter a valid email address.'
  }
  if (!password) errors.password = 'Password is required.'
  return errors
}

export function LoginPage() {
  const { login, status } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (status === 'authenticated') navigate(from, { replace: true })
  }, [status, from, navigate])

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault()
    setFormError(null)
    const fieldErrors = validate(email, password)
    setErrors(fieldErrors)
    if (Object.keys(fieldErrors).length > 0) return

    setBusy(true)
    try {
      const outcome = await login(email.trim(), password)
      if (outcome === 'mfa') {
        navigate('/mfa', { replace: true })
      } else {
        navigate(from, { replace: true })
      }
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

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Access your surgical logbook, training and marketplace workspaces."
      footer={
        <>
          <span>
            New to STAR? <Link to="/register">Create an account</Link>
          </span>
          <Link to="/forgot-password">Forgot your password?</Link>
        </>
      }
    >
      <form className="form" onSubmit={(event) => void onSubmit(event)} noValidate>
        {formError && (
          <p className="form-alert" role="alert">
            {formError}
          </p>
        )}
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
        <TextField
          label="Password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={errors.password}
        />
        <Button type="submit" block loading={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
    </AuthLayout>
  )
}
