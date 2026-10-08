import { describe, expect, it } from 'vitest'
import { mapServiceAvailabilityToSelectedSlots } from './publicSalon'
import type { ServiceAvailabilityResponse } from '../types/publicCatalog'

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
