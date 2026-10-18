/**
 * @vitest-environment jsdom
 */
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PublicSalonPage } from './PublicSalonPage'

const reactActEnv = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean
}
reactActEnv.IS_REACT_ACT_ENVIRONMENT = true

const roots: Array<{ root: Root; container: HTMLDivElement }> = []
const SLUG = 'demo-salon'
const SERVICE_ID = 'service-1'

function response(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => body,
  } as unknown as Response
}

function mountPublicSalon() {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  roots.push({ root, container })
  act(() => {
    root.render(
      <MemoryRouter initialEntries={[`/s/${SLUG}`]}>
        <Routes>
          <Route path="/s/:slug" element={<PublicSalonPage />} />
        </Routes>
      </MemoryRouter>,
    )
  })
  return container
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

describe('PublicSalonPage Showcase integration', () => {
  it('shows Showcase after services and keeps it out of the booking flow', async () => {
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith(`/api/v1/public/salons/${SLUG}`)) {
        return Promise.resolve(
          response({
            salon_id: 'salon-1',
            slug: SLUG,
            name: 'Салон Лиман',
            currency_code: 'KGS',
            timezone: 'Asia/Bishkek',
            logo_media_id: null,
            background_media_id: null,
            appearance: null,
          }),
        )
      }
      if (url.endsWith(`/api/v1/public/salons/${SLUG}/services`)) {
        return Promise.resolve(
          response({
            salon_id: 'salon-1',
            services: [
              {
                id: SERVICE_ID,
                name: 'Стрижка',
                description: 'Классическая форма',
                duration_minutes: 60,
                buffer_before_minutes: 0,
                buffer_after_minutes: 0,
                price_cents: 150000,
                currency_code: 'KGS',
                cover_media_id: null,
              },
            ],
          }),
        )
      }
      if (url.endsWith(`/api/v1/public/salons/${SLUG}/reviews`)) {
        return Promise.resolve(
          response({
            salon_id: 'salon-1',
            reviews: [
              {
                id: 'review-1',
                rating: 5,
                title: 'Отличный сервис',
                body: 'Обязательно вернусь.',
                staff_display_name: 'Алия',
                published_at: '2026-01-05T12:00:00Z',
                created_at: '2026-01-04T12:00:00Z',
              },
            ],
          }),
        )
      }
      if (url.includes('/showcase?')) {
        return Promise.resolve(
          response({
            salon_id: 'salon-1',
            items: [
              {
                id: 'showcase-1',
                category: 'work',
                title: 'Вечерняя укладка',
                description: null,
                price_cents: null,
                image_url: `/api/v1/public/salons/${SLUG}/showcase/items/showcase-1/image`,
              },
            ],
          }),
        )
      }
      if (url.endsWith(`/services/${SERVICE_ID}/staff`)) {
        return Promise.resolve(
          response({ salon_id: 'salon-1', service_id: SERVICE_ID, staff: [] }),
        )
      }
      throw new Error(`Unexpected request URL: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    const container = mountPublicSalon()
    await settle()

    const services = container.querySelector('.public-salon-page__services')
    const showcase = container.querySelector('.showcase-section')
    const reviews = container.querySelector('.public-reviews-section')
    expect(services).not.toBeNull()
    expect(showcase).not.toBeNull()
    expect(reviews).not.toBeNull()
    expect(
      Boolean(
        services!.compareDocumentPosition(showcase!) &
          Node.DOCUMENT_POSITION_FOLLOWING,
      ),
    ).toBe(true)
    expect(
      Boolean(
        showcase!.compareDocumentPosition(reviews!) &
          Node.DOCUMENT_POSITION_FOLLOWING,
      ),
    ).toBe(true)
    expect(container.textContent).toContain('Отличный сервис')
    expect(container.textContent).toContain('Вечерняя укладка')

    const serviceButton = container.querySelector<HTMLButtonElement>(
      '.service-card--interactive',
    )
    expect(serviceButton).not.toBeNull()
    act(() => serviceButton?.click())
    await settle()

    expect(container.querySelector('.public-salon-page__booking')).not.toBeNull()
    expect(container.querySelector('.showcase-section')).toBeNull()
    expect(container.querySelector('.public-reviews-section')).toBeNull()
    expect(container.textContent).toContain('Выберите мастера')
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/bookings'))).toBe(
      false,
    )
  })
})
