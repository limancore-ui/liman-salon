import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/errors'
import type { StaffListItem } from '../types/staff'
import {
  assignedStaffSummary,
  serviceStaffActionPendingKey,
  staffAvailableToAssign,
  mapAdminServiceStaffAssignError,
} from './adminServiceStaffAssign'

function staff(id: string, display_name: string, sort_order = 0): StaffListItem {
  return {
    id,
    display_name,
    title: null,
    bio: null,
    color_hex: null,
    is_bookable: true,
    is_active: true,
    sort_order,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
}

describe('serviceStaffActionPendingKey', () => {
  it('combines service, staff, and action', () => {
    expect(serviceStaffActionPendingKey('svc-1', 'st-1', 'attach')).toBe(
      'svc-1:st-1:attach',
    )
  })
})

describe('staffAvailableToAssign', () => {
  it('excludes already assigned staff and sorts by sort_order then name', () => {
    const salon = [
      staff('b', 'Bravo', 1),
      staff('a', 'Alpha', 0),
      staff('c', 'Charlie', 2),
    ]
    const assigned = [staff('a', 'Alpha', 0)]
    expect(staffAvailableToAssign(salon, assigned).map((row) => row.id)).toEqual([
      'b',
      'c',
    ])
  })
})

describe('assignedStaffSummary', () => {
  it('formats empty, short, and truncated lists', () => {
    expect(assignedStaffSummary(undefined)).toBe('Staff')
    expect(assignedStaffSummary([])).toBe('No staff assigned')
    expect(assignedStaffSummary([staff('1', 'Alex')])).toBe('Alex')
    expect(
      assignedStaffSummary([
        staff('1', 'Alex'),
        staff('2', 'Blair'),
        staff('3', 'Casey'),
      ]),
    ).toBe('Alex, Blair +1')
  })
})

describe('mapAdminServiceStaffAssignError', () => {
  it('maps forbidden, not found, and network errors', () => {
    expect(mapAdminServiceStaffAssignError(new ApiError(403, 'Forbidden'))).toContain(
      'permission',
    )
    expect(mapAdminServiceStaffAssignError(new ApiError(404, 'missing'))).toBe('missing')
    expect(mapAdminServiceStaffAssignError(new ApiError(0, ''))).toContain('connection')
    expect(mapAdminServiceStaffAssignError(new Error('offline'))).toContain('connection')
  })
})
