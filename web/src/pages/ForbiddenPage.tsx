import { Link } from 'react-router-dom'

export function ForbiddenPage() {
  return (
    <div className="standalone-page">
      <main className="standalone-card glass">
        <span className="standalone-card__code">403</span>
        <h1>You don&apos;t have access to this page</h1>
        <p>
          Your account does not hold the role this workspace requires. Ask an
          administrator for access, or return to your account.
        </p>
        <Link className="btn btn--primary" to="/">
          Back to STAR
        </Link>
      </main>
    </div>
  )
}
