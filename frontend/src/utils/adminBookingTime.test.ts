import { describe, expect, it } from 'vitest'
import {
  addCalendarDay,
  isoToSalonLocalDatetimeLocal,
  salonLocalDateRangeToUtcIso,
  salonLocalDateTimeToIso,
} from './adminBookingTime'

describe('salonLocalDateTimeToIso', () => {
  it('maps salon wall time to UTC (America/New_York)', () => {
    expect(salonLocalDateTimeToIso('2026-09-25T09:30', 'America/New_York')).toBe(
      '2026-09-25T13:30:00.000Z',
    )
  })
})

describe('isoToSalonLocalDatetimeLocal', () => {
  it('maps UTC instant to salon datetime-local', () => {
    expect(isoToSalonLocalDatetimeLocal('2026-09-25T13:30:00.000Z', 'America/New_York')).toBe(
      '2026-09-25T09:30',
    )
  })
})

describe('salonLocalDateRangeToUtcIso', () => {
  it('uses salon-local day boundaries, not UTC midnight', () => {
    expect(
      salonLocalDateRangeToUtcIso('2026-09-25', '2026-09-25', 'America/New_York'),
    ).toEqual({
      starts_at_from: '2026-09-25T04:00:00.000Z',
      starts_at_to: '2026-09-26T04:00:00.000Z',
    })
  })

  it('falls back to UTC calendar day when timezone is UTC', () => {
    expect(salonLocalDateRangeToUtcIso('2026-09-25', '2026-09-26', 'UTC')).toEqual({
      starts_at_from: '2026-09-25T00:00:00.000Z',
      starts_at_to: '2026-09-27T00:00:00.000Z',
    })
  })
})

describe('addCalendarDay', () => {
  it('advances YYYY-MM-DD by one day', () => {
    expect(addCalendarDay('2026-09-25')).toBe('2026-09-26')
  })
})
