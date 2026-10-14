import type { BookingListItem } from '../types/bookings'
import type { StaffListItem } from '../types/staff'

/** Initial staff selection when opening reschedule; never guesses from display name. */
export function initialRescheduleStaffId(
  staffList: StaffListItem[],
  booking: Pick<BookingListItem, 'staff_id'>,
): string {
  const match = staffList.find((row) => row.id === booking.staff_id)
  if (match?.is_active) {
    return match.id
  }
  return ''
}
