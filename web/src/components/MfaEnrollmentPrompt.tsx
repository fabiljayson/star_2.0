import { Link } from 'react-router-dom'
import { useAuth } from '../auth/context'

export function MfaEnrollmentPrompt() {
  const { user } = useAuth()
  if (!user?.is_platform_admin || user.mfa_enabled) return null

  return (
    <section
      className="mfa-prompt"
      aria-labelledby="mfa-prompt-title"
      role="region"
    >
      <div>
        <h2 className="mfa-prompt__title" id="mfa-prompt-title">
          Two-factor authentication required
        </h2>
        <p className="mfa-prompt__text">
          Platform administrator actions need an authenticator code. Enrol before
          verifying suppliers, moderating products, resolving disputes or
          publishing policies.
        </p>
      </div>
      <Link to="/account#two-factor" className="btn btn--secondary btn--sm">
        Set up two-factor
      </Link>
    </section>
  )
}
