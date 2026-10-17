import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/errors'
import {
  isAdminBookingSlotConflictError,
  mapAdminBookingActionError,
  mapAdminBookingCreateError,
} from './mapAdminBookingActionError'

describe('mapAdminBookingActionError', () => {
  it('maps known HTTP statuses', () => {
    expect(mapAdminBookingActionError(new ApiError(404, 'x'))).toBe('Запись не найдена.')
    expect(mapAdminBookingActionError(new ApiError(422, 'x'))).toBe(
      'Эту запись нельзя изменить в текущем статусе.',
    )
    expect(mapAdminBookingActionError(new ApiError(409, 'x'))).toBe(
      'Выбранное время недоступно.',
    )
  })
})

describe('mapAdminBookingCreateError', () => {
  it('maps 422 without exposing raw backend detail', () => {
    expect(mapAdminBookingCreateError(new ApiError(422, 'staff is not active'))).toBe(
      'Эту запись нельзя изменить в текущем статусе.',
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
