import { ApiError } from './errors'
import type { BookingListItem, ListBookingsParams } from '../types/bookings'

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
    /* ignore non-JSON error bodies */
  }
  return new ApiError(response.status, detail, code)
}

function buildQuery(params: ListBookingsParams): string {
  const search = new URLSearchParams()
  if (params.starts_at_from) {
    search.set('starts_at_from', params.starts_at_from)
  }
  if (params.starts_at_to) {
    search.set('starts_at_to', params.starts_at_to)
  }
  if (params.status) {
    search.set('status', params.status)
  }
  if (params.limit !== undefined) {
    search.set('limit', String(params.limit))
  }
  if (params.offset !== undefined) {
    search.set('offset', String(params.offset))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export async function fetchAdminBookings(
  token: string,
  salonId: string,
  params: ListBookingsParams = {},
): Promise<BookingListItem[]> {
  const query = buildQuery(params)
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/bookings${query}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as BookingListItem[]
}
