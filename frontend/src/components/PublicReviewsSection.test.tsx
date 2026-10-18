/**
 * @vitest-environment jsdom
 */
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PublicReviewsSection } from './PublicReviewsSection'
import type { PublicSalonReview, PublicSalonReviewsResponse } from '../types/reviews'

const reactActEnv = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean
}
reactActEnv.IS_REACT_ACT_ENVIRONMENT = true

const roots: Array<{ root: Root; container: HTMLDivElement }> = []

function jsonResponse(body: PublicSalonReviewsResponse, status = 200): Response {
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

function review(overrides: Partial<PublicSalonReview> = {}): PublicSalonReview {
  return {
    id: 'review-1',
    rating: 4,
    title: 'Всё понравилось',
    body: 'Очень внимательный мастер.',
    staff_display_name: 'Алия',
    published_at: '2026-01-05T12:00:00Z',
    created_at: '2026-01-04T12:00:00Z',
    ...overrides,
  }
}

function payload(reviews: PublicSalonReview[] = []): PublicSalonReviewsResponse {
  return { salon_id: 'salon-1', reviews }
}

function mountSection(slug = 'demo-salon') {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  roots.push({ root, container })
  act(() => {
    root.render(
      <PublicReviewsSection slug={slug} timeZone="Asia/Bishkek" />,
    )
  })
  return { container, root }
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

afterEach(() => {
  for (const { root, container } of roots.splice(0)) {
    act(() => root.unmount())
    container.remove()
  }
  vi.unstubAllGlobals()
})

describe('PublicReviewsSection', () => {
  it('shows loading while the request is pending', async () => {
    const fetchMock = vi.fn().mockReturnValue(new Promise<Response>(() => {}))
    vi.stubGlobal('fetch', fetchMock)
    const { container } = mountSection()
    await act(async () => Promise.resolve())

    expect(container.querySelector('[role="status"]')?.textContent).toContain(
      'Загрузка отзывов…',
    )
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('renders published review text, rating, date, and optional staff name safely', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          payload([
            review({
              body: '<img src=x onerror=alert(1)> текст',
              staff_display_name: 'Алия',
            }),
            review({
              id: 'review-2',
              title: null,
              body: null,
              staff_display_name: null,
              rating: 5,
            }),
          ]),
        ),
      ),
    )
    const { container } = mountSection()
    await settle()

    expect(container.textContent).toContain('Отзывы клиентов')
    expect(container.textContent).toContain('<img src=x onerror=alert(1)> текст')
    expect(container.textContent).toContain('Всё понравилось')
    expect(container.textContent).toContain('Мастер: Алия')
    expect(container.textContent).toContain('5 января 2026')
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelectorAll('[role="img"]')[0]?.getAttribute('aria-label')).toBe(
      'Оценка: 4 из 5',
    )
    expect(container.querySelectorAll('.public-review-card__title')).toHaveLength(1)
    expect(container.querySelectorAll('.public-review-card__body')).toHaveLength(1)
    expect(container.querySelectorAll('.public-review-card__meta p')).toHaveLength(1)
    expect(container.querySelector('time')?.getAttribute('dateTime')).toBe(
      '2026-01-05T12:00:00Z',
    )
  })

  it('shows an empty state when the API returns no public reviews', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(payload())))
    const { container } = mountSection()
    await settle()

    expect(container.querySelector('[role="status"]')?.textContent).toContain(
      'Пока нет опубликованных отзывов.',
    )
  })

  it('shows a localized error and retries the request', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error('synthetic internal path'))
      .mockResolvedValueOnce(jsonResponse(payload([review()])))
    vi.stubGlobal('fetch', fetchMock)
    const { container } = mountSection()
    await settle()

    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      'Не удалось загрузить отзывы. Попробуйте ещё раз.',
    )
    expect(container.textContent).not.toContain('synthetic internal path')

    act(() => buttonByText(container, 'Повторить').click())
    await settle()

    expect(container.textContent).toContain('Всё понравилось')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('aborts the old slug request and ignores its late response', async () => {
    const previous = deferred<Response>()
    const current = deferred<Response>()
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(previous.promise)
      .mockReturnValueOnce(current.promise)
    vi.stubGlobal('fetch', fetchMock)
    const { container, root } = mountSection('old-salon')
    await act(async () => Promise.resolve())
    const oldSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal

    act(() => {
      root.render(
        <PublicReviewsSection slug="new-salon" timeZone="Asia/Bishkek" />,
      )
    })
    await act(async () => Promise.resolve())
    expect(oldSignal.aborted).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(2)

    current.resolve(jsonResponse(payload([review({ title: 'Новый отзыв' })])))
    await settle()
    previous.resolve(jsonResponse(payload([review({ title: 'Старый отзыв' })])))
    await settle()

    expect(container.textContent).toContain('Новый отзыв')
    expect(container.textContent).not.toContain('Старый отзыв')
  })
})
