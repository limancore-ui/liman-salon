import { ApiError } from './errors'
import type {
  PublicSalonEntryResponse,
  PublicSalonWithMedia,
  PublicSelectedSlot,
} from '../types/publicSalon'
import type {
  PublicBookingCreatePayload,
  PublicBookingCreateResponse,
} from '../types/publicBooking'
import type {
  PublicCatalogServiceOut,
  PublicCatalogServiceWithMedia,
  PublicCatalogServicesResponse,
  PublicCatalogStaffOut,
  PublicCatalogStaffWithMedia,
  PublicCatalogStaffResponse,
  ServiceAvailabilityResponse,
} from '../types/publicCatalog'
import { resolvePublicMediaUrl } from '../utils/publicMedia'

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

export function mapPublicSalonWithMedia(
  slug: string,
  entry: PublicSalonEntryResponse,
): PublicSalonWithMedia {
  return {
    ...entry,
    logo_url: resolvePublicMediaUrl(slug, entry.logo_media_id),
  }
}

export function mapPublicServiceWithMedia(
  slug: string,
  service: PublicCatalogServiceOut,
): PublicCatalogServiceWithMedia {
  return {
    ...service,
    cover_url: resolvePublicMediaUrl(slug, service.cover_media_id),
  }
}

export function mapPublicStaffWithMedia(
  slug: string,
  member: PublicCatalogStaffOut,
): PublicCatalogStaffWithMedia {
  return {
    ...member,
    avatar_url: resolvePublicMediaUrl(slug, member.avatar_media_id),
  }
}

export async function getPublicSalon(
  slug: string,
): Promise<PublicSalonWithMedia> {
  const response = await fetch(
    `/api/v1/public/salons/${encodeURIComponent(slug)}`,
  )
  const entry = await parseJsonResponse<PublicSalonEntryResponse>(response)
  return mapPublicSalonWithMedia(slug, entry)
}

export type PublicCatalogServicesWithMedia = {
  salon_id: string
  services: PublicCatalogServiceWithMedia[]
}

export async function getPublicServices(
  slug: string,
): Promise<PublicCatalogServicesWithMedia> {
  const response = await fetch(
    `/api/v1/public/salons/${encodeURIComponent(slug)}/services`,
  )
  const body = await parseJsonResponse<PublicCatalogServicesResponse>(response)
  return {
    salon_id: body.salon_id,
    services: body.services.map((service) =>
      mapPublicServiceWithMedia(slug, service),
    ),
  }
}

export type PublicCatalogStaffWithMediaResponse = {
  salon_id: string
  service_id: string
  staff: PublicCatalogStaffWithMedia[]
}

export async function getPublicServiceStaff(
  slug: string,
  serviceId: string,
): Promise<PublicCatalogStaffWithMediaResponse> {
  const response = await fetch(
    `/api/v1/public/salons/${encodeURIComponent(slug)}/services/${encodeURIComponent(serviceId)}/staff`,
  )
  const body = await parseJsonResponse<PublicCatalogStaffResponse>(response)
  return {
    salon_id: body.salon_id,
    service_id: body.service_id,
    staff: body.staff.map((member) => mapPublicStaffWithMedia(slug, member)),
  }
}

export type PublicServiceAvailabilityParams = {
  serviceId: string
  /** Omit when aggregating slots for any bookable staff. */
  staffId?: string
  startDate: string
  endDate: string
}

export function mapServiceAvailabilityToSelectedSlots(
  response: ServiceAvailabilityResponse,
  staffId: string | undefined,
): PublicSelectedSlot[] {
  const rows =
    staffId !== undefined
      ? response.staff.filter((entry) => entry.staff_id === staffId)
      : response.staff

  const slots: PublicSelectedSlot[] = []
  for (const row of rows) {
    for (const slot of row.slots) {
      slots.push({
        staff_id: row.staff_id,
        service_start: slot.service_start,
        service_end: slot.service_end,
      })
    }
  }
  slots.sort((a, b) => a.service_start.localeCompare(b.service_start))
  return slots
}

export async function getPublicServiceAvailability(
  slug: string,
  params: PublicServiceAvailabilityParams,
): Promise<ServiceAvailabilityResponse> {
  const query = new URLSearchParams({
    service_id: params.serviceId,
    start_date: params.startDate,
    end_date: params.endDate,
  })
  if (params.staffId !== undefined) {
    query.set('staff_id', params.staffId)
  }
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
