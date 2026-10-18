import type { ReactNode } from 'react'

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info'

type BadgeProps = {
  tone?: BadgeTone
  children: ReactNode
  title?: string
}

export function Badge({ tone = 'neutral', children, title }: BadgeProps) {
  return (
    <span className={`badge badge--${tone}`} title={title}>
      {children}
    </span>
  )
}
