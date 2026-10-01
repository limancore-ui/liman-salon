import { describe, expect, it } from 'vitest'
import {
  buildAdminBookingsFilterPath,
  parseAdminBookingsFilterParams,
} from './adminBookingsFilterParams'

describe('parseAdminBookingsFilterParams', () => {
  it('reads status and date range from search params', () => {
    const params = new URLSearchParams(
      'status=pending&date_from=2026-09-25&date_to=2026-09-25',
    )
    expect(parseAdminBookingsFilterParams(params)).toEqual({
      dateFrom: '2026-09-25',
      dateTo: '2026-09-25',
      status: 'pending',
    })
  })

  it('ignores invalid status and date values', () => {
    const params = new URLSearchParams(
      'status=unknown&date_from=not-a-date&date_to=2026-01-02',
    )
    expect(parseAdminBookingsFilterParams(params)).toEqual({
      dateFrom: '',
      dateTo: '2026-01-02',
      status: '',
    })
  })
})

describe('buildAdminBookingsFilterPath', () => {
  it('builds deep link with salon date and status', () => {
    expect(buildAdminBookingsFilterPath('2026-09-25', 'confirmed')).toBe(
      '/admin/bookings?date_from=2026-09-25&date_to=2026-09-25&status=confirmed',
    )
  })

  it('omits invalid status', () => {
    expect(buildAdminBookingsFilterPath('2026-09-25', 'bogus')).toBe(
      '/admin/bookings?date_from=2026-09-25&date_to=2026-09-25',
    )
  })
})
