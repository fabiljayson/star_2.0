import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { Button } from '../components/Button'
import { initialsOf, roleLabel } from '../lib/roles'
import { NAV_ITEMS, filterNavItems } from './nav'

export function AppShell() {
  const { user, logout, hasAnyRole } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    if (!menuOpen) return
    function onKeyDown(event: KeyboardEvent): void {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [menuOpen])

  if (!user) return null

  const items = filterNavItems(NAV_ITEMS, hasAnyRole)
  const primaryRole = user.roles.find((assignment) => assignment.is_active)
  const roleDescription = primaryRole ? roleLabel(primaryRole.role) : 'Signed in'

  async function onLogout(): Promise<void> {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="app-shell">
      <header className="app-topbar glass">
        <button
          type="button"
          className="nav-toggle"
          aria-expanded={menuOpen}
          aria-controls="app-sidebar"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          onClick={() => setMenuOpen((open) => !open)}
        >
          ☰
        </button>
        <span className="brand">
          <img className="brand__mark" src="/app-icon.png" alt="" width={36} height={36} />
          <span className="brand__text">STAR</span>
        </span>
        <span className="app-topbar__spacer" />
        <div className="app-topbar__user">
          <span className="user-chip">
            <span className="user-chip__avatar" aria-hidden="true">
              {initialsOf(user.full_name)}
            </span>
            <span className="user-chip__meta">
              <span className="user-chip__name">{user.full_name}</span>
              <span className="user-chip__role">{roleDescription}</span>
            </span>
          </span>
          <Button variant="ghost" size="sm" onClick={() => void onLogout()}>
            Sign out
          </Button>
        </div>
      </header>

      <div className="app-body">
        {menuOpen && (
          <button
            type="button"
            className="drawer-backdrop"
            aria-label="Close menu"
            onClick={() => setMenuOpen(false)}
          />
        )}
        <nav
          id="app-sidebar"
          className={`app-sidebar glass ${menuOpen ? 'is-open' : ''}`.trim()}
          aria-label="Main navigation"
        >
          <ul className="app-nav">
            {items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className="app-nav__link"
                  onClick={() => setMenuOpen(false)}
                >
                  <span className="app-nav__icon" aria-hidden="true">
                    {item.icon}
                  </span>
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main className="app-main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
