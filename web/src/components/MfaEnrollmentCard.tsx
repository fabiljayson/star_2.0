import { useState, type FormEvent } from 'react'
import { apiFetch } from '../lib/api'
import type { MessageResponse } from '../lib/types'
import { Button } from './Button'
import { Card } from './Card'
import { TextField } from './TextField'

type SetupResponse = { secret: string; otpauth_url: string }

type MfaEnrollmentCardProps = {
  enabled: boolean
  required?: boolean
  onChanged: () => Promise<void> | void
}

function messageFor(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

export function MfaEnrollmentCard({
  enabled,
  required = false,
  onChanged,
}: MfaEnrollmentCardProps) {
  const [mode, setMode] = useState<'idle' | 'setup' | 'disable'>('idle')
  const [secret, setSecret] = useState<string | null>(null)
  const [otpauthUrl, setOtpauthUrl] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  function reset(): void {
    setMode('idle')
    setSecret(null)
    setOtpauthUrl(null)
    setCode('')
    setError(null)
  }

  async function startSetup(): Promise<void> {
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      const data = await apiFetch<SetupResponse>('/auth/mfa/setup/', {
        method: 'POST',
      })
      setSecret(data.secret)
      setOtpauthUrl(data.otpauth_url)
      setMode('setup')
    } catch (caught) {
      setError(messageFor(caught, 'Could not start two-factor setup.'))
    } finally {
      setBusy(false)
    }
  }

  async function confirmEnable(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      await apiFetch<MessageResponse>('/auth/mfa/enable/', {
        method: 'POST',
        body: { code: code.trim() },
      })
      await onChanged()
      setMessage('Two-factor authentication is now on.')
      reset()
    } catch (caught) {
      setError(messageFor(caught, 'Could not enable two-factor authentication.'))
    } finally {
      setBusy(false)
    }
  }

  async function confirmDisable(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      await apiFetch<MessageResponse>('/auth/mfa/disable/', {
        method: 'POST',
        body: { code: code.trim() },
      })
      await onChanged()
      setMessage('Two-factor authentication is off.')
      reset()
    } catch (caught) {
      setError(messageFor(caught, 'Could not disable two-factor authentication.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Two-factor authentication">
      {message && (
        <p className="form-alert form-alert--success" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="form-alert" role="alert">
          {error}
        </p>
      )}

      {enabled ? (
        mode === 'disable' ? (
          <form className="mfa-setup" onSubmit={(event) => void confirmDisable(event)}>
            <p className="field__hint">
              Enter a current code from your authenticator app to turn two-factor
              authentication off.
            </p>
            <TextField
              label="Six-digit code"
              name="mfa-disable-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={8}
              value={code}
              onChange={(event) => setCode(event.target.value)}
              required
              autoFocus
            />
            <div className="mfa-actions">
              <Button
                type="submit"
                variant="danger"
                loading={busy}
                disabled={!code.trim()}
              >
                Confirm disable
              </Button>
              <Button variant="ghost" onClick={reset} disabled={busy}>
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          <>
            <p className="field__hint">
              Your account asks for an authenticator code when you sign in and
              before platform administration actions.
            </p>
            <Button
              variant="secondary"
              onClick={() => {
                setMode('disable')
                setCode('')
                setError(null)
                setMessage(null)
              }}
            >
              Disable two-factor
            </Button>
          </>
        )
      ) : mode === 'setup' && secret ? (
        <form className="mfa-setup" onSubmit={(event) => void confirmEnable(event)}>
          <p className="field__hint">
            Add this key to your authenticator app, then confirm the current
            code it shows.
          </p>
          <code className="mfa-secret" aria-label="Two-factor setup key">
            {secret}
          </code>
          {otpauthUrl && (
            <p className="field__hint">
              <a href={otpauthUrl}>Open in an authenticator app</a>
            </p>
          )}
          <TextField
            label="Six-digit code"
            name="mfa-enable-code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={8}
            value={code}
            onChange={(event) => setCode(event.target.value)}
            required
            autoFocus
          />
          <div className="mfa-actions">
            <Button type="submit" loading={busy} disabled={!code.trim()}>
              Verify and enable
            </Button>
            <Button variant="ghost" onClick={reset} disabled={busy}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <>
          <p className="field__hint">
            Use an authenticator app to protect sign-in and sensitive actions.
            {required
              ? ' Two-factor authentication is required for platform administrator actions.'
              : ''}
          </p>
          <Button loading={busy} onClick={() => void startSetup()}>
            Set up two-factor
          </Button>
        </>
      )}
    </Card>
  )
}
