/**
 * @vitest-environment jsdom
 */
import { act, useState } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { AdminLayout } from './AdminLayout'
import { useAuth } from '../auth/AuthContext'

const reactActEnv = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean
}
reactActEnv.IS_REACT_ACT_ENVIRONMENT = true

vi.mock('../auth/AuthContext', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../utils/adminNotificationSound', () => ({
  ensureAdminNotificationAudioReady: vi.fn().mockResolvedValue(null),
  isAdminNotificationSoundMuted: vi.fn().mockReturnValue(true),
  playAdminNotificationSound: vi.fn(),
  setAdminNotificationSoundMuted: vi.fn(),
}))

vi.mock('../hooks/useAdminNotifications', () => ({
  useAdminNotifications: () => {
    const [open, setOpen] = useState(false)
    return {
      canUse: true,
      items: [],
      unreadCount: 0,
      open,
      setOpen,
      loading: false,
      markRead: vi.fn(),
      markAllRead: vi.fn(),
    }
  },
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
    } as MediaQueryList
  }) as typeof window.matchMedia
}

function mockOwnerSession() {
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
        role: 'owner',
        email: 'owner@example.com',
        salon_name: 'Liman',
        salon_slug: 'liman',
        timezone: 'UTC',
      },
      salons: [
        {
          salon_id: 'salon-1',
          salon_name: 'Liman',
          salon_slug: 'liman',
          role: 'owner',
        },
      ],
    },
    logout: vi.fn(),
    switchWorkspace: vi.fn(),
    refreshSession: vi.fn(),
    clearAuthAndRedirect: vi.fn(),
  } as unknown as ReturnType<typeof useAuth>)
}

async function renderAdminLayout(container: HTMLElement) {
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
  return root
}

describe('AdminLayout notification panel (mobile nav)', () => {
  const originalMatchMedia = window.matchMedia

  beforeEach(() => {
    installMatchMedia(true)
    mockOwnerSession()
  })

  afterEach(() => {
    vi.clearAllMocks()
    window.matchMedia = originalMatchMedia
  })

  it('opens notification panel from bell and closes it when mobile menu opens', async () => {
    const container = document.createElement('div')
    const root = await renderAdminLayout(container)

    const bell = container.querySelector(
      '.admin-notifications__bell',
    ) as HTMLButtonElement
    expect(bell).not.toBeNull()

    await act(async () => {
      bell.click()
    })
    expect(bell.getAttribute('aria-expanded')).toBe('true')
    expect(
      container.querySelector('.admin-notifications__panel'),
    ).not.toBeNull()

    const menuToggle = container.querySelector(
      '.admin-shell__menu-toggle',
    ) as HTMLButtonElement
    await act(async () => {
      menuToggle.click()
    })

    expect(container.querySelector('.admin-notifications__panel')).toBeNull()
    expect(bell.getAttribute('aria-expanded')).toBe('false')
    expect(menuToggle.getAttribute('aria-expanded')).toBe('true')
    expect(container.querySelector('.admin-shell--nav-open')).not.toBeNull()
    expect(
      container.querySelector('#admin-shell-sidebar')?.hasAttribute('inert'),
    ).toBe(false)

    await act(async () => {
      menuToggle.click()
    })
    expect(menuToggle.getAttribute('aria-expanded')).toBe('false')
    expect(container.querySelector('.admin-shell--nav-open')).toBeNull()
    expect(
      container.querySelector('.admin-notifications__panel'),
    ).toBeNull()

    await act(async () => {
      root.unmount()
    })
  })

  it('does not open notification panel when bell is clicked while mobile menu is open', async () => {
    const container = document.createElement('div')
    const root = await renderAdminLayout(container)

    const menuToggle = container.querySelector(
      '.admin-shell__menu-toggle',
    ) as HTMLButtonElement
    await act(async () => {
      menuToggle.click()
    })
    expect(menuToggle.getAttribute('aria-expanded')).toBe('true')
    expect(container.querySelector('.admin-shell--nav-open')).not.toBeNull()

    const bell = container.querySelector(
      '.admin-notifications__bell',
    ) as HTMLButtonElement
    await act(async () => {
      bell.click()
    })

    expect(bell.getAttribute('aria-expanded')).toBe('false')
    expect(container.querySelector('.admin-notifications__panel')).toBeNull()
    expect(menuToggle.getAttribute('aria-expanded')).toBe('true')
    expect(
      container.querySelector('#admin-shell-sidebar')?.hasAttribute('inert'),
    ).toBe(false)

    await act(async () => {
      root.unmount()
    })
  })
})
