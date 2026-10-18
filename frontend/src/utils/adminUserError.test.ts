import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/errors'
import { adminUserErrorMessage } from './adminUserError'

describe('adminUserErrorMessage', () => {
  it('maps network, forbidden, not-found, conflict, and validation by status', () => {
    expect(adminUserErrorMessage(new ApiError(0, 'network error'))).toBe(
      'Ошибка сети. Попробуйте снова.',
    )
    expect(adminUserErrorMessage(new ApiError(403, 'Forbidden'))).toBe(
      'Недостаточно прав для этого действия.',
    )
    expect(adminUserErrorMessage(new ApiError(404, 'missing'))).toBe(
      'Запрошенные данные не найдены.',
    )
    expect(adminUserErrorMessage(new ApiError(409, 'conflict'))).toBe(
      'Действие конфликтует с текущим состоянием.',
    )
    expect(adminUserErrorMessage(new ApiError(422, 'display_name required'))).toBe(
      'Проверьте введённые данные и попробуйте снова.',
    )
  })

  it('prefers known API codes over raw English detail', () => {
    expect(adminUserErrorMessage(new ApiError(403, 'x', 'forbidden'))).toBe(
      'Недостаточно прав для этого действия.',
    )
    expect(adminUserErrorMessage(new ApiError(404, 'x', 'not_found'))).toBe(
      'Запрошенные данные не найдены.',
    )
    expect(
      adminUserErrorMessage(new ApiError(409, 'x', 'slot_not_available')),
    ).toBe('Выбранное время недоступно.')
  })

  it('uses operation fallback for unknown statuses and never leaks detail', () => {
    const msg = adminUserErrorMessage(
      new ApiError(500, 'Server exploded'),
      'admin.reviews.loadFailed',
    )
    expect(msg).toBe('Не удалось загрузить отзывы.')
    expect(msg).not.toContain('Server exploded')
  })

  it('uses generic fallback for non-ApiError values', () => {
    expect(adminUserErrorMessage(new Error('boom'))).toBe(
      'Не удалось выполнить действие. Попробуйте позже.',
    )
    expect(adminUserErrorMessage(new Error('boom'), 'admin.reviews.actionFailed')).toBe(
      'Действие не выполнено.',
    )
  })
})
