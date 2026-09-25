import { ApiError } from '../api/errors'

/** User-facing message; does not expose raw backend details. */
export function mapPublicBookingError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 409) {
      return 'Это время уже занято. Выберите другое время.'
    }
    if (err.status === 404) {
      return 'Салон или услуга не найдены.'
    }
    if (err.status === 422) {
      return 'Не удалось создать запись. Проверьте данные и попробуйте снова.'
    }
    if (err.status === 0) {
      return 'Нет связи с сервером. Проверьте интернет и попробуйте снова.'
    }
    return 'Не удалось создать запись. Попробуйте позже.'
  }
  return 'Нет связи с сервером. Проверьте интернет и попробуйте снова.'
}

export function isSlotConflictError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 409
}
