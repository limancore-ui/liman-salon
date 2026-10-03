import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/errors'
import { mapPublicReviewError } from './mapPublicReviewError'

describe('mapPublicReviewError', () => {
  it('maps conflict to already reviewed message', () => {
    expect(mapPublicReviewError(new ApiError(409, 'conflict', 'conflict'))).toMatch(
      /уже оставили/i,
    )
  })

  it('maps validation errors', () => {
    expect(
      mapPublicReviewError(new ApiError(422, 'review can only', 'validation_error')),
    ).toBe('review can only')
  })
})
