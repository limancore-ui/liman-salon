import { ApiError } from '../api/errors'
import { t, type MessageKey } from '../i18n'

const CODE_MESSAGE_KEYS: Record<string, MessageKey> = {
  forbidden: 'admin.error.forbidden',
  not_found: 'admin.error.notFound',
  slot_not_available: 'admin.bookingError.slotUnavailable',
  booking_overlap: 'admin.bookingError.slotUnavailable',
}

/**
 * Safe Russian user-facing message for admin UI errors.
 * Does not expose raw backend detail strings.
 */
export function adminUserErrorMessage(
  err: unknown,
  fallback: MessageKey = 'admin.error.generic',
): string {
  if (err instanceof ApiError) {
    if (err.status === 0) {
      return t('common.networkError')
    }
    if (err.code) {
      const byCode = CODE_MESSAGE_KEYS[err.code]
      if (byCode) {
        return t(byCode)
      }
    }
    if (err.status === 403) {
      return t('admin.error.forbidden')
    }
    if (err.status === 404) {
      return t('admin.error.notFound')
    }
    if (err.status === 409) {
      return t('admin.error.conflict')
    }
    if (err.status === 422) {
      return t('admin.error.validation')
    }
    return t(fallback)
  }
  return t(fallback)
}
