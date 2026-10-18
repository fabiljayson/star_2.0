import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { LandingPage } from './LandingPage'

function renderLanding() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>,
  )
}

describe('LandingPage', () => {
  it('renders the hero headline and the brand logo', () => {
    renderLanding()

    expect(
      screen.getByRole('heading', { level: 1, name: /track every procedure/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByAltText(/secure surgical tracking/i),
    ).toHaveAttribute('src', '/logo.png')
  })

  it('offers sign-in and registration entry points', () => {
    renderLanding()

    const links = screen.getAllByRole('link', { name: /Sign in|Create account/i })
    const targets = links.map((link) => link.getAttribute('href'))
    expect(targets).toContain('/login')
    expect(targets).toContain('/register')
  })

  it('presents the four platform modules', () => {
    renderLanding()

    for (const title of [
      'Surgical logbook',
      'Training & assessment',
      'Reports & exports',
      'Equipment marketplace',
    ]) {
      expect(screen.getByRole('heading', { name: title })).toBeInTheDocument()
    }
  })
})
