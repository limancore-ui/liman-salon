import { t, type MessageKey } from './index'

const STATUS_LABEL_KEYS: Record<string, MessageKey> = {
  pending: 'admin.status.pending',
  confirmed: 'admin.status.confirmed',
  in_progress: 'admin.status.inProgress',
  completed: 'admin.status.completed',
  cancelled: 'admin.status.cancelled',
  no_show: 'admin.status.noShow',
  expired: 'admin.status.expired',
}

/** Display label for a booking status API value. Unknown codes fall back safely. */
export function bookingStatusLabel(status: string): string {
  const key = STATUS_LABEL_KEYS[status]
  if (key) {
    return t(key)
  }
  return status.replaceAll('_', ' ')
}
