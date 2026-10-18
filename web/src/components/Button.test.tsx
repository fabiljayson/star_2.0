import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Button } from './Button'

describe('Button', () => {
  it('fires the click handler once', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()

    render(<Button onClick={onClick}>Save intervention</Button>)
    await user.click(screen.getByRole('button', { name: 'Save intervention' }))

    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('ignores clicks while disabled', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()

    render(
      <Button disabled onClick={onClick}>
        Save
      </Button>,
    )
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(onClick).not.toHaveBeenCalled()
  })

  it('marks itself busy and blocks clicks while loading', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()

    render(
      <Button loading onClick={onClick}>
        Signing in
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Signing in' })

    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button).toBeDisabled()
    await user.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('renders the requested variant class', () => {
    render(<Button variant="danger">Delete</Button>)
    expect(screen.getByRole('button', { name: 'Delete' })).toHaveClass('btn--danger')
  })
})
