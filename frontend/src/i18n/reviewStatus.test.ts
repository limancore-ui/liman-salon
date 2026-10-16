import { describe, expect, it } from 'vitest'
import { reviewStatusLabel } from './reviewStatus'

describe('reviewStatusLabel', () => {
  it('maps known review API statuses to Russian labels', () => {
    expect(reviewStatusLabel('pending')).toBe('Ожидает')
    expect(reviewStatusLabel('published')).toBe('Опубликован')
    expect(reviewStatusLabel('rejected')).toBe('Отклонён')
    expect(reviewStatusLabel('hidden')).toBe('Скрыт')
  })

  it('falls back safely for unknown status codes', () => {
    expect(reviewStatusLabel('awaiting_moderation')).toBe('awaiting moderation')
  })
})
