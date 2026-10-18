/**
 * @vitest-environment jsdom
 */
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAuth } from '../auth/AuthContext'
import { AdminLoginPage } from './AdminLoginPage'
import { AdminNoAccessPage } from './AdminNoAccessPage'
import { AdminWorkspacePickerPage } from './AdminWorkspacePickerPage'

vi.mock('../auth/AuthContext', () => ({
  useAuth: vi.fn(),
}))

const mockedUseAuth = vi.mocked(useAuth)

const reactActEnv = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean
}
reactActEnv.IS_REACT_ACT_ENVIRONMENT = true

async function renderPage(node: React.ReactNode): Promise<{
  container: HTMLDivElement
  root: Root
}> {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  await act(async () => {
    root.render(<MemoryRouter>{node}</MemoryRouter>)
  })
  return { container, root }
}

describe('Admin auth shell pages (RU)', () => {
  afterEach(async () => {
    vi.clearAllMocks()
    document.body.replaceChildren()
  })

  it('renders Russian login form copy', async () => {
    mockedUseAuth.mockReturnValue({
      status: 'anonymous',
      login: vi.fn(),
    } as unknown as ReturnType<typeof useAuth>)

    const { container, root } = await renderPage(<AdminLoginPage />)
    expect(container.textContent).toContain('Админ салона')
    expect(container.textContent).toContain(
      'Войдите с учётной записью сотрудника.',
    )
    expect(container.textContent).toContain('Войти')
    expect(container.textContent).not.toContain('Sign in')
    await act(async () => {
      root.unmount()
    })
  })

  it('renders Russian no-access copy with email', async () => {
    mockedUseAuth.mockReturnValue({
      status: 'no_salon_access',
      pendingWorkspace: {
        token: 'tok',
        user: { user_id: 'u1', email: 'guest@example.com', full_name: 'Guest' },
        salons: [],
      },
      logout: vi.fn(),
    } as unknown as ReturnType<typeof useAuth>)

    const { container, root } = await renderPage(<AdminNoAccessPage />)
    expect(container.textContent).toContain('Нет доступа к салону')
    expect(container.textContent).toContain(
      'guest@example.com не привязан ни к одному активному салону.',
    )
    expect(container.textContent).toContain('Выйти')
    expect(container.textContent).not.toContain('No salon access')
    await act(async () => {
      root.unmount()
    })
  })

  it('renders Russian workspace picker copy', async () => {
    mockedUseAuth.mockReturnValue({
      status: 'workspace_picker',
      pendingWorkspace: {
        token: 'tok',
        user: { user_id: 'u1', email: 'owner@example.com', full_name: 'Owner' },
        salons: [
          {
            salon_id: 'salon-1',
            salon_name: 'Liman',
            salon_slug: 'liman',
            role: 'owner',
          },
        ],
      },
      selectWorkspace: vi.fn(),
      logout: vi.fn(),
    } as unknown as ReturnType<typeof useAuth>)

    const { container, root } = await renderPage(<AdminWorkspacePickerPage />)
    expect(container.textContent).toContain('Выберите салон')
    expect(container.textContent).toContain(
      'Вы вошли как owner@example.com. Выберите салон для управления.',
    )
    expect(container.textContent).toContain('Продолжить')
    expect(container.textContent).toContain('Выйти')
    expect(container.textContent).not.toContain('Choose workspace')
    await act(async () => {
      root.unmount()
    })
  })
})
