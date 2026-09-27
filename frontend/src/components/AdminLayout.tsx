import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const NAV_ITEMS = [
  { label: 'Dashboard', to: '/admin' },
  { label: 'Bookings', to: '/admin/bookings' },
  { label: 'Customers', to: '/admin/customers' },
  { label: 'Staff', to: '/admin/staff' },
  { label: 'Services', to: '/admin/services' },
  { label: 'Schedule', to: '/admin/schedule' },
] as const

type AdminLayoutProps = {
  children: ReactNode
}

export function AdminLayout({ children }: AdminLayoutProps) {
  const { session, logout } = useAuth()
  const salon = session?.salon
  const user = session?.user

  return (
    <div className="admin-shell">
      <aside className="admin-shell__sidebar" aria-label="Admin navigation">
        <div className="admin-shell__brand">
          <p className="admin-shell__salon-name">{salon?.salon_name ?? 'Salon'}</p>
          <p className="admin-shell__salon-slug">{salon?.salon_slug}</p>
        </div>
        <nav className="admin-nav">
          <ul className="admin-nav__list">
            {NAV_ITEMS.map((item) => (
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
