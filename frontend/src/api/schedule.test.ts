import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './errors'
import { previewScheduleImpact } from './schedule'

const salonId = 'salon-a'
const token = 'test-token'
const workingHoursId = 'wh-1'

const samplePreviewResponse = {
  as_of: '2026-01-01T12:00:00+00:00',
  change_summary: {
    kind: 'working_hours.delete',
    affected_staff_ids: ['staff-1'],
    horizon: {
      starts_at_from: '2026-01-01T12:00:00+00:00',
      starts_at_to: '2026-04-01T12:00:00+00:00',
      days: 90,
    },
  },
  impacts: [],
  counts: { total_impacted: 0, by_reason: {} },
  pagination: {
    offset: 0,
    limit: 50,
    returned: 0,
    total_impacted: 0,
    has_more: false,
  },
  commit_policy: {
    allow_commit_with_impacts: true,
    requires_acknowledgement: false,
  },
  impact_fingerprint: 'abc123',
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('previewScheduleImpact', () => {
  it('POSTs impact preview to schedule impact-preview endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => samplePreviewResponse,
    })
    vi.stubGlobal('fetch', fetchMock)

    const body = {
      change: {
        kind: 'working_hours.delete' as const,
        working_hours_id: workingHoursId,
      },
      horizon_days: 30,
      impact_offset: 0,
      impact_limit: 25,
    }

    const result = await previewScheduleImpact(token, salonId, body)

    expect(result).toEqual(samplePreviewResponse)
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/salons/${salonId}/schedule/impact-preview`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      },
    )
  })

  it('throws ApiError with backend detail and code on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
        json: async () => ({ detail: 'Forbidden', code: 'forbidden' }),
      }),
    )

    const err = await previewScheduleImpact(token, salonId, {
      change: {
        kind: 'working_hours.delete',
        working_hours_id: workingHoursId,
      },
    }).catch((e: unknown) => e)

    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({
      status: 403,
      message: 'Forbidden',
      code: 'forbidden',
    })
  })
})
