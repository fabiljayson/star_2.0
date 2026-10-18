import { Link } from 'react-router-dom'

type NotFoundPageProps = {
  title?: string
  message?: string
}

export function NotFoundPage({ title, message }: NotFoundPageProps) {
  return (
    <div className="standalone-page">
      <main className="standalone-card glass">
        <span className="standalone-card__code">404</span>
        <h1>{title ?? 'Page not found'}</h1>
        <p>{message ?? 'The address you opened does not exist in STAR.'}</p>
        <Link className="btn btn--primary" to="/">
          Back to STAR
        </Link>
      </main>
    </div>
  )
}
