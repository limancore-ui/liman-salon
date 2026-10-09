import { ApiError } from '../api/errors'
import type { StaffListItem } from '../types/staff'

export type ServiceStaffAction = 'attach' | 'detach'

export function serviceStaffActionPendingKey(
  serviceId: string,
  staffId: string,
  action: ServiceStaffAction,
): string {
  return `${serviceId}:${staffId}:${action}`
}

function staffSortKey(row: StaffListItem): [number, string, string] {
  return [row.sort_order, row.display_name.toLocaleLowerCase(), row.id]
}

export function sortStaffList(rows: StaffListItem[]): StaffListItem[] {
  return [...rows].sort((a, b) => {
    const ka = staffSortKey(a)
    const kb = staffSortKey(b)
    for (let i = 0; i < ka.length; i += 1) {
      if (ka[i] < kb[i]) {
        return -1
      }
      if (ka[i] > kb[i]) {
        return 1
      }
    }
    return 0
  })
}

export function assignedStaffIdSet(assigned: StaffListItem[]): Set<string> {
  return new Set(assigned.map((row) => row.id))
}

/** Salon roster members not yet linked to the service. */
export function staffAvailableToAssign(
  salonStaff: StaffListItem[],
  assigned: StaffListItem[],
): StaffListItem[] {
  const linked = assignedStaffIdSet(assigned)
  return sortStaffList(salonStaff.filter((row) => !linked.has(row.id)))
}

export function assignedStaffSummary(assigned: StaffListItem[] | undefined): string {
  if (assigned === undefined) {
    return 'Staff'
  }
  if (assigned.length === 0) {
    return 'No staff assigned'
  }
  const names = sortStaffList(assigned).map((row) => row.display_name)
  if (names.length <= 2) {
    return names.join(', ')
  }
  return `${names.slice(0, 2).join(', ')} +${names.length - 2}`
}

export function mapAdminServiceStaffAssignError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 403) {
      return 'You do not have permission to change staff assignments.'
    }
    if (err.status === 404) {
      return err.message.trim() !== ''
        ? err.message
        : 'Service or staff member was not found.'
    }
    if (err.status === 422 && err.message.trim() !== '') {
      return err.message
    }
    if (err.status === 0) {
      return 'Could not reach the server. Check your connection and try again.'
    }
    return 'Could not update staff assignment. Try again later.'
  }
  return 'Could not reach the server. Check your connection and try again.'
}

export function mapAdminServiceStaffLoadError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 403) {
      return 'You do not have permission to view staff assignments.'
    }
    if (err.status === 404) {
      return 'Service not found.'
    }
    if (err.status === 0) {
      return 'Could not reach the server. Check your connection and try again.'
    }
    return 'Could not load assigned staff. Try again later.'
  }
  return 'Could not reach the server. Check your connection and try again.'
}

/** Staff-panel `colSpan` on AdminServicesPage (must equal rendered `<th>` count). */
export function adminServicesTableColumnCount(canWrite: boolean): number {
  // Name, Description, Duration, Price, Active, Cover (+ Actions when owner/admin).
  const catalogColumns = 6
  return catalogColumns + (canWrite ? 1 : 0)
}
