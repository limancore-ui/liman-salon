import { ApiError } from './errors'
import type {
  AdminReviewListItem,
  AdminReviewModerationResponse,
} from '../types/reviews'

type ApiErrorBody = {
  detail?: string
  code?: string
}

async function readApiError(response: Response): Promise<ApiError> {
  let detail = response.statusText
  let code: string | undefined
  try {
    const body = (await response.json()) as ApiErrorBody
    if (typeof body.detail === 'string') {
      detail = body.detail
    }
    if (typeof body.code === 'string') {
      code = body.code
    }
  } catch {
    /* ignore */
  }
  return new ApiError(response.status, detail, code)
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as T
}

export async function fetchAdminReviews(
  token: string,
  salonId: string,
): Promise<AdminReviewListItem[]> {
  const response = await fetch(`/api/v1/salons/${encodeURIComponent(salonId)}/reviews`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return parseJsonResponse<AdminReviewListItem[]>(response)
}

async function postModeration(
  token: string,
  salonId: string,
  reviewId: string,
  action: 'publish' | 'reject' | 'hide',
): Promise<AdminReviewModerationResponse> {
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/reviews/${encodeURIComponent(reviewId)}/${action}`,
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  return parseJsonResponse<AdminReviewModerationResponse>(response)
}

export function publishAdminReview(
  token: string,
  salonId: string,
  reviewId: string,
): Promise<AdminReviewModerationResponse> {
  return postModeration(token, salonId, reviewId, 'publish')
}

export function rejectAdminReview(
  token: string,
  salonId: string,
  reviewId: string,
): Promise<AdminReviewModerationResponse> {
  return postModeration(token, salonId, reviewId, 'reject')
}

export function hideAdminReview(
  token: string,
  salonId: string,
  reviewId: string,
): Promise<AdminReviewModerationResponse> {
  return postModeration(token, salonId, reviewId, 'hide')
}
