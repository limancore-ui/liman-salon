import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/errors'
import { mapPublicReviewError } from './mapPublicReviewError'

describe('mapPublicReviewError', () => {
  it('maps conflict to already reviewed message', () => {
    expect(mapPublicReviewError(new ApiError(409, 'conflict', 'conflict'))).toMatch(
      /уже оставили/i,
    )
  })

  it('maps incomplete-visit validation to Russian copy', () => {
    expect(
      mapPublicReviewError(
        new ApiError(
          422,
          'review can only be submitted for a completed booking',
          'validation_error',
        ),
      ),
    ).toBe('Отзыв можно оставить после завершения визита')
  })

  it('maps other validation errors to detail or fallback', () => {
    expect(
      mapPublicReviewError(new ApiError(422, 'rating must be between 1 and 5', 'validation_error')),
    ).toBe('rating must be between 1 and 5')
  })
})
