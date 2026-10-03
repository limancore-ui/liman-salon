import { ApiError } from '../api/errors'

export function mapPublicReviewError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 409) {
      return 'Вы уже оставили отзыв об этом визите.'
    }
    if (err.status === 422) {
      return err.message || 'Нельзя оставить отзыв для этой записи.'
    }
    if (err.status === 404) {
      return 'Не удалось подтвердить доступ к записи.'
    }
    return err.message || 'Не удалось отправить отзыв.'
  }
  return 'Не удалось отправить отзыв.'
}
