import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type ReactNode,
} from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { membershipLabel } from '../auth/workspace'
import { t, type MessageKey } from '../i18n'
import { AdminNotificationBell } from './AdminNotificationBell'

const NAV_ITEMS: ReadonlyArray<{
  labelKey: MessageKey
  to: string
  ownerAdminOnly?: boolean
  icon?: 'palette'
}> = [
  { labelKey: 'admin.nav.dashboard', to: '/admin' },
  { labelKey: 'admin.nav.bookings', to: '/admin/bookings' },
  { labelKey: 'admin.nav.customers', to: '/admin/customers' },
  { labelKey: 'admin.nav.reviews', to: '/admin/reviews' },
  { labelKey: 'admin.nav.showcase', to: '/admin/showcase' },
  { labelKey: 'admin.nav.staff', to: '/admin/staff' },
  { labelKey: 'admin.nav.services', to: '/admin/services' },
  { labelKey: 'admin.nav.schedule', to: '/admin/schedule' },
  { labelKey: 'admin.nav.media', to: '/admin/media' },
  {
    labelKey: 'admin.nav.appearance',
    to: '/admin/appearance',
    ownerAdminOnly: true,
    icon: 'palette',
  },
  {
    labelKey: 'admin.nav.settings',
    to: '/admin/settings',
    ownerAdminOnly: true,
  },
]

const MOBILE_NAV_MEDIA_QUERY = '(max-width: 47.99rem)'

function readNarrowViewport(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  return window.matchMedia(MOBILE_NAV_MEDIA_QUERY).matches
}

type AdminLayoutProps = {
  children: ReactNode
}

function canAccessOwnerAdminNav(role: string | undefined): boolean {
  return role === 'owner' || role === 'admin'
}

function NavPaletteIcon() {
  return (
    <svg
      className="admin-nav__icon"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <path
        fill="currentColor"
        d="M12 3c-4.97 0-9 3.58-9 8 0 3.31 2.4 6.1 5.7 7.3.4.14.8-.16.8-.56v-1.84c0-.28-.14-.53-.38-.67C6.8 14.5 5.5 12.9 5.5 11c0-3.31 2.91-6 6.5-6s6.5 2.69 6.5 6c0 1.66-1 3.05-2.5 3.8-.3.15-.5.45-.5.78V18c0 .55.45 1 1 1h.5c3.58 0 6.5-3.13 6.5-7 0-4.42-4.03-8-9-8zm-5.5 9.5a1.25 1.25 0 1 1 0-2.5 1.25 1.25 0 0 1 0 2.5zm2.25-3.25a1.25 1.25 0 1 1 0-2.5 1.25 1.25 0 0 1 0 2.5zM12 7.75a1.25 1.25 0 1 1 0-2.5 1.25 1.25 0 0 1 0 2.5zm3.25 1.5a1.25 1.25 0 1 1 0-2.5 1.25 1.25 0 0 1 0 2.5z"
      />
    </svg>
  )
}

export function AdminLayout({ children }: AdminLayoutProps) {
  const { session, logout, switchWorkspace } = useAuth()
  const [switchingSalon, setSwitchingSalon] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [isNarrowViewport, setIsNarrowViewport] = useState(readNarrowViewport)
  const [profileMenuOpen, setProfileMenuOpen] = useState(false)
  const profileMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') {
      return
    }
    const mediaQuery = window.matchMedia(MOBILE_NAV_MEDIA_QUERY)
    const syncNarrowViewport = () => {
      setIsNarrowViewport(mediaQuery.matches)
    }
    mediaQuery.addEventListener('change', syncNarrowViewport)
    return () => {
      mediaQuery.removeEventListener('change', syncNarrowViewport)
    }
  }, [])

  useEffect(() => {
    if (!isNarrowViewport && mobileNavOpen) {
      setMobileNavOpen(false)
    }
  }, [isNarrowViewport, mobileNavOpen])

  useEffect(() => {
    if (!mobileNavOpen) {
      return
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== 'Escape') {
        return
      }
      setMobileNavOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [mobileNavOpen])

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
    (item) => !item.ownerAdminOnly || canAccessOwnerAdminNav(salon?.role),
  )

  useEffect(() => {
    if (!profileMenuOpen) {
      return
    }
    function onDocClick(event: MouseEvent) {
      if (!profileMenuRef.current?.contains(event.target as Node)) {
        setProfileMenuOpen(false)
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== 'Escape') {
        return
      }
      setProfileMenuOpen(false)
      profileMenuRef.current
        ?.querySelector<HTMLButtonElement>('.admin-profile__trigger')
        ?.focus()
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [profileMenuOpen])

  function closeMobileNav() {
    setMobileNavOpen(false)
  }

  function toggleMobileNav() {
    setMobileNavOpen((open) => !open)
    if (!mobileNavOpen) {
      setProfileMenuOpen(false)
    }
  }

  const shellClassName = mobileNavOpen
    ? 'admin-shell admin-shell--nav-open'
    : 'admin-shell'
  const sidebarInert = isNarrowViewport && !mobileNavOpen

  return (
    <div className={shellClassName}>
      <button
        type="button"
        className="admin-shell__nav-backdrop"
        aria-label={t('admin.layout.closeNav')}
        tabIndex={mobileNavOpen ? 0 : -1}
        onClick={closeMobileNav}
      />
      <aside
        id="admin-shell-sidebar"
        className="admin-shell__sidebar"
        aria-label={t('admin.layout.navAria')}
        inert={sidebarInert ? true : undefined}
      >
        <div className="admin-shell__brand">
          {showWorkspaceSwitcher ? (
            <label className="admin-shell__workspace-switch">
              <span className="visually-hidden">
                {t('admin.layout.activeWorkspace')}
              </span>
              <select
                className="form-field__input admin-shell__workspace-select"
                value={salon?.salon_id ?? ''}
                disabled={switchingSalon}
                onChange={handleWorkspaceChange}
                aria-label={t('admin.layout.switchWorkspace')}
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
                {salon?.salon_name ?? t('admin.layout.salonFallback')}
              </p>
              <p className="admin-shell__salon-slug">{salon?.salon_slug}</p>
            </>
          )}
        </div>
        <nav className="admin-nav">
          <ul className="admin-nav__list">
            {navItems.map((item) => (
              <li key={item.to} className="admin-nav__item">
                <NavLink
                  to={item.to}
                  end={item.to === '/admin'}
                  className={({ isActive }) =>
                    `admin-nav__link${isActive ? ' admin-nav__link--active' : ''}`
                  }
                  onClick={closeMobileNav}
                >
                  {item.icon === 'palette' ? <NavPaletteIcon /> : null}
                  <span>{t(item.labelKey)}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <div className="admin-shell__main">
        <header className="admin-shell__header">
          <div className="admin-shell__header-leading">
            <button
              type="button"
              className="admin-shell__menu-toggle btn btn--secondary btn--compact"
              aria-expanded={mobileNavOpen}
              aria-controls="admin-shell-sidebar"
              onClick={toggleMobileNav}
            >
              {mobileNavOpen
                ? t('admin.layout.closeMenu')
                : t('admin.layout.openMenu')}
            </button>
            <div className="admin-profile" ref={profileMenuRef}>
              <button
                type="button"
                className="admin-profile__trigger"
                aria-haspopup="menu"
                aria-expanded={profileMenuOpen}
                aria-controls="admin-profile-menu"
                onClick={() => setProfileMenuOpen((open) => !open)}
              >
                <span className="admin-shell__email">{user?.email}</span>
                <span className="admin-shell__role">{salon?.role}</span>
              </button>
              {profileMenuOpen ? (
                <div
                  id="admin-profile-menu"
                  className="admin-profile__menu"
                  role="menu"
                  aria-label={t('admin.layout.profileMenu')}
                >
                  <button
                    type="button"
                    role="menuitem"
                    className="admin-profile__item"
                    onClick={logout}
                  >
                    {t('common.logOut')}
                  </button>
                </div>
              ) : null}
            </div>
          </div>
          <div className="admin-shell__header-trailing">
            <AdminNotificationBell mobileNavOpen={mobileNavOpen} />
          </div>
        </header>
        <div className="admin-shell__content">{children}</div>
      </div>
    </div>
  )
}
