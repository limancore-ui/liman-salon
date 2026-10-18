import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  getPublicBookingManageBySlug,
  getPublicReviews,
  getPublicShowcase,
  mapServiceAvailabilityToSelectedSlots,
} from './publicSalon'
import { ApiError } from './errors'
import type { ServiceAvailabilityResponse } from '../types/publicCatalog'
import type { PublicShowcaseResponse } from '../types/publicShowcase'

afterEach(() => {
  vi.unstubAllGlobals()
})

const response: ServiceAvailabilityResponse = {
  service_id: 'svc-1',
  staff: [
    {
      staff_id: 'staff-a',
      slots: [
        {
          service_start: '2026-07-10T10:00:00.000Z',
          service_end: '2026-07-10T11:00:00.000Z',
        },
        {
          service_start: '2026-07-10T10:30:00.000Z',
          service_end: '2026-07-10T11:30:00.000Z',
        },
      ],
    },
    {
      staff_id: 'staff-b',
      slots: [
        {
          service_start: '2026-07-10T10:00:00.000Z',
          service_end: '2026-07-10T11:00:00.000Z',
        },
      ],
    },
  ],
}

describe('mapServiceAvailabilityToSelectedSlots', () => {
  it('returns all starts for a specific staff member', () => {
    const slots = mapServiceAvailabilityToSelectedSlots(response, 'staff-a')
    expect(slots).toHaveLength(2)
    expect(slots.every((s) => s.staff_id === 'staff-a')).toBe(true)
  })

  it('dedupes identical start times for any staff', () => {
    const slots = mapServiceAvailabilityToSelectedSlots(response, undefined)
    expect(slots).toHaveLength(2)
    expect(slots.map((s) => s.service_start)).toEqual([
      '2026-07-10T10:00:00.000Z',
      '2026-07-10T10:30:00.000Z',
    ])
    expect(slots[0]?.staff_id).toBe('staff-a')
  })
})

describe('getPublicBookingManageBySlug', () => {
  const slug = 'demo-salon'
  const bookingId = '11111111-1111-4111-8111-111111111111'
  const token = 'manage-token-secret'

  it('GETs manage URL with token header and parses response', async () => {
    const body = {
      booking_id: bookingId,
      status: 'pending',
      service_id: '22222222-2222-4222-8222-222222222222',
      service_name: 'Haircut',
      staff_id: '33333333-3333-4333-8333-333333333333',
      staff_display_name: 'Alex',
      service_start: '2026-09-25T09:00:00.000Z',
      service_end: '2026-09-25T10:00:00.000Z',
      hold_expires_at: '2026-09-25T09:15:00.000Z',
      can_cancel: true,
      can_reschedule: true,
      timezone: 'Europe/Moscow',
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => body,
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await getPublicBookingManageBySlug(slug, bookingId, token)

    expect(result).toEqual(body)
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/public/salons/${slug}/bookings/${bookingId}/manage`,
      {
        headers: { 'X-Booking-Manage-Token': token },
        signal: undefined,
      },
    )
  })

  it('throws ApiError with backend detail on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: async () => ({ detail: 'Not found', code: 'not_found' }),
      }),
    )

    const err = await getPublicBookingManageBySlug(slug, bookingId, token).catch(
      (e: unknown) => e,
    )

    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({
      status: 404,
      message: 'Not found',
      code: 'not_found',
    })
  })
})

describe('getPublicShowcase', () => {
  const body: PublicShowcaseResponse = {
    salon_id: 'salon-1',
    items: [
      {
        id: 'item-1',
        category: 'work',
        title: 'Образ для фотосессии',
        description: null,
        price_cents: null,
        image_url: '/api/v1/public/salons/demo/showcase/items/item-1/image',
      },
    ],
  }

  it('encodes the slug and requests the first 50 items without a category', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => body,
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(getPublicShowcase('salon / demo')).resolves.toEqual(body)

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/public/salons/salon%20%2F%20demo/showcase?limit=50&offset=0',
    )
  })

  it.each(['work', 'cosmetics', 'dyes', 'varnishes'] as const)(
    'passes the selected category %s',
    async (category) => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => body,
      })
      vi.stubGlobal('fetch', fetchMock)

      await getPublicShowcase('demo-salon', category)

      expect(fetchMock).toHaveBeenCalledWith(
        `/api/v1/public/salons/demo-salon/showcase?limit=50&offset=0&category=${category}`,
      )
    },
  )

  it('converts HTTP errors to ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: async () => ({ detail: 'salon not found', code: 'not_found' }),
      }),
    )

    await expect(getPublicShowcase('missing')).rejects.toMatchObject({
      status: 404,
      message: 'salon not found',
      code: 'not_found',
    })
  })

  it('converts network errors without exposing the original error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new Error('synthetic socket detail')),
    )

    await expect(getPublicShowcase('demo-salon')).rejects.toMatchObject({
      status: 0,
      message: 'network error',
    })
  })
})

describe('getPublicReviews', () => {
  it('encodes the salon slug and forwards an abort signal', async () => {
    const body = { salon_id: 'salon-1', reviews: [] }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => body,
    })
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()

    await expect(getPublicReviews('salon / demo', controller.signal)).resolves.toEqual(
      body,
    )

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/public/salons/salon%20%2F%20demo/reviews',
      { signal: controller.signal },
    )
  })
})
