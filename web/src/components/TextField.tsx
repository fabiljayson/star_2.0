import { useId, type InputHTMLAttributes } from 'react'

type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  label: string
  error?: string | null
  hint?: string
}

export function TextField({
  label,
  error,
  hint,
  className,
  ...inputProps
}: TextFieldProps) {
  const reactId = useId()
  const id = inputProps.name ? `field-${inputProps.name}` : reactId
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  const describedBy = [error ? errorId : null, hint ? hintId : null]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={`field ${className ?? ''}`.trim()}>
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className="field__control"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        {...inputProps}
      />
      {hint && !error && (
        <p className="field__hint" id={hintId}>
          {hint}
        </p>
      )}
      {error && (
        <p className="field__error" id={errorId} role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
