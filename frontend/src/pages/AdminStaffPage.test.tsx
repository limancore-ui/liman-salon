/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createRoot, type Root } from 'react-dom/client'
import { act, type ReactNode } from 'react'
import { AdminStaffPage } from './AdminStaffPage'
import { createAdminStaff, fetchAdminStaff, patchAdminStaff } from '../api/staff'
import { ApiError } from '../api/errors'
import { useAuth } from '../auth/AuthContext'
import type { StaffListItem } from '../types/staff'

vi.mock('../api/staff', () => ({
  fetchAdminStaff: vi.fn(),
  createAdminStaff: vi.fn(),
  patchAdminStaff: vi.fn(),
}))

vi.mock('../auth/AuthContext', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../components/AdminLayout', () => ({
  AdminLayout: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

vi.mock('../components/AdminEntityMediaAttach', () => ({
  AdminEntityMediaAttach: () => <span data-testid="media-attach" />,
}))

vi.mock('../hooks/useSalonMediaAttachmentIndex', () => ({
  useSalonMediaAttachmentIndex: () => ({
    assets: [],
    loading: false,
    error: null,
    reload: vi.fn(),
    getAttachment: () => undefined,
  }),
}))

const mockedFetch = vi.mocked(fetchAdminStaff)
const mockedCreate = vi.mocked(createAdminStaff)
const mockedPatch = vi.mocked(patchAdminStaff)
const mockedUseAuth = vi.mocked(useAuth)

const TOKEN = 'tok-1'
const SALON_ID = 'salon-1'

function makeStaff(overrides: Partial<StaffListItem> = {}): StaffListItem {
  return {
    id: 'staff-1',
    display_name: 'Alex',
    title: 'Stylist',
    bio: null,
    color_hex: null,
    is_bookable: true,
    is_active: true,
    sort_order: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function setAuth(role: string, clearAuthAndRedirect = vi.fn()) {
  mockedUseAuth.mockReturnValue({
    session: { token: TOKEN, salon: { salon_id: SALON_ID, role } },
    clearAuthAndRedirect,
  } as unknown as ReturnType<typeof useAuth>)
  return clearAuthAndRedirect
}

function flushPromises() {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, 0)
  })
}

describe('AdminStaffPage CRUD', () => {
  let container: HTMLDivElement
  let root: Root

  async function settle() {
    await act(async () => {
      await flushPromises()
      await flushPromises()
    })
  }

  async function renderPage() {
    await act(async () => {
      root.render(<AdminStaffPage />)
      await flushPromises()
      await flushPromises()
    })
  }

  function buttonByText(scope: ParentNode, text: string | RegExp): HTMLButtonElement | undefined {
    return Array.from(scope.querySelectorAll('button')).find((b) => {
      const label = b.textContent?.trim() ?? ''
      return typeof text === 'string' ? label === text : text.test(label)
    }) as HTMLButtonElement | undefined
  }

  function inputByLabel(labelText: string): HTMLInputElement | undefined {
    const label = Array.from(container.querySelectorAll('label')).find((el) =>
      el.textContent?.includes(labelText),
    )
    const id = label?.htmlFor
    if (id) {
      return container.querySelector(`#${CSS.escape(id)}`) as HTMLInputElement | undefined
    }
    return label?.querySelector('input') as HTMLInputElement | undefined
  }

  async function click(el: HTMLElement | undefined | null) {
    expect(el).toBeTruthy()
    await act(async () => {
      el?.click()
      await flushPromises()
    })
  }

  async function setInputValue(el: HTMLInputElement, value: string) {
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set?.call(
        el,
        value,
      )
      el.dispatchEvent(new Event('input', { bubbles: true }))
      await flushPromises()
    })
  }

  beforeEach(() => {
    ;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    vi.clearAllMocks()
    setAuth('owner')
    mockedFetch.mockResolvedValue([makeStaff()])
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
  })

  it('creates staff and refreshes the list', async () => {
    mockedCreate.mockResolvedValue(makeStaff({ display_name: 'Jordan' }))
    mockedFetch
      .mockResolvedValueOnce([makeStaff()])
      .mockResolvedValueOnce([makeStaff(), makeStaff({ id: 'staff-2', display_name: 'Jordan' })])

    await renderPage()
    await settle()

    await click(buttonByText(container, 'Add staff'))
    await settle()

    const nameInput = inputByLabel('Display name')
    expect(nameInput).toBeTruthy()
    await setInputValue(nameInput!, 'Jordan')

    await click(buttonByText(container, 'Create staff'))
    await settle()

    expect(mockedCreate).toHaveBeenCalledWith(TOKEN, SALON_ID, {
      display_name: 'Jordan',
    })
    expect(mockedFetch).toHaveBeenCalledTimes(2)
    expect(container.textContent).toContain('Jordan')
  })

  it('requires display name on create', async () => {
    await renderPage()
    await settle()

    await click(buttonByText(container, 'Add staff'))
    await settle()

    await click(buttonByText(container, 'Create staff'))
    await settle()

    expect(mockedCreate).not.toHaveBeenCalled()
    expect(container.textContent).toContain('Display name is required.')
  })

  it('edits staff with a partial PATCH and refreshes', async () => {
    mockedPatch.mockResolvedValue(makeStaff({ display_name: 'Alex R.' }))
    mockedFetch
      .mockResolvedValueOnce([makeStaff()])
      .mockResolvedValueOnce([makeStaff({ display_name: 'Alex R.' })])

    await renderPage()
    await settle()

    await click(buttonByText(container, 'Edit'))
    await settle()

    const nameInput = inputByLabel('Display name')
    await setInputValue(nameInput!, 'Alex R.')

    await click(buttonByText(container, 'Save changes'))
    await settle()

    expect(mockedPatch).toHaveBeenCalledWith(TOKEN, SALON_ID, 'staff-1', {
      display_name: 'Alex R.',
    })
    expect(mockedFetch).toHaveBeenCalledTimes(2)
    expect(container.textContent).toContain('Alex R.')
  })

  it('toggles is_active and is_bookable independently', async () => {
    mockedPatch.mockImplementation(async (_t, _s, _id, body) =>
      makeStaff({
        is_active: body.is_active ?? true,
        is_bookable: body.is_bookable ?? true,
      }),
    )

    await renderPage()
    await settle()

    await click(buttonByText(container, 'Make unbookable'))
    await settle()

    expect(mockedPatch).toHaveBeenLastCalledWith(TOKEN, SALON_ID, 'staff-1', {
      is_bookable: false,
    })

    mockedFetch.mockResolvedValue([makeStaff({ is_bookable: false })])
    await settle()

    await click(buttonByText(container, 'Deactivate'))
    await settle()
    expect(mockedPatch).toHaveBeenCalledTimes(1)

    await click(buttonByText(container, 'Confirm deactivation'))
    await settle()

    expect(mockedPatch).toHaveBeenLastCalledWith(TOKEN, SALON_ID, 'staff-1', {
      is_active: false,
    })
    expect(mockedPatch).toHaveBeenCalledTimes(2)
  })

  it('shows API errors on create and toggle', async () => {
    mockedCreate.mockRejectedValue(new ApiError(422, 'display_name must not be blank'))
    mockedPatch.mockRejectedValue(new ApiError(403, 'Forbidden'))

    await renderPage()
    await settle()

    await click(buttonByText(container, 'Add staff'))
    await settle()

    const nameInput = inputByLabel('Display name')
    await setInputValue(nameInput!, 'Bad')
    await click(buttonByText(container, 'Create staff'))
    await settle()

    expect(container.textContent).toContain('display_name must not be blank')

    await click(buttonByText(container, 'Deactivate'))
    await settle()
    await click(buttonByText(container, 'Confirm deactivation'))
    await settle()

    expect(container.textContent).toContain('You do not have permission to update staff.')
    expect(buttonByText(container, 'Make unbookable')).toBeTruthy()
  })

  it('shows loading state while list loads', async () => {
    let resolveFetch!: (rows: StaffListItem[]) => void
    mockedFetch.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve
        }),
    )

    await renderPage()
    expect(container.textContent).toContain('Loading staff…')

    await act(async () => {
      resolveFetch([makeStaff()])
      await flushPromises()
      await flushPromises()
    })

    expect(container.textContent).not.toContain('Loading staff…')
    expect(container.textContent).toContain('Alex')
  })

  it('blocks save when clearing title and shows unsupported message', async () => {
    mockedFetch.mockResolvedValue([makeStaff({ title: 'Stylist' })])

    await renderPage()
    await settle()

    await click(buttonByText(container, 'Edit'))
    await settle()

    const titleInput = inputByLabel('Title')
    expect(titleInput).toBeTruthy()
    await setInputValue(titleInput!, '')

    await click(buttonByText(container, 'Save changes'))
    await settle()

    expect(mockedPatch).not.toHaveBeenCalled()
    expect(container.textContent).toContain('Clearing title, bio, or color is not supported')
  })

  it('rejects title longer than 100 characters on create', async () => {
    await renderPage()
    await settle()

    await click(buttonByText(container, 'Add staff'))
    await settle()

    const nameInput = inputByLabel('Display name')
    await setInputValue(nameInput!, 'Jordan')
    const titleInput = inputByLabel('Title')
    await setInputValue(titleInput!, 't'.repeat(101))

    await click(buttonByText(container, 'Create staff'))
    await settle()

    expect(mockedCreate).not.toHaveBeenCalled()
    expect(container.textContent).toContain('Title must be at most 100 characters.')
  })

  it('disables row toggles while that row is being edited', async () => {
    await renderPage()
    await settle()

    await click(buttonByText(container, 'Edit'))
    await settle()

    const deactivate = buttonByText(container, 'Deactivate')
    const unbookable = buttonByText(container, 'Make unbookable')
    expect(deactivate?.disabled).toBe(true)
    expect(unbookable?.disabled).toBe(true)
  })

  it('hides write actions for receptionist role', async () => {
    setAuth('receptionist')
    await renderPage()
    await settle()

    expect(buttonByText(container, 'Add staff')).toBeUndefined()
    expect(buttonByText(container, 'Edit')).toBeUndefined()
    expect(container.textContent).toContain('Alex')
  })
})

describe('AdminStaffPage deactivation confirmation', () => {
  let container: HTMLDivElement
  let root: Root

  async function settle() {
    await act(async () => {
      await flushPromises()
      await flushPromises()
    })
  }

  async function renderPage() {
    await act(async () => {
      root.render(<AdminStaffPage />)
      await flushPromises()
      await flushPromises()
    })
  }

  function buttonByText(scope: ParentNode, text: string | RegExp): HTMLButtonElement | undefined {
    return Array.from(scope.querySelectorAll('button')).find((b) => {
      const label = b.textContent?.trim() ?? ''
      return typeof text === 'string' ? label === text : text.test(label)
    }) as HTMLButtonElement | undefined
  }

  async function click(el: HTMLElement | undefined | null) {
    expect(el).toBeTruthy()
    await act(async () => {
      el?.click()
      await flushPromises()
    })
  }

  beforeEach(() => {
    ;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    vi.clearAllMocks()
    setAuth('owner')
    mockedFetch.mockResolvedValue([makeStaff()])
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
  })

  it('does not PATCH immediately when Deactivate is clicked', async () => {
    await renderPage()
    await settle()

    await click(buttonByText(container, 'Deactivate'))
    await settle()

    expect(mockedPatch).not.toHaveBeenCalled()
    expect(container.textContent).toContain('Deactivate Alex?')
  })

  it('does not PATCH when Cancel is clicked', async () => {
    await renderPage()
    await settle()

    await click(buttonByText(container, 'Deactivate'))
    await settle()
    await click(buttonByText(container, 'Cancel'))
    await settle()

    expect(mockedPatch).not.toHaveBeenCalled()
    expect(buttonByText(container, 'Deactivate')).toBeTruthy()
    expect(container.textContent).not.toContain('Deactivate Alex?')
  })

  it('PATCHes is_active false only after Confirm deactivation', async () => {
    mockedPatch.mockResolvedValue(makeStaff({ is_active: false }))
    mockedFetch
      .mockResolvedValueOnce([makeStaff()])
      .mockResolvedValueOnce([makeStaff({ is_active: false })])

    await renderPage()
    await settle()

    await click(buttonByText(container, 'Deactivate'))
    await settle()
    await click(buttonByText(container, 'Confirm deactivation'))
    await settle()

    expect(mockedPatch).toHaveBeenCalledTimes(1)
    expect(mockedPatch).toHaveBeenCalledWith(TOKEN, SALON_ID, 'staff-1', {
      is_active: false,
    })
  })

  it('shows staff display name in the confirmation prompt', async () => {
    mockedFetch.mockResolvedValue([
      makeStaff({ id: 'staff-2', display_name: 'Jordan Lee' }),
    ])

    await renderPage()
    await settle()

    await click(buttonByText(container, 'Deactivate'))
    await settle()

    expect(container.textContent).toContain('Deactivate Jordan Lee?')
  })

  it('shows API errors after confirm and keeps the page usable', async () => {
    mockedPatch.mockRejectedValue(new ApiError(403, 'Forbidden'))

    await renderPage()
    await settle()

    await click(buttonByText(container, 'Deactivate'))
    await settle()
    await click(buttonByText(container, 'Confirm deactivation'))
    await settle()

    expect(container.textContent).toContain('You do not have permission to update staff.')
    expect(buttonByText(container, 'Edit')).toBeTruthy()
    expect(buttonByText(container, 'Make unbookable')).toBeTruthy()
    expect(mockedPatch).toHaveBeenCalledWith(TOKEN, SALON_ID, 'staff-1', {
      is_active: false,
    })
  })
})
