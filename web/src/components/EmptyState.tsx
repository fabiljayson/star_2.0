import type { ReactNode } from 'react'

type EmptyStateProps = {
  title: string
  message?: string
  action?: ReactNode
}

export function EmptyState({ title, message, action }: EmptyStateProps) {
  return (
    <div className="state-block">
      <h3 className="state-block__title">{title}</h3>
      {message && <p className="state-block__message">{message}</p>}
      {action}
    </div>
  )
}
