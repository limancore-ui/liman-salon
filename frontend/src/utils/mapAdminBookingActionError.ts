import { ApiError } from '../api/errors'
import { t } from '../i18n'

/** User-facing message for admin cancel/reschedule; does not expose raw backend details. */
export function mapAdminBookingActionError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) {
      return t('admin.bookingError.notFound')
    }
    if (err.status === 403) {
      return t('admin.bookingError.forbidden')
    }
    if (err.status === 409) {
      return t('admin.bookingError.slotUnavailable')
    }
    if (err.status === 422) {
      return t('admin.bookingError.badStatus')
    }
    if (err.status === 0) {
      return t('admin.bookingError.unreachable')
    }
    return t('admin.bookingError.generic')
  }
  return t('admin.bookingError.unreachable')
}

/** Create booking: reuse action mapping without exposing raw backend detail. */
export function mapAdminBookingCreateError(err: unknown): string {
  return mapAdminBookingActionError(err)
}

export function isAdminBookingSlotConflictError(err: unknown): boolean {
  if (!(err instanceof ApiError) || err.status !== 409) {
    return false
  }
  if (err.code === 'slot_not_available' || err.code === 'booking_overlap') {
    return true
  }
  return err.code === undefined
}
