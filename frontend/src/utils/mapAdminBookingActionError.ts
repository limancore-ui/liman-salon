import { ApiError } from '../api/errors'

/** User-facing message for admin cancel/reschedule; does not expose raw backend details. */
export function mapAdminBookingActionError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) {
      return 'Booking not found.'
    }
    if (err.status === 403) {
      return 'You do not have permission to change this booking.'
    }
    if (err.status === 409) {
      return 'The selected time is not available.'
    }
    if (err.status === 422) {
      return 'This booking cannot be changed in its current status.'
    }
    if (err.status === 0) {
      return 'Could not reach the server. Check your connection and try again.'
    }
    return 'Could not complete the action. Try again later.'
  }
  return 'Could not reach the server. Check your connection and try again.'
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
