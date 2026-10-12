import { describe, expect, it } from 'vitest'
import {
  formToCreateBody,
  timeInputToApi,
  workingHoursFormToCreateBody,
} from './scheduleFormBodies'

describe('scheduleFormBodies (shared with impact builders)', () => {
  it('timeInputToApi appends seconds for HH:mm', () => {
    expect(timeInputToApi('09:30')).toBe('09:30:00')
  })

  it('workingHoursFormToCreateBody applies staff scope', () => {
    const body = workingHoursFormToCreateBody(
      {
        dayOfWeek: 4,
        startTime: '10:00',
        endTime: '18:00',
        effectiveFrom: '',
        effectiveTo: '',
      },
      null,
    )
    expect(body.staff_id).toBeNull()
    expect(body.start_time).toBe('10:00:00')
  })

  it('formToCreateBody maps empty staffId to null', () => {
    const body = formToCreateBody({
      staffId: '',
      startsAtLocal: '2026-08-01T09:00',
      endsAtLocal: '2026-08-01T10:00',
      reason: '',
      blockType: 'time_off',
    })
    expect(body.staff_id).toBeNull()
    expect(body.block_type).toBe('time_off')
  })
})
