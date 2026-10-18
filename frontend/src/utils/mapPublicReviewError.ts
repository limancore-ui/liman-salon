import { ApiError } from '../api/errors'

const INCOMPLETE_VISIT_REVIEW_MESSAGE =
  'Отзыв можно оставить после завершения визита'

function isIncompleteVisitReviewError(message: string): boolean {
  const normalized = message.toLowerCase()
  return (
    normalized.includes('completed booking') ||
    normalized.includes('only be submitted for a completed')
  )
}

export function mapPublicReviewError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 409) {
      return 'Вы уже оставили отзыв об этом визите.'
    }
    if (err.status === 422) {
      if (isIncompleteVisitReviewError(err.message)) {
        return INCOMPLETE_VISIT_REVIEW_MESSAGE
      }
      return err.message || 'Нельзя оставить отзыв для этой записи.'
    }
    if (err.status === 404) {
      return 'Не удалось подтвердить доступ к записи.'
    }
    return err.message || 'Не удалось отправить отзыв.'
  }
  return 'Не удалось отправить отзыв.'
}
