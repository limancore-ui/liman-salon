import { ApiError } from '../api/errors'
import type { StaffListItem } from '../types/staff'
import { t } from '../i18n'
import { adminUserErrorMessage } from './adminUserError'

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
    return t('admin.services.staffSummary')
  }
  if (assigned.length === 0) {
    return t('admin.services.noStaffAssigned')
  }
  const names = sortStaffList(assigned).map((row) => row.display_name)
  if (names.length <= 2) {
    return names.join(', ')
  }
  return `${names.slice(0, 2).join(', ')} +${names.length - 2}`
}

export function mapAdminServiceStaffAssignError(err: unknown): string {
  if (err instanceof ApiError && err.status === 403) {
    return t('admin.services.assignForbidden')
  }
  if (err instanceof ApiError && err.status === 404) {
    return t('admin.services.assignNotFound')
  }
  return adminUserErrorMessage(err, 'admin.services.assignFailed')
}

export function mapAdminServiceStaffLoadError(err: unknown): string {
  if (err instanceof ApiError && err.status === 403) {
    return t('admin.services.assignViewForbidden')
  }
  if (err instanceof ApiError && err.status === 404) {
    return t('admin.services.serviceNotFound')
  }
  return adminUserErrorMessage(err, 'admin.services.assignLoadFailed')
}

/** Staff-panel `colSpan` on AdminServicesPage (must equal rendered `<th>` count). */
export function adminServicesTableColumnCount(canWrite: boolean): number {
  // Name, Description, Duration, Price, Active, Cover (+ Actions when owner/admin).
  const catalogColumns = 6
  return catalogColumns + (canWrite ? 1 : 0)
}
