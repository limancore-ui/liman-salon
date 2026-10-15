import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './errors'
import { createWorkingHours, previewScheduleImpact } from './schedule'

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

describe('createWorkingHours', () => {
  it('POSTs the frozen proposal together with the canonical preview gate', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'wh-new',
        staff_id: null,
        day_of_week: 1,
        start_time: '09:00:00',
        end_time: '17:00:00',
        effective_from: null,
        effective_to: null,
        created_at: '2026-01-01T12:00:00+00:00',
        updated_at: '2026-01-01T12:00:00+00:00',
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const body = {
      staff_id: null,
      day_of_week: 1,
      start_time: '09:00:00',
      end_time: '17:00:00',
      effective_from: null,
      effective_to: null,
      impact_fingerprint: 'a'.repeat(64),
      as_of: '2026-03-15T08:30:00+00:00',
      horizon_days: 30,
      acknowledge_impacts: true,
    }

    await createWorkingHours(token, salonId, body)

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/salons/${salonId}/schedule/working-hours`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      },
    )
    const sent = JSON.parse(String(fetchMock.mock.calls[0][1].body)) as Record<string, unknown>
    expect(sent.impact_fingerprint).toBe('a'.repeat(64))
    expect(sent.as_of).toBe('2026-03-15T08:30:00+00:00')
    expect(sent.horizon_days).toBe(30)
    expect(sent.acknowledge_impacts).toBe(true)
    expect(sent).not.toHaveProperty('impact_offset')
    expect(sent).not.toHaveProperty('impact_limit')
    expect(sent).not.toHaveProperty('kind')
  })
})
