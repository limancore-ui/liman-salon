import { describe, expect, it } from 'vitest'
import type { PublicBookingManageResponse } from '../api/publicSalon'
import type { ManageBookingSnapshot } from '../types/publicBooking'
import { mergeManageApiIntoSnapshot } from './mergeManageBookingSnapshot'

const baseSnapshot: ManageBookingSnapshot = {
  token: 'tok',
  booking_id: 'b1',
  slug: 'salon-a',
  salon_id: 'salon-1',
  service_id: 'svc-old',
  staff_id: 'staff-old',
  service_name: 'Стрижка',
  staff_display_name: 'Anna',
  service_start: '2026-07-10T10:00:00.000Z',
  service_end: '2026-07-10T11:00:00.000Z',
  hold_expires_at: '2026-07-10T12:00:00.000Z',
  status: 'confirmed',
}

function apiResponse(
  overrides: Partial<PublicBookingManageResponse> = {},
): PublicBookingManageResponse {
  return {
    booking_id: 'b1',
    status: 'confirmed',
    service_id: 'svc-new',
    service_name: 'Окрашивание',
    staff_id: 'staff-new',
    staff_display_name: 'Boris',
    service_start: '2026-07-11T10:00:00.000Z',
    service_end: '2026-07-11T11:00:00.000Z',
    hold_expires_at: null,
    can_cancel: true,
    can_reschedule: false,
    timezone: 'Europe/Moscow',
    ...overrides,
  }
}

describe('mergeManageApiIntoSnapshot', () => {
  it('applies API fields and action flags', () => {
    const merged = mergeManageApiIntoSnapshot(baseSnapshot, apiResponse())
    expect(merged.service_id).toBe('svc-new')
    expect(merged.service_name).toBe('Окрашивание')
    expect(merged.can_cancel).toBe(true)
    expect(merged.can_reschedule).toBe(false)
    expect(merged.token).toBe('tok')
    expect(merged.slug).toBe('salon-a')
  })

  it('keeps snapshot strings when API sends empty values', () => {
    const merged = mergeManageApiIntoSnapshot(
      baseSnapshot,
      apiResponse({
        service_name: '',
        staff_display_name: '   ',
        service_start: '',
      }),
    )
    expect(merged.service_name).toBe('Стрижка')
    expect(merged.staff_display_name).toBe('Anna')
    expect(merged.service_start).toBe('2026-07-10T10:00:00.000Z')
  })

  it('keeps hold_expires_at when API returns null', () => {
    const merged = mergeManageApiIntoSnapshot(
      baseSnapshot,
      apiResponse({ hold_expires_at: null }),
    )
    expect(merged.hold_expires_at).toBe('2026-07-10T12:00:00.000Z')
  })
})
