import { describe, expect, it } from 'vitest'
import {
  WORKING_HOURS_TIMES_REQUIRED_MESSAGE,
  WORKING_HOURS_TIME_ORDER_MESSAGE,
  validateWorkingHoursForm,
} from './scheduleFormValidation'

describe('validateWorkingHoursForm', () => {
  it('accepts start before end', () => {
    expect(validateWorkingHoursForm({ startTime: '09:00', endTime: '17:00' })).toBeNull()
  })

  it('accepts HH:mm:ss values', () => {
    expect(
      validateWorkingHoursForm({ startTime: '09:00:00', endTime: '09:00:01' }),
    ).toBeNull()
  })

  it('rejects an empty start time', () => {
    expect(validateWorkingHoursForm({ startTime: '', endTime: '17:00' })).toBe(
      WORKING_HOURS_TIMES_REQUIRED_MESSAGE,
    )
  })

  it('rejects an empty end time', () => {
    expect(validateWorkingHoursForm({ startTime: '09:00', endTime: '' })).toBe(
      WORKING_HOURS_TIMES_REQUIRED_MESSAGE,
    )
  })

  it('rejects both times empty', () => {
    expect(validateWorkingHoursForm({ startTime: '', endTime: '' })).toBe(
      WORKING_HOURS_TIMES_REQUIRED_MESSAGE,
    )
  })

  it('rejects malformed times', () => {
    expect(validateWorkingHoursForm({ startTime: 'abc', endTime: '17:00' })).toBe(
      WORKING_HOURS_TIMES_REQUIRED_MESSAGE,
    )
    expect(validateWorkingHoursForm({ startTime: '09:00', endTime: '25:00' })).toBe(
      WORKING_HOURS_TIMES_REQUIRED_MESSAGE,
    )
  })

  it('rejects start equal to end', () => {
    expect(validateWorkingHoursForm({ startTime: '09:00', endTime: '09:00' })).toBe(
      WORKING_HOURS_TIME_ORDER_MESSAGE,
    )
  })

  it('rejects start after end', () => {
    expect(validateWorkingHoursForm({ startTime: '18:00', endTime: '09:00' })).toBe(
      WORKING_HOURS_TIME_ORDER_MESSAGE,
    )
  })
})
