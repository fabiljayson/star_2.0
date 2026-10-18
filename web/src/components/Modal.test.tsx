import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Modal } from './Modal'

function renderModal(onClose = vi.fn()) {
  render(
    <Modal open onClose={onClose} title="Cancel this order?">
      <p>The reserved stock will be released immediately.</p>
    </Modal>,
  )
  return onClose
}

describe('Modal', () => {
  it('exposes an accessible dialog labelled by its title', () => {
    renderModal()

    const dialog = screen.getByRole('dialog', { name: 'Cancel this order?' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(
      screen.getByText('The reserved stock will be released immediately.'),
    ).toBeInTheDocument()
  })

  it('closes on Escape', async () => {
    const user = userEvent.setup()
    const onClose = renderModal()

    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes from the close button', async () => {
    const user = userEvent.setup()
    const onClose = renderModal()

    await user.click(screen.getByRole('button', { name: 'Close dialog' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes when the backdrop is clicked', async () => {
    const user = userEvent.setup()
    const onClose = renderModal()
    const backdrop = document.querySelector('.modal-backdrop')

    if (backdrop) {
      await user.click(backdrop)
    }

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders nothing while closed', () => {
    render(
      <Modal open={false} onClose={vi.fn()} title="Hidden">
        <p>Body</p>
      </Modal>,
    )

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
