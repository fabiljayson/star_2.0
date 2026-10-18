import type { ReactNode } from 'react'

type CardProps = {
  title?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}

export function Card({ title, actions, children, className }: CardProps) {
  return (
    <section className={`card ${className ?? ''}`.trim()}>
      {(title || actions) && (
        <header className="card__header">
          {title && <h2 className="card__title">{title}</h2>}
          {actions && <div>{actions}</div>}
        </header>
      )}
      <div className="card__body">{children}</div>
    </section>
  )
}
