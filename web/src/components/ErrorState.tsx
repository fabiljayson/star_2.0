import type { ReactNode } from 'react'

type ErrorStateProps = {
  title?: string
  message: string
  onRetry?: () => void
  retryLabel?: string
  action?: ReactNode
}

export function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
  retryLabel = 'Try again',
  action,
}: ErrorStateProps) {
  return (
    <div className="state-block state-block--error" role="alert">
      <h3 className="state-block__title">{title}</h3>
      <p className="state-block__message">{message}</p>
      {onRetry && (
        <button type="button" className="btn btn--secondary btn--sm" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
      {action}
    </div>
  )
}
