import { ApiError } from './errors'
import type {
  AdminBookingCancelRequest,
  AdminBookingCancelResponse,
  AdminBookingRescheduleRequest,
  AdminBookingRescheduleResponse,
  BookingListItem,
  ListBookingsParams,
} from '../types/bookings'

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

function bookingsBase(salonId: string): string {
  return `/api/v1/salons/${encodeURIComponent(salonId)}/bookings`
}

export async function cancelAdminBooking(
  token: string,
  salonId: string,
  bookingId: string,
  body: AdminBookingCancelRequest = {},
): Promise<AdminBookingCancelResponse> {
  const payload: Record<string, string> = {}
  const reason = body.reason?.trim()
  if (reason) {
    payload.reason = reason
  }
  const response = await fetch(
    `${bookingsBase(salonId)}/${encodeURIComponent(bookingId)}/cancel`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as AdminBookingCancelResponse
}

export async function rescheduleAdminBooking(
  token: string,
  salonId: string,
  bookingId: string,
  body: AdminBookingRescheduleRequest,
): Promise<AdminBookingRescheduleResponse> {
  const response = await fetch(
    `${bookingsBase(salonId)}/${encodeURIComponent(bookingId)}/reschedule`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        staff_id: body.staff_id,
        service_start: body.service_start,
      }),
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as AdminBookingRescheduleResponse
}
