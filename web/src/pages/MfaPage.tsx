import { useEffect, useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { Button } from '../components/Button'
import { TextField } from '../components/TextField'
import { ApiError } from '../lib/api'
import { AuthLayout } from './AuthLayout'

export function MfaPage() {
  const { verifyMfa, cancelMfa, pendingMfaToken, status } = useAuth()
  const navigate = useNavigate()
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (status === 'authenticated') navigate('/', { replace: true })
  }, [status, navigate])

  if (status !== 'loading' && !pendingMfaToken) {
    return <Navigate to="/login" replace />
  }

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault()
    setError(null)
    if (!code.trim()) {
      setError('Enter the 6-digit code from your authenticator app.')
      return
    }
    setBusy(true)
    try {
      await verifyMfa(code.trim())
      navigate('/', { replace: true })
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Verification failed. Please try again.',
      )
    } finally {
      setBusy(false)
    }
  }

  function onCancel(): void {
    cancelMfa()
    navigate('/login', { replace: true })
  }

  return (
    <AuthLayout
      title="Two-factor code"
      subtitle="Enter the current code from your authenticator app to finish signing in."
      footer={
        <Button variant="ghost" size="sm" onClick={onCancel}>
          Back to sign in
        </Button>
      }
    >
      <form className="form" onSubmit={(event) => void onSubmit(event)} noValidate>
        {error && (
          <p className="form-alert" role="alert">
            {error}
          </p>
        )}
        <TextField
          label="Authentication code"
          name="code"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={8}
          placeholder="123456"
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
        <Button type="submit" block loading={busy}>
          {busy ? 'Verifying…' : 'Verify code'}
        </Button>
      </form>
    </AuthLayout>
  )
}
