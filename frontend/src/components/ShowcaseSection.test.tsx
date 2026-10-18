/**
 * @vitest-environment jsdom
 */
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ShowcaseSection } from './ShowcaseSection'
import type {
  PublicShowcaseItem,
  PublicShowcaseResponse,
} from '../types/publicShowcase'

const reactActEnv = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean
}
reactActEnv.IS_REACT_ACT_ENVIRONMENT = true

const roots: Array<{ root: Root; container: HTMLDivElement }> = []

function jsonResponse(body: PublicShowcaseResponse, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Not Found',
    json: async () => body,
  } as unknown as Response
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

function mountShowcase() {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  roots.push({ root, container })
  act(() => {
    root.render(<ShowcaseSection slug="demo-salon" currencyCode="KGS" />)
  })
  return container
}

function buttonByText(container: HTMLElement, label: string): HTMLButtonElement {
  const button = Array.from(container.querySelectorAll('button')).find(
    (candidate) => candidate.textContent?.trim() === label,
  )
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`Button not found: ${label}`)
  }
  return button
}

async function settle() {
  await act(async () => {
    await Promise.resolve()
    await new Promise<void>((resolve) => setTimeout(resolve, 0))
    await Promise.resolve()
  })
}

function item(
  overrides: Partial<PublicShowcaseItem> = {},
): PublicShowcaseItem {
  return {
    id: 'item-1',
    category: 'work',
    title: 'Образ для фотосессии',
    description: 'Мягкие волны и естественный объём',
    price_cents: 125000,
    image_url: '/api/v1/public/salons/demo/showcase/items/item-1/image',
    ...overrides,
  }
}

function payload(items: PublicShowcaseItem[] = []): PublicShowcaseResponse {
  return { salon_id: 'salon-1', items }
}

afterEach(() => {
  for (const { root, container } of roots.splice(0)) {
    act(() => root.unmount())
    container.remove()
  }
  vi.unstubAllGlobals()
})

describe('ShowcaseSection', () => {
  it('shows an accessible loading state while the request is pending', async () => {
    const pending = deferred<Response>()
    const fetchMock = vi.fn().mockReturnValue(pending.promise)
    vi.stubGlobal('fetch', fetchMock)

    const container = mountShowcase()
    await act(async () => Promise.resolve())

    expect(container.querySelector('[role="status"]')?.textContent).toContain(
      'Загрузка витрины…',
    )
    expect(fetchMock).toHaveBeenCalledTimes(1)
    pending.resolve(jsonResponse(payload()))
    await settle()
  })

  it('renders returned work, image URL, optional details, and keyboard-focusable filters', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(payload([item()])),
    )
    vi.stubGlobal('fetch', fetchMock)

    const container = mountShowcase()
    await settle()

    const image = container.querySelector('img')
    expect(container.textContent).toContain('Витрина салона')
    expect(container.textContent).toContain('Образ для фотосессии')
    expect(container.textContent).toContain('Мягкие волны и естественный объём')
    expect(container.querySelector('.showcase-card__price')).not.toBeNull()
    expect(image?.getAttribute('src')).toBe(
      '/api/v1/public/salons/demo/showcase/items/item-1/image',
    )
    expect(image?.getAttribute('alt')).toBe('Образ для фотосессии')
    expect(image?.getAttribute('loading')).toBe('lazy')

    const filters = Array.from(container.querySelectorAll('.showcase-filter button'))
    expect(filters.map((filter) => filter.textContent?.trim())).toEqual([
      'Все',
      'Работы',
      'Косметика',
      'Красители',
      'Лаки',
    ])
    expect(filters.every((filter) => filter.getAttribute('type') === 'button')).toBe(
      true,
    )
    const allFilter = buttonByText(container, 'Все')
    allFilter.focus()
    expect(document.activeElement).toBe(allFilter)
    expect(allFilter.getAttribute('aria-pressed')).toBe('true')
  })

  it('refetches every supported category and omits the category for “Все”', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload()))
    vi.stubGlobal('fetch', fetchMock)
    const container = mountShowcase()
    await settle()

    const cases = [
      ['Работы', 'work'],
      ['Косметика', 'cosmetics'],
      ['Красители', 'dyes'],
      ['Лаки', 'varnishes'],
      ['Все', undefined],
    ] as const

    for (const [label, category] of cases) {
      act(() => buttonByText(container, label).click())
      await settle()
      const lastCall = fetchMock.mock.calls[fetchMock.mock.calls.length - 1]
      expect(lastCall?.[0]).toBe(
        category
          ? `/api/v1/public/salons/demo-salon/showcase?limit=50&offset=0&category=${category}`
          : '/api/v1/public/salons/demo-salon/showcase?limit=50&offset=0',
      )
    }
  })

  it('shows a localized empty state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(payload())))
    const container = mountShowcase()
    await settle()

    expect(container.querySelector('[role="status"]')?.textContent).toContain(
      'В этой категории пока нет позиций.',
    )
  })

  it('hides absent descriptions and zero or absent prices', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          payload([
            item({ id: 'item-null', description: null, price_cents: null }),
            item({
              id: 'item-zero',
              title: 'Без цены',
              description: '',
              price_cents: 0,
            }),
          ]),
        ),
      ),
    )
    const container = mountShowcase()
    await settle()

    expect(container.querySelectorAll('.showcase-card__description')).toHaveLength(0)
    expect(container.querySelectorAll('.showcase-card__price')).toHaveLength(0)
  })

  it('shows a safe error and retries the request', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error('synthetic internal path'))
      .mockResolvedValueOnce(jsonResponse(payload([item()])))
    vi.stubGlobal('fetch', fetchMock)
    const container = mountShowcase()
    await settle()

    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      'Не удалось загрузить витрину. Попробуйте ещё раз.',
    )
    expect(container.textContent).not.toContain('synthetic internal path')

    act(() => buttonByText(container, 'Повторить').click())
    await settle()

    expect(container.textContent).toContain('Образ для фотосессии')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('shows an image fallback after the returned image URL fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(payload([item()]))),
    )
    const container = mountShowcase()
    await settle()
    const image = container.querySelector('img')
    expect(image).not.toBeNull()

    act(() => image?.dispatchEvent(new Event('error')))

    expect(container.querySelector('.showcase-card__image-fallback')?.textContent).toContain(
      'Изображение временно недоступно',
    )
    expect(container.querySelector('img')).toBeNull()
  })

  it('does not let an older category response replace the current result', async () => {
    const oldResponse = deferred<Response>()
    const currentResponse = deferred<Response>()
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(oldResponse.promise)
      .mockReturnValueOnce(currentResponse.promise)
    vi.stubGlobal('fetch', fetchMock)
    const container = mountShowcase()
    await act(async () => Promise.resolve())

    act(() => buttonByText(container, 'Работы').click())
    await act(async () => Promise.resolve())
    expect(fetchMock).toHaveBeenCalledTimes(2)

    currentResponse.resolve(
      jsonResponse(payload([item({ id: 'current', title: 'Актуальная работа' })])),
    )
    await settle()
    expect(container.textContent).toContain('Актуальная работа')

    oldResponse.resolve(
      jsonResponse(payload([item({ id: 'old', title: 'Устаревший ответ' })])),
    )
    await settle()
    expect(container.textContent).toContain('Актуальная работа')
    expect(container.textContent).not.toContain('Устаревший ответ')
  })
})
