/**
 * @vitest-environment jsdom
 */
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { AdminAppearancePage } from './AdminAppearancePage'
import { useAuth } from '../auth/AuthContext'
import * as appearanceApi from '../api/salonAppearance'
import * as profileApi from '../api/salonProfile'

const reactActEnv = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean
}
reactActEnv.IS_REACT_ACT_ENVIRONMENT = true

vi.mock('../auth/AuthContext', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../components/AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="admin-layout">{children}</div>
  ),
}))

vi.mock('../hooks/useSalonMediaAttachmentIndex', () => ({
  useSalonMediaAttachmentIndex: () => ({
    assets: [],
    loading: false,
    error: null,
    reload: vi.fn(),
    getAttachment: () => null,
  }),
}))

vi.mock('../api/salonAppearance', () => ({
  fetchSalonAppearance: vi.fn(),
  patchSalonAppearance: vi.fn(),
}))

vi.mock('../api/salonProfile', () => ({
  patchSalonProfile: vi.fn(),
}))

const mockedUseAuth = vi.mocked(useAuth)
const mockedFetch = vi.mocked(appearanceApi.fetchSalonAppearance)
const mockedPatchAppearance = vi.mocked(appearanceApi.patchSalonAppearance)
const mockedPatchProfile = vi.mocked(profileApi.patchSalonProfile)

function mockOwnerSession(refreshSession = vi.fn()) {
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
        salon_name: 'Demo Salon',
        salon_slug: 'demo-salon',
      },
      salons: [],
    },
    clearAuthAndRedirect: vi.fn(),
    refreshSession,
  } as unknown as ReturnType<typeof useAuth>)
  return refreshSession
}

async function renderPage() {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root: Root = createRoot(container)
  await act(async () => {
    root.render(
      <MemoryRouter>
        <AdminAppearancePage />
      </MemoryRouter>,
    )
  })
  // allow load effect
  await act(async () => {
    await Promise.resolve()
  })
  return {
    container,
    cleanup() {
      act(() => root.unmount())
      container.remove()
    },
  }
}

describe('AdminAppearancePage', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it('loads appearance, shows name, and saves colors', async () => {
    mockOwnerSession()
    mockedFetch.mockResolvedValue({
      salon_id: 'salon-1',
      salon_name: 'Demo Salon',
      primary_color: '#2f6b4f',
      accent_soft_color: '#e8f2ec',
      background_color: '#f4f7f5',
    })
    mockedPatchAppearance.mockResolvedValue({
      salon_id: 'salon-1',
      salon_name: 'Demo Salon',
      primary_color: '#2f6b4f',
      accent_soft_color: '#e8f2ec',
      background_color: '#f4f7f5',
    })

    const { container, cleanup } = await renderPage()

    expect(container.textContent).toContain('Demo Salon')
    expect(container.textContent).toContain('Название салона')
    expect(container.textContent).toContain('Предпросмотр')
    const nameInput = container.querySelector(
      'input[type="text"]',
    ) as HTMLInputElement
    expect(nameInput.value).toBe('Demo Salon')
    expect(mockedFetch).toHaveBeenCalledWith('tok', 'salon-1')

    const colorForm = Array.from(container.querySelectorAll('form')).find(
      (f) => f.textContent?.includes('Сохранить изменения'),
    ) as HTMLFormElement
    await act(async () => {
      colorForm.requestSubmit()
      await Promise.resolve()
    })

    expect(mockedPatchAppearance).toHaveBeenCalled()
    expect(mockedPatchProfile).not.toHaveBeenCalled()
    cleanup()
  })

  it('saves renamed salon via profile API and refreshes session', async () => {
    const refreshSession = mockOwnerSession(vi.fn().mockResolvedValue(undefined))
    mockedFetch.mockResolvedValue({
      salon_id: 'salon-1',
      salon_name: 'Demo Salon',
    })
    mockedPatchProfile.mockResolvedValue({
      salon_id: 'salon-1',
      name: 'Новое название',
      slug: 'demo-salon',
    })

    const { container, cleanup } = await renderPage()
    const nameInput = container.querySelector(
      'input[type="text"]',
    ) as HTMLInputElement

    await act(async () => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        'value',
      )?.set
      nativeInputValueSetter?.call(nameInput, 'Новое название')
      nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    })

    const nameForm = Array.from(container.querySelectorAll('form')).find(
      (f) => f.textContent?.includes('Сохранить название'),
    ) as HTMLFormElement
    await act(async () => {
      nameForm.requestSubmit()
      await Promise.resolve()
    })

    expect(mockedPatchProfile).toHaveBeenCalledWith('tok', 'salon-1', {
      name: 'Новое название',
    })
    expect(refreshSession).toHaveBeenCalled()
    expect(container.textContent).toContain('Название салона сохранено.')
    expect(container.querySelector('.admin-appearance__preview-name')?.textContent).toBe(
      'Новое название',
    )
    cleanup()
  })

  it('does not call profile API when name is unchanged', async () => {
    mockOwnerSession()
    mockedFetch.mockResolvedValue({
      salon_id: 'salon-1',
      salon_name: 'Demo Salon',
    })

    const { container, cleanup } = await renderPage()
    const nameForm = Array.from(container.querySelectorAll('form')).find(
      (f) => f.textContent?.includes('Сохранить название'),
    ) as HTMLFormElement
    await act(async () => {
      nameForm.requestSubmit()
      await Promise.resolve()
    })

    expect(mockedPatchProfile).not.toHaveBeenCalled()
    expect(container.textContent).toContain('Название не изменилось.')
    cleanup()
  })

  it('shows error when name save fails', async () => {
    mockOwnerSession()
    mockedFetch.mockResolvedValue({
      salon_id: 'salon-1',
      salon_name: 'Demo Salon',
    })
    mockedPatchProfile.mockRejectedValue(new Error('boom'))

    const { container, cleanup } = await renderPage()
    const nameInput = container.querySelector(
      'input[type="text"]',
    ) as HTMLInputElement
    await act(async () => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        'value',
      )?.set
      nativeInputValueSetter?.call(nameInput, 'Other Name')
      nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    })

    const nameForm = Array.from(container.querySelectorAll('form')).find(
      (f) => f.textContent?.includes('Сохранить название'),
    ) as HTMLFormElement
    await act(async () => {
      nameForm.requestSubmit()
      await Promise.resolve()
    })

    expect(mockedPatchProfile).toHaveBeenCalled()
    expect(container.textContent).toContain('Не удалось сохранить название.')
    cleanup()
  })
})
