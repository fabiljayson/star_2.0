type SpinnerProps = {
  size?: 'sm' | 'md'
  label?: string
  className?: string
}

export function Spinner({ size = 'md', label, className }: SpinnerProps) {
  const spinner = (
    <span
      className={`spinner spinner--${size} ${className ?? ''}`.trim()}
      aria-hidden="true"
    />
  )
  if (!label) return spinner
  return (
    <span className="spinner-wrap" role="status">
      {spinner}
      <span>{label}</span>
    </span>
  )
}
