import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchAdminSmartGaps } from './smartGaps'
import type { SmartGapListResponse } from '../types/smartGaps'

const salonId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
const token = 'test-token'
const staffId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'

const sampleResponse: SmartGapListResponse = {
  salon_id: salonId,
  staff_id: staffId,
  gaps: [
    {
      start: '2026-09-25T09:00:00Z',
      end: '2026-09-25T11:00:00Z',
      suitable_services: [
        {
          service_id: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
          name: 'Haircut',
          duration_minutes: 60,
          price_cents: 2500,
        },
      ],
    },
  ],
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fetchAdminSmartGaps', () => {
  it('GETs smart-gaps with staff and date query params', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => sampleResponse,
      }),
    )

    const result = await fetchAdminSmartGaps(token, salonId, {
      staff_id: staffId,
      start_date: '2026-09-25',
      end_date: '2026-09-25',
    })

    expect(result).toEqual(sampleResponse)
    expect(fetch).toHaveBeenCalledWith(
      `/api/v1/salons/${salonId}/smart-gaps?staff_id=${staffId}&start_date=2026-09-25&end_date=2026-09-25`,
      expect.objectContaining({
        headers: { Authorization: `Bearer ${token}` },
      }),
    )
  })

  it('throws ApiError on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        statusText: 'Service Unavailable',
        json: async () => ({ detail: 'Unavailable', code: 'unavailable' }),
      }),
    )

    await expect(
      fetchAdminSmartGaps(token, salonId, {
        staff_id: staffId,
        start_date: '2026-09-25',
        end_date: '2026-09-25',
      }),
    ).rejects.toMatchObject({
      status: 503,
      message: 'Unavailable',
      code: 'unavailable',
    })
  })
})
