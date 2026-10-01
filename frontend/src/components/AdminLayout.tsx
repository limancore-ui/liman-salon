import { useState, type ChangeEvent, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { membershipLabel } from '../auth/workspace'

const NAV_ITEMS = [
  { label: 'Dashboard', to: '/admin' },
  { label: 'Bookings', to: '/admin/bookings' },
  { label: 'Customers', to: '/admin/customers' },
  { label: 'Staff', to: '/admin/staff' },
  { label: 'Services', to: '/admin/services' },
  { label: 'Schedule', to: '/admin/schedule' },
  { label: 'Media', to: '/admin/media' },
  { label: 'Settings', to: '/admin/settings' },
] as const

type AdminLayoutProps = {
  children: ReactNode
}

function canAccessSalonSettings(role: string | undefined): boolean {
  return role === 'owner' || role === 'admin'
}

export function AdminLayout({ children }: AdminLayoutProps) {
  const { session, logout, switchWorkspace } = useAuth()
  const [switchingSalon, setSwitchingSalon] = useState(false)
  const salon = session?.salon
  const user = session?.user
  const salons = session?.salons ?? []
  const showWorkspaceSwitcher = salons.length > 1

  async function handleWorkspaceChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextSalonId = event.target.value
    if (!nextSalonId || nextSalonId === salon?.salon_id) {
      return
    }
    setSwitchingSalon(true)
    try {
      await switchWorkspace(nextSalonId)
    } finally {
      setSwitchingSalon(false)
    }
  }
  const navItems = NAV_ITEMS.filter(
    (item) => item.to !== '/admin/settings' || canAccessSalonSettings(salon?.role),
  )

  return (
    <div className="admin-shell">
      <aside className="admin-shell__sidebar" aria-label="Admin navigation">
        <div className="admin-shell__brand">
          {showWorkspaceSwitcher ? (
            <label className="admin-shell__workspace-switch">
              <span className="visually-hidden">Active salon workspace</span>
              <select
                className="form-field__input admin-shell__workspace-select"
                value={salon?.salon_id ?? ''}
                disabled={switchingSalon}
                onChange={handleWorkspaceChange}
                aria-label="Switch salon workspace"
              >
                {salons.map((membership) => (
                  <option key={membership.salon_id} value={membership.salon_id}>
                    {membershipLabel(membership)}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <>
              <p className="admin-shell__salon-name">
                {salon?.salon_name ?? 'Salon'}
              </p>
              <p className="admin-shell__salon-slug">{salon?.salon_slug}</p>
            </>
          )}
        </div>
        <nav className="admin-nav">
          <ul className="admin-nav__list">
            {navItems.map((item) => (
              <li key={item.label} className="admin-nav__item">
                <NavLink
                  to={item.to}
                  end={item.to === '/admin'}
                  className={({ isActive }) =>
                    `admin-nav__link${isActive ? ' admin-nav__link--active' : ''}`
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <div className="admin-shell__main">
        <header className="admin-shell__header">
          <div className="admin-shell__user">
            <span className="admin-shell__email">{user?.email}</span>
            <span className="admin-shell__role">{salon?.role}</span>
          </div>
          <button
            type="button"
            className="btn btn--secondary btn--compact"
            onClick={logout}
          >
            Log out
          </button>
        </header>
        <div className="admin-shell__content">{children}</div>
      </div>
    </div>
  )
}
