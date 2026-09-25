import { ApiError } from './errors'
import type { PublicSalonEntryResponse } from '../types/publicSalon'
import type {
  PublicCatalogServicesResponse,
  PublicCatalogStaffResponse,
  ServiceAvailabilityResponse,
} from '../types/publicCatalog'

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: string }
      if (typeof body.detail === 'string') {
        detail = body.detail
      }
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new ApiError(response.status, detail)
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
