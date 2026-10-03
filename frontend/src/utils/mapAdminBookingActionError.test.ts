import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/errors'
import {
  isAdminBookingSlotConflictError,
  mapAdminBookingActionError,
  mapAdminBookingCreateError,
} from './mapAdminBookingActionError'

describe('mapAdminBookingActionError', () => {
  it('maps known HTTP statuses', () => {
    expect(mapAdminBookingActionError(new ApiError(404, 'x'))).toBe('Booking not found.')
    expect(mapAdminBookingActionError(new ApiError(422, 'x'))).toBe(
      'This booking cannot be changed in its current status.',
    )
    expect(mapAdminBookingActionError(new ApiError(409, 'x'))).toBe(
      'The selected time is not available.',
    )
  })
})

describe('mapAdminBookingCreateError', () => {
  it('surfaces backend detail on 422', () => {
    expect(mapAdminBookingCreateError(new ApiError(422, 'staff is not active'))).toBe(
      'staff is not active',
    )
  })
})

describe('isAdminBookingSlotConflictError', () => {
  it('detects slot conflict codes and legacy 409 without code', () => {
    expect(isAdminBookingSlotConflictError(new ApiError(409, 'x', 'slot_not_available'))).toBe(
      true,
    )
    expect(isAdminBookingSlotConflictError(new ApiError(409, 'x', 'booking_overlap'))).toBe(true)
    expect(isAdminBookingSlotConflictError(new ApiError(409, 'x'))).toBe(true)
    expect(isAdminBookingSlotConflictError(new ApiError(422, 'x'))).toBe(false)
  })
})
