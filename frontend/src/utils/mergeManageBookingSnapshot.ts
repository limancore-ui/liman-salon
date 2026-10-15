import type { PublicBookingManageResponse } from '../api/publicSalon'
import type { ManageBookingSnapshot } from '../types/publicBooking'

function preferNonEmpty(apiValue: string, baseValue: string): string {
  return apiValue.trim() !== '' ? apiValue : baseValue
}

/** Merge GET /manage fields into a client snapshot without wiping known values with empties. */
export function mergeManageApiIntoSnapshot(
  base: ManageBookingSnapshot,
  api: PublicBookingManageResponse,
): ManageBookingSnapshot {
  const holdFromApi =
    api.hold_expires_at === null || api.hold_expires_at === undefined
      ? base.hold_expires_at
      : api.hold_expires_at

  return {
    ...base,
    booking_id: preferNonEmpty(api.booking_id, base.booking_id),
    status: preferNonEmpty(api.status, base.status ?? ''),
    service_id: preferNonEmpty(api.service_id, base.service_id),
    service_name: preferNonEmpty(api.service_name, base.service_name),
    staff_id: preferNonEmpty(api.staff_id, base.staff_id),
    staff_display_name: preferNonEmpty(
      api.staff_display_name,
      base.staff_display_name,
    ),
    service_start: preferNonEmpty(api.service_start, base.service_start),
    service_end: preferNonEmpty(api.service_end, base.service_end),
    hold_expires_at: preferNonEmpty(holdFromApi, base.hold_expires_at),
    can_cancel: api.can_cancel,
    can_reschedule: api.can_reschedule,
  }
}

/** User-facing message when GET manage fails fatally (e.g. confirmed 404). */
export function mapPublicManageBookingLoadFatalError(): string {
  return 'Запись не найдена или ссылка недействительна.'
}
