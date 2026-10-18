import type { ReactNode } from 'react'

type AuthLayoutProps = {
  title: string
  subtitle?: string
  children?: ReactNode
  footer?: ReactNode
  wide?: boolean
}

export function AuthLayout({ title, subtitle, children, footer, wide }: AuthLayoutProps) {
  return (
    <div className="auth-page">
      <main className={`auth-card glass ${wide ? 'auth-card--wide' : ''}`.trim()}>
        <div className="auth-card__brand">
          <span className="brand">
            <img className="brand__mark" src="/app-icon.png" alt="" width={36} height={36} />
            <span className="brand__text">STAR</span>
          </span>
          <span className="auth-card__tagline">
            Surgical logbook, training &amp; equipment marketplace
          </span>
        </div>
        <h1 className="auth-card__title">{title}</h1>
        {subtitle && <p className="auth-card__subtitle">{subtitle}</p>}
        {children}
        {footer && <div className="auth-card__footer">{footer}</div>}
      </main>
    </div>
  )
}
