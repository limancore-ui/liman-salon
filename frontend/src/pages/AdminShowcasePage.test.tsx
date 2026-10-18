/**
 * @vitest-environment jsdom
 */
import { act, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminShowcasePage } from './AdminShowcasePage'
import { ApiError } from '../api/errors'
import * as showcaseApi from '../api/adminShowcase'
import * as mediaApi from '../api/media'
import { useAuth } from '../auth/AuthContext'
import type { AdminShowcaseItem } from '../types/adminShowcase'
import type { MediaAssetResponse } from '../types/media'

vi.mock('../auth/AuthContext', () => ({ useAuth: vi.fn() }))
vi.mock('../components/AdminLayout', () => ({
  AdminLayout: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))
vi.mock('../components/AdminMediaPreview', () => ({
  AdminMediaPreview: ({ alt }: { alt: string }) => <div data-testid="media-preview">{alt}</div>,
}))
vi.mock('../api/adminShowcase', () => ({
  fetchAdminShowcaseItems: vi.fn(),
  createAdminShowcaseItem: vi.fn(),
  patchAdminShowcaseItem: vi.fn(),
  publishAdminShowcaseItem: vi.fn(),
  unpublishAdminShowcaseItem: vi.fn(),
  deleteAdminShowcaseItem: vi.fn(),
}))
vi.mock('../api/media', () => ({ fetchAdminMediaList: vi.fn() }))

const mockedUseAuth = vi.mocked(useAuth)
const mockedFetchItems = vi.mocked(showcaseApi.fetchAdminShowcaseItems)
const mockedCreate = vi.mocked(showcaseApi.createAdminShowcaseItem)
const mockedPatch = vi.mocked(showcaseApi.patchAdminShowcaseItem)
const mockedPublish = vi.mocked(showcaseApi.publishAdminShowcaseItem)
const mockedUnpublish = vi.mocked(showcaseApi.unpublishAdminShowcaseItem)
const mockedDelete = vi.mocked(showcaseApi.deleteAdminShowcaseItem)
const mockedFetchMedia = vi.mocked(mediaApi.fetchAdminMediaList)

const TOKEN = 'admin-test-token'
const SALON_ID = 'salon-1'

function makeItem(overrides: Partial<AdminShowcaseItem> = {}): AdminShowcaseItem {
  return {
    id: 'item-1',
    salon_id: SALON_ID,
    category: 'work',
    title: 'Layered haircut',
    description: null,
    price_cents: null,
    media_asset_id: 'media-1',
    sort_order: 0,
    is_published: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function makeMedia(overrides: Partial<MediaAssetResponse> = {}): MediaAssetResponse {
  return {
    id: 'media-1',
    salon_id: SALON_ID,
    original_filename: 'work-photo.webp',
    content_type: 'image/webp',
    byte_size: 2048,
    checksum_sha256: null,
    width_px: 800,
    height_px: 600,
    created_by_user_id: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function setAuth(role: string, clearAuthAndRedirect = vi.fn(), salonId = SALON_ID) {
  mockedUseAuth.mockReturnValue({
    session: {
      token: TOKEN,
      user: { user_id: 'user-1', email: 'owner@example.test', full_name: 'Owner' },
      salon: {
        user_id: 'user-1',
        salon_id: salonId,
        role,
        email: 'owner@example.test',
        salon_name: 'Demo Salon',
        salon_slug: 'demo-salon',
        currency_code: 'KGS',
      },
      salons: [],
    },
    clearAuthAndRedirect,
  } as unknown as ReturnType<typeof useAuth>)
  return clearAuthAndRedirect
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

const reactActEnv = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean
}
reactActEnv.IS_REACT_ACT_ENVIRONMENT = true

describe('AdminShowcasePage', () => {
  let container: HTMLDivElement
  let root: Root

  async function renderPage(settle = true) {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <AdminShowcasePage />
        </MemoryRouter>,
      )
      if (settle) {
        await Promise.resolve()
        await Promise.resolve()
      }
    })
  }

  async function settle() {
    await act(async () => {
      await new Promise<void>((resolve) => setTimeout(resolve, 0))
      await Promise.resolve()
    })
  }

  function button(text: string): HTMLButtonElement | undefined {
    return Array.from(container.querySelectorAll('button')).find(
      (candidate) => candidate.textContent?.trim() === text,
    ) as HTMLButtonElement | undefined
  }

  async function clickButton(text: string) {
    const target = button(text)
    expect(target, `button "${text}"`).toBeTruthy()
    await act(async () => {
      target?.click()
      await new Promise<void>((resolve) => setTimeout(resolve, 0))
      await Promise.resolve()
    })
  }

  function field(labelText: string): HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement {
    const label = Array.from(container.querySelectorAll('label')).find((candidate) =>
      candidate.textContent?.includes(labelText),
    )
    const control = label?.htmlFor
      ? container.querySelector(`#${CSS.escape(label.htmlFor)}`)
      : label?.querySelector('input, textarea, select')
    expect(control, `field "${labelText}"`).toBeTruthy()
    return control as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
  }

  async function setField(labelText: string, value: string) {
    const control = field(labelText)
    await act(async () => {
      const prototype = control instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : control instanceof HTMLTextAreaElement
          ? HTMLTextAreaElement.prototype
          : HTMLInputElement.prototype
      Object.getOwnPropertyDescriptor(prototype, 'value')?.set?.call(control, value)
      control.dispatchEvent(new Event(control instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true }))
      await new Promise<void>((resolve) => setTimeout(resolve, 0))
    })
  }

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    vi.clearAllMocks()
    setAuth('owner')
    mockedFetchItems.mockResolvedValue([makeItem()])
    mockedFetchMedia.mockResolvedValue([makeMedia()])
    mockedCreate.mockResolvedValue(makeItem({ id: 'item-2', title: 'New display item' }))
    mockedPatch.mockResolvedValue(makeItem({ title: 'Updated haircut' }))
    mockedPublish.mockResolvedValue(makeItem({ is_published: true }))
    mockedUnpublish.mockResolvedValue(makeItem({ is_published: false }))
    mockedDelete.mockResolvedValue(undefined)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    vi.restoreAllMocks()
  })

  it('shows the loading state while the list request is pending', async () => {
    mockedFetchItems.mockReturnValue(new Promise<AdminShowcaseItem[]>(() => {}))

    await renderPage(false)

    expect(container.textContent).toContain('Загрузка витрины…')
  })

  it('shows the empty state when the salon has no items', async () => {
    mockedFetchItems.mockResolvedValue([])

    await renderPage()

    expect(container.textContent).toContain('Витрина пока пуста.')
  })

  it('keeps the current salon data when list requests resolve in reverse order', async () => {
    const firstSalonRequest = deferred<AdminShowcaseItem[]>()
    const secondSalonRequest = deferred<AdminShowcaseItem[]>()
    mockedFetchItems
      .mockReturnValueOnce(firstSalonRequest.promise)
      .mockReturnValueOnce(secondSalonRequest.promise)

    await renderPage(false)
    expect(mockedFetchItems).toHaveBeenCalledTimes(1)

    setAuth('owner', vi.fn(), 'salon-2')
    await renderPage(false)
    expect(mockedFetchItems).toHaveBeenCalledTimes(2)
    expect(container.textContent).toContain('Загрузка витрины…')
    expect(container.textContent).not.toContain('Layered haircut')

    const currentSalonItem = makeItem({
      id: 'salon-2-item',
      salon_id: 'salon-2',
      title: 'Current salon item',
    })
    await act(async () => {
      secondSalonRequest.resolve([currentSalonItem])
      await secondSalonRequest.promise
    })
    expect(container.textContent).toContain('Current salon item')

    const latePreviousSalonItem = makeItem({
      id: 'salon-1-late-item',
      title: 'Late previous salon item',
    })
    await act(async () => {
      firstSalonRequest.resolve([latePreviousSalonItem])
      await firstSalonRequest.promise
    })

    expect(container.textContent).toContain('Current salon item')
    expect(container.textContent).not.toContain('Late previous salon item')
  })

  it('creates an item using a media asset belonging to the active salon', async () => {
    await renderPage()
    await clickButton('Добавить позицию')
    await settle()
    await setField('Название', 'Color refresh')
    await setField('Категория', 'dyes')
    await setField('Фотография из медиабиблиотеки', 'media-1')
    await setField('Цена в валюте салона', '125.50')
    await clickButton('Сохранить позицию')

    expect(mockedCreate).toHaveBeenCalledWith(TOKEN, SALON_ID, {
      category: 'dyes',
      title: 'Color refresh',
      media_asset_id: 'media-1',
      description: null,
      price_cents: 12550,
      sort_order: 0,
    })
    expect(container.textContent).toContain('Позиция добавлена.')
  })

  it('edits only changed fields through PATCH', async () => {
    await renderPage()
    await clickButton('Изменить')
    await settle()
    await setField('Название', 'Updated haircut')
    await clickButton('Сохранить позицию')

    expect(mockedPatch).toHaveBeenCalledWith(TOKEN, SALON_ID, 'item-1', {
      title: 'Updated haircut',
    })
  })

  it('keeps create form values after a POST failure', async () => {
    mockedCreate.mockRejectedValueOnce(new ApiError(500, 'internal create detail'))
    await renderPage()
    await clickButton('Добавить позицию')
    await settle()
    await setField('Название', 'Keep this new title')
    await setField('Категория', 'cosmetics')
    await setField('Фотография из медиабиблиотеки', 'media-1')
    await setField('Описание (необязательно)', 'Keep this description')
    await setField('Цена в валюте салона', '42.75')

    await clickButton('Сохранить позицию')

    expect(mockedCreate).toHaveBeenCalledWith(TOKEN, SALON_ID, {
      category: 'cosmetics',
      title: 'Keep this new title',
      media_asset_id: 'media-1',
      description: 'Keep this description',
      price_cents: 4275,
      sort_order: 0,
    })
    expect(container.querySelector('form.admin-showcase__form')).toBeTruthy()
    expect(field('Название').value).toBe('Keep this new title')
    expect(field('Категория').value).toBe('cosmetics')
    expect(field('Фотография из медиабиблиотеки').value).toBe('media-1')
    expect(field('Описание (необязательно)').value).toBe('Keep this description')
    expect(field('Цена в валюте салона').value).toBe('42.75')
    expect(container.textContent).toContain('Не удалось выполнить действие. Попробуйте ещё раз.')
    expect(container.textContent).not.toContain('internal create detail')
    expect(container.textContent).not.toContain('Позиция добавлена.')
  })

  it('keeps edit form values after a PATCH failure', async () => {
    mockedPatch.mockRejectedValueOnce(new ApiError(500, 'internal patch detail'))
    await renderPage()
    await clickButton('Изменить')
    await settle()
    await setField('Название', 'Keep this edited title')
    await setField('Описание (необязательно)', 'Keep edited description')

    await clickButton('Сохранить позицию')

    expect(mockedPatch).toHaveBeenCalledWith(TOKEN, SALON_ID, 'item-1', {
      title: 'Keep this edited title',
      description: 'Keep edited description',
    })
    expect(container.querySelector('form.admin-showcase__form')).toBeTruthy()
    expect(field('Название').value).toBe('Keep this edited title')
    expect(field('Описание (необязательно)').value).toBe('Keep edited description')
    expect(container.textContent).toContain('Не удалось выполнить действие. Попробуйте ещё раз.')
    expect(container.textContent).not.toContain('internal patch detail')
    expect(container.textContent).not.toContain('Изменения сохранены.')
  })

  it('shows a safe 403 message and preserves the create form for retry', async () => {
    mockedCreate.mockRejectedValueOnce(new ApiError(403, 'private authorization detail', 'forbidden'))
    await renderPage()
    await clickButton('Добавить позицию')
    await settle()
    await setField('Название', 'Retry after access is restored')
    await setField('Фотография из медиабиблиотеки', 'media-1')

    await clickButton('Сохранить позицию')

    expect(mockedCreate).toHaveBeenCalledOnce()
    expect(container.querySelector('form.admin-showcase__form')).toBeTruthy()
    expect(field('Название').value).toBe('Retry after access is restored')
    expect(field('Фотография из медиабиблиотеки').value).toBe('media-1')
    expect(container.textContent).toContain('Недостаточно прав для этого действия.')
    expect(container.textContent).not.toContain('private authorization detail')
    expect(container.textContent).not.toContain('Позиция добавлена.')
  })

  it('allows an admin to open the Showcase editor', async () => {
    setAuth('admin')
    await renderPage()

    expect(button('Добавить позицию')).toBeTruthy()
    await clickButton('Изменить')
    expect(field('Название').value).toBe('Layered haircut')
  })

  it('publishes and hides items through their dedicated actions', async () => {
    mockedFetchItems
      .mockResolvedValueOnce([makeItem()])
      .mockResolvedValueOnce([makeItem({ is_published: true })])
      .mockResolvedValueOnce([makeItem({ is_published: false })])
    await renderPage()
    await clickButton('Опубликовать')
    expect(mockedPublish).toHaveBeenCalledWith(TOKEN, SALON_ID, 'item-1')

    await clickButton('Скрыть')
    expect(mockedUnpublish).toHaveBeenCalledWith(TOKEN, SALON_ID, 'item-1')
  })

  it('requires confirmation before deleting an item', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    await renderPage()
    await clickButton('Удалить')

    expect(confirm).toHaveBeenCalledWith('Удалить позицию «Layered haircut»?')
    expect(mockedDelete).toHaveBeenCalledWith(TOKEN, SALON_ID, 'item-1')
  })

  it('shows an error and retries loading the list', async () => {
    mockedFetchItems
      .mockRejectedValueOnce(new ApiError(500, 'internal detail'))
      .mockResolvedValueOnce([])
    await renderPage()

    expect(container.textContent).toContain('Не удалось загрузить витрину.')
    expect(container.textContent).not.toContain('internal detail')
    await clickButton('Повторить')
    expect(mockedFetchItems).toHaveBeenCalledTimes(2)
    expect(container.textContent).toContain('Витрина пока пуста.')
  })

  it('redirects on expired authorization', async () => {
    const clearAuthAndRedirect = setAuth('owner')
    mockedFetchItems.mockRejectedValue(new ApiError(401, 'unauthorized'))

    await renderPage()

    expect(clearAuthAndRedirect).toHaveBeenCalledOnce()
  })

  it.each(['staff', 'receptionist'])('%s access is read-only and does not load the media picker', async (role) => {
    setAuth(role)
    await renderPage()

    expect(container.textContent).toContain('Для вашей роли доступен только просмотр витрины.')
    expect(button('Добавить позицию')).toBeUndefined()
    expect(button('Изменить')).toBeUndefined()
    expect(button('Опубликовать')).toBeUndefined()
    expect(button('Удалить')).toBeUndefined()
    expect(mockedFetchMedia).not.toHaveBeenCalled()
    expect(mockedCreate).not.toHaveBeenCalled()
    expect(mockedPatch).not.toHaveBeenCalled()
    expect(mockedPublish).not.toHaveBeenCalled()
    expect(mockedUnpublish).not.toHaveBeenCalled()
    expect(mockedDelete).not.toHaveBeenCalled()
  })

  it('does not offer a media asset from a different salon', async () => {
    mockedFetchMedia.mockResolvedValue([makeMedia({ id: 'foreign-media', salon_id: 'salon-2' })])
    await renderPage()
    await clickButton('Добавить позицию')
    await settle()

    expect(field('Фотография из медиабиблиотеки').querySelector('option[value="foreign-media"]')).toBeNull()
    await setField('Название', 'No foreign media')
    await clickButton('Сохранить позицию')
    expect(container.textContent).toContain('Выберите доступную фотографию из медиабиблиотеки.')
    expect(mockedCreate).not.toHaveBeenCalled()
  })
})
