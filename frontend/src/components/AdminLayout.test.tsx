/**
 * @vitest-environment jsdom
 */
import { act, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { describe, expect, it, vi, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { renderToStaticMarkup } from 'react-dom/server'
import { AdminLayout } from './AdminLayout'
import { useAuth } from '../auth/AuthContext'

const reactActEnv = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean
}
reactActEnv.IS_REACT_ACT_ENVIRONMENT = true

vi.mock('../auth/AuthContext', () => ({
  useAuth: vi.fn(),
}))

vi.mock('./AdminNotificationBell', () => ({
  AdminNotificationBell: () => <div data-testid="admin-notification-bell" />,
}))

const mockedUseAuth = vi.mocked(useAuth)

const MOBILE_NAV_MEDIA_QUERY = '(max-width: 47.99rem)'

type MatchMediaListener = (event: MediaQueryListEvent) => void

function installMatchMedia(initialMatches: boolean) {
  let matches = initialMatches
  const listeners = new Set<MatchMediaListener>()

  window.matchMedia = vi.fn((query: string) => {
    expect(query).toBe(MOBILE_NAV_MEDIA_QUERY)
    return {
      media: query,
      get matches() {
        return matches
      },
      addEventListener: (_type: string, listener: MatchMediaListener) => {
        listeners.add(listener)
      },
      removeEventListener: (_type: string, listener: MatchMediaListener) => {
        listeners.delete(listener)
      },
      dispatchChange: (nextMatches: boolean) => {
        matches = nextMatches
        const event = {
          matches: nextMatches,
          media: query,
        } as MediaQueryListEvent
        listeners.forEach((listener) => listener(event))
      },
    } as MediaQueryList & { dispatchChange: (nextMatches: boolean) => void }
  }) as typeof window.matchMedia

  return {
    setMatches(nextMatches: boolean) {
      matches = nextMatches
      const event = {
        matches: nextMatches,
        media: MOBILE_NAV_MEDIA_QUERY,
      } as MediaQueryListEvent
      listeners.forEach((listener) => listener(event))
    },
  }
}

function mockSession(role: string) {
  mockedUseAuth.mockReturnValue({
    session: {
      token: 'tok',
      user: {
        user_id: 'u1',
        email: 'owner@example.com',
        full_name: 'Owner',
      },
      salon: {
        user_id: 'u1',
        salon_id: 'salon-1',
        role,
        email: 'owner@example.com',
        salon_name: 'Liman',
        salon_slug: 'liman',
      },
      salons: [
        {
          salon_id: 'salon-1',
          salon_name: 'Liman',
          salon_slug: 'liman',
          role,
        },
      ],
    },
    logout: vi.fn(),
    switchWorkspace: vi.fn(),
  } as unknown as ReturnType<typeof useAuth>)
}

function renderLayout(children: ReactNode = <p>Page content</p>) {
  return renderToStaticMarkup(
    <MemoryRouter>
      <AdminLayout>{children}</AdminLayout>
    </MemoryRouter>,
  )
}

describe('AdminLayout', () => {
  const originalMatchMedia = window.matchMedia

  afterEach(() => {
    vi.clearAllMocks()
    window.matchMedia = originalMatchMedia
  })

  it('renders mobile menu button closed by default with accessible name', () => {
    installMatchMedia(false)
    mockSession('staff')
    const html = renderLayout()
    expect(html).toContain('admin-shell__menu-toggle')
    expect(html).toContain('aria-expanded="false"')
    expect(html).toContain('aria-controls="admin-shell-sidebar"')
    expect(html).toContain('Open menu')
  })

  it('omits Settings nav for roles without salon settings access', () => {
    installMatchMedia(false)
    mockSession('staff')
    const html = renderLayout()
    expect(html).not.toContain('>Settings<')
    expect(html).toContain('>Bookings<')
  })

  it('includes Settings nav for owner role', () => {
    installMatchMedia(false)
    mockSession('owner')
    const html = renderLayout()
    expect(html).toContain('>Settings<')
  })

  it('toggles aria-expanded when menu button is clicked', async () => {
    installMatchMedia(true)
    mockSession('staff')
    const container = document.createElement('div')
    const root: Root = createRoot(container)

    await act(async () => {
      root.render(
        <MemoryRouter>
          <AdminLayout>
            <p>Page content</p>
          </AdminLayout>
        </MemoryRouter>,
      )
    })

    const toggle = container.querySelector(
      '.admin-shell__menu-toggle',
    ) as HTMLButtonElement
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    expect(toggle.textContent).toBe('Open menu')

    await act(async () => {
      toggle.click()
    })
    expect(toggle.getAttribute('aria-expanded')).toBe('true')
    expect(toggle.textContent).toBe('Close menu')
    expect(container.querySelector('.admin-shell--nav-open')).not.toBeNull()

    await act(async () => {
      root.unmount()
    })
  })

  it('closes mobile nav when a nav link is clicked', async () => {
    installMatchMedia(true)
    mockSession('staff')
    const container = document.createElement('div')
    const root: Root = createRoot(container)

    await act(async () => {
      root.render(
        <MemoryRouter>
          <AdminLayout>
            <p>Page content</p>
          </AdminLayout>
        </MemoryRouter>,
      )
    })

    const toggle = container.querySelector(
      '.admin-shell__menu-toggle',
    ) as HTMLButtonElement
    await act(async () => {
      toggle.click()
    })

    const bookingsLink = container.querySelector(
      'a.admin-nav__link[href="/admin/bookings"]',
    ) as HTMLAnchorElement
    await act(async () => {
      bookingsLink.click()
    })

    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    expect(container.querySelector('.admin-shell--nav-open')).toBeNull()

    await act(async () => {
      root.unmount()
    })
  })

  it('closes mobile nav when backdrop is clicked', async () => {
    installMatchMedia(true)
    mockSession('staff')
    const container = document.createElement('div')
    const root: Root = createRoot(container)

    await act(async () => {
      root.render(
        <MemoryRouter>
          <AdminLayout>
            <p>Page content</p>
          </AdminLayout>
        </MemoryRouter>,
      )
    })

    const toggle = container.querySelector(
      '.admin-shell__menu-toggle',
    ) as HTMLButtonElement
    await act(async () => {
      toggle.click()
    })
    expect(toggle.getAttribute('aria-expanded')).toBe('true')

    const backdrop = container.querySelector(
      '.admin-shell__nav-backdrop',
    ) as HTMLButtonElement
    await act(async () => {
      backdrop.click()
    })

    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    expect(container.querySelector('.admin-shell--nav-open')).toBeNull()

    await act(async () => {
      root.unmount()
    })
  })

  it('marks sidebar inert on narrow viewport when mobile nav is closed', async () => {
    installMatchMedia(true)
    mockSession('staff')
    const container = document.createElement('div')
    const root: Root = createRoot(container)

    await act(async () => {
      root.render(
        <MemoryRouter>
          <AdminLayout>
            <p>Page content</p>
          </AdminLayout>
        </MemoryRouter>,
      )
    })

    const sidebar = container.querySelector(
      '#admin-shell-sidebar',
    ) as HTMLElement
    expect(sidebar.hasAttribute('inert')).toBe(true)

    await act(async () => {
      root.unmount()
    })
  })

  it('does not mark sidebar inert on wide viewport', async () => {
    installMatchMedia(false)
    mockSession('staff')
    const container = document.createElement('div')
    const root: Root = createRoot(container)

    await act(async () => {
      root.render(
        <MemoryRouter>
          <AdminLayout>
            <p>Page content</p>
          </AdminLayout>
        </MemoryRouter>,
      )
    })

    const sidebar = container.querySelector(
      '#admin-shell-sidebar',
    ) as HTMLElement
    expect(sidebar.hasAttribute('inert')).toBe(false)

    await act(async () => {
      root.unmount()
    })
  })

  it('removes sidebar inert when mobile nav opens on narrow viewport', async () => {
    installMatchMedia(true)
    mockSession('staff')
    const container = document.createElement('div')
    const root: Root = createRoot(container)

    await act(async () => {
      root.render(
        <MemoryRouter>
          <AdminLayout>
            <p>Page content</p>
          </AdminLayout>
        </MemoryRouter>,
      )
    })

    const toggle = container.querySelector(
      '.admin-shell__menu-toggle',
    ) as HTMLButtonElement
    const sidebar = container.querySelector(
      '#admin-shell-sidebar',
    ) as HTMLElement
    expect(sidebar.hasAttribute('inert')).toBe(true)

    await act(async () => {
      toggle.click()
    })
    expect(sidebar.hasAttribute('inert')).toBe(false)

    await act(async () => {
      root.unmount()
    })
  })

  it('updates sidebar inert when viewport media query changes', async () => {
    const { setMatches } = installMatchMedia(true)
    mockSession('staff')
    const container = document.createElement('div')
    const root: Root = createRoot(container)

    await act(async () => {
      root.render(
        <MemoryRouter>
          <AdminLayout>
            <p>Page content</p>
          </AdminLayout>
        </MemoryRouter>,
      )
    })

    const sidebar = container.querySelector(
      '#admin-shell-sidebar',
    ) as HTMLElement
    expect(sidebar.hasAttribute('inert')).toBe(true)

    await act(async () => {
      setMatches(false)
    })
    expect(sidebar.hasAttribute('inert')).toBe(false)

    await act(async () => {
      setMatches(true)
    })
    expect(sidebar.hasAttribute('inert')).toBe(true)

    await act(async () => {
      root.unmount()
    })
  })
})
