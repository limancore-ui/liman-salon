import { ApiError } from './errors'
import type { PublicSalonEntryResponse } from '../types/publicSalon'
import type {
  PublicBookingCreatePayload,
  PublicBookingCreateResponse,
} from '../types/publicBooking'
import type {
  PublicCatalogServicesResponse,
  PublicCatalogStaffResponse,
  ServiceAvailabilityResponse,
} from '../types/publicCatalog'

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

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as T
}

export async function getPublicSalon(
  slug: string,
): Promise<PublicSalonEntryResponse> {
  const response = await fetch(
    `/api/v1/public/salons/${encodeURIComponent(slug)}`,
  )
  return parseJsonResponse<PublicSalonEntryResponse>(response)
}

export async function getPublicServices(
  slug: string,
): Promise<PublicCatalogServicesResponse> {
  const response = await fetch(
    `/api/v1/public/salons/${encodeURIComponent(slug)}/services`,
  )
  return parseJsonResponse<PublicCatalogServicesResponse>(response)
}

export async function getPublicServiceStaff(
  slug: string,
  serviceId: string,
): Promise<PublicCatalogStaffResponse> {
  const response = await fetch(
    `/api/v1/public/salons/${encodeURIComponent(slug)}/services/${encodeURIComponent(serviceId)}/staff`,
  )
  return parseJsonResponse<PublicCatalogStaffResponse>(response)
}

export type PublicServiceAvailabilityParams = {
  serviceId: string
  staffId: string
  startDate: string
  endDate: string
}

export async function getPublicServiceAvailability(
  slug: string,
  params: PublicServiceAvailabilityParams,
): Promise<ServiceAvailabilityResponse> {
  const query = new URLSearchParams({
    service_id: params.serviceId,
    start_date: params.startDate,
    end_date: params.endDate,
    staff_id: params.staffId,
  })
  const response = await fetch(
    `/api/v1/public/salons/${encodeURIComponent(slug)}/availability/service?${query.toString()}`,
  )
  return parseJsonResponse<ServiceAvailabilityResponse>(response)
}

function buildBookingRequestBody(
  payload: PublicBookingCreatePayload,
): Record<string, string> {
  const body: Record<string, string> = {
    phone: payload.phone,
    full_name: payload.full_name,
    service_id: payload.service_id,
    staff_id: payload.staff_id,
    service_start: payload.service_start,
  }
  const email = payload.email?.trim()
  if (email) {
    body.email = email
  }
  const notes = payload.customer_notes?.trim()
  if (notes) {
    body.customer_notes = notes
  }
  return body
}

export async function createPublicBookingBySlug(
  slug: string,
  payload: PublicBookingCreatePayload,
): Promise<PublicBookingCreateResponse> {
  let response: Response
  try {
    response = await fetch(
      `/api/v1/public/salons/${encodeURIComponent(slug)}/bookings`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildBookingRequestBody(payload)),
      },
    )
  } catch {
    throw new ApiError(0, 'network error')
  }
  return parseJsonResponse<PublicBookingCreateResponse>(response)
}
