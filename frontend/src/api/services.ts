import { ApiError } from './errors'
import type {
  ListServicesParams,
  ServiceCreateBody,
  ServiceListItem,
  ServiceUpdateBody,
} from '../types/services'
import type { StaffListItem } from '../types/staff'

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

function buildQuery(params: ListServicesParams): string {
  const search = new URLSearchParams()
  if (params.active_only !== undefined) {
    search.set('active_only', String(params.active_only))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export async function fetchAdminServices(
  token: string,
  salonId: string,
  params: ListServicesParams = {},
): Promise<ServiceListItem[]> {
  const query = buildQuery(params)
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/services${query}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as ServiceListItem[]
}

export async function fetchAdminStaffForService(
  token: string,
  salonId: string,
  serviceId: string,
): Promise<StaffListItem[]> {
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/services/${encodeURIComponent(serviceId)}/staff`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as StaffListItem[]
}

function servicesBase(salonId: string): string {
  return `/api/v1/salons/${encodeURIComponent(salonId)}/services`
}

export async function createAdminService(
  token: string,
  salonId: string,
  body: ServiceCreateBody,
): Promise<ServiceListItem> {
  const response = await fetch(servicesBase(salonId), {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as ServiceListItem
}

export async function patchAdminService(
  token: string,
  salonId: string,
  serviceId: string,
  body: ServiceUpdateBody,
): Promise<ServiceListItem> {
  const response = await fetch(
    `${servicesBase(salonId)}/${encodeURIComponent(serviceId)}`,
    {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as ServiceListItem
}

export async function attachAdminStaffToService(
  token: string,
  salonId: string,
  serviceId: string,
  staffId: string,
): Promise<StaffListItem> {
  const response = await fetch(
    `${servicesBase(salonId)}/${encodeURIComponent(serviceId)}/staff/${encodeURIComponent(staffId)}`,
    {
      method: 'PUT',
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as StaffListItem
}

export async function detachAdminStaffFromService(
  token: string,
  salonId: string,
  serviceId: string,
  staffId: string,
): Promise<void> {
  const response = await fetch(
    `${servicesBase(salonId)}/${encodeURIComponent(serviceId)}/staff/${encodeURIComponent(staffId)}`,
    {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
}
