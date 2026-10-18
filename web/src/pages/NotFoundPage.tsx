import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="standalone-page">
      <main className="standalone-card glass">
        <span className="standalone-card__code">404</span>
        <h1>Page not found</h1>
        <p>The address you opened does not exist in STAR.</p>
        <Link className="btn btn--primary" to="/">
          Back to STAR
        </Link>
      </main>
    </div>
  )
}
