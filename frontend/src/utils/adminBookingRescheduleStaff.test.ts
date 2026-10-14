import { describe, expect, it } from 'vitest'
import { initialRescheduleStaffId } from './adminBookingRescheduleStaff'
import type { BookingListItem } from '../types/bookings'
import type { StaffListItem } from '../types/staff'

function makeStaff(overrides: Partial<StaffListItem> = {}): StaffListItem {
  return {
    id: 'staff-a',
    display_name: 'Alex',
    title: null,
    bio: null,
    color_hex: null,
    is_bookable: true,
    is_active: true,
    sort_order: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function makeBooking(staffId: string): Pick<BookingListItem, 'staff_id'> {
  return { staff_id: staffId }
}

describe('initialRescheduleStaffId', () => {
  it('uses booking staff_id when two staff share display_name', () => {
    const staffList = [
      makeStaff({ id: 'staff-a', display_name: 'Alex' }),
      makeStaff({ id: 'staff-b', display_name: 'Alex' }),
    ]
    expect(initialRescheduleStaffId(staffList, makeBooking('staff-b'))).toBe('staff-b')
  })

  it('returns empty when original staff is missing from list', () => {
    const staffList = [makeStaff({ id: 'staff-other', display_name: 'Alex' })]
    expect(initialRescheduleStaffId(staffList, makeBooking('staff-gone'))).toBe('')
  })

  it('returns empty when original staff is inactive', () => {
    const staffList = [
      makeStaff({ id: 'staff-a', is_active: false }),
      makeStaff({ id: 'staff-b', display_name: 'Jordan' }),
    ]
    expect(initialRescheduleStaffId(staffList, makeBooking('staff-a'))).toBe('')
  })
})
