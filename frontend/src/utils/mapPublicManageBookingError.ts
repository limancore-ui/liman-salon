import { ApiError } from '../api/errors'

/** User-facing message for cancel/reschedule; does not expose raw backend details. */
export function mapPublicManageBookingError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) {
      return 'Запись не найдена или ссылка недействительна.'
    }
    if (err.status === 409) {
      return 'Выбранное время уже занято.'
    }
    if (err.status === 422) {
      return 'Запись нельзя изменить в текущем статусе. Обратитесь в салон.'
    }
    if (err.status === 0) {
      return 'Нет связи с сервером. Проверьте интернет и попробуйте снова.'
    }
    return 'Не удалось выполнить действие. Попробуйте позже.'
  }
  return 'Нет связи с сервером. Проверьте интернет и попробуйте снова.'
}

export function isManageSlotConflictError(err: unknown): boolean {
  if (!(err instanceof ApiError) || err.status !== 409) {
    return false
  }
  if (err.code === 'slot_not_available' || err.code === 'booking_overlap') {
    return true
  }
  return err.code === undefined
}
