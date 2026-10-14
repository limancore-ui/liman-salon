import { ApiError, formatApiErrorDetail } from './errors'
import type {
  ListStaffParams,
  StaffCreateBody,
  StaffListItem,
  StaffUpdateBody,
} from '../types/staff'

type ApiErrorBody = {
  detail?: unknown
  code?: string
}

async function readApiError(response: Response): Promise<ApiError> {
  let detail = response.statusText
  let code: string | undefined
  try {
    const body = (await response.json()) as ApiErrorBody
    const formatted = formatApiErrorDetail(body.detail)
    if (formatted !== undefined) {
      detail = formatted
    }
    if (typeof body.code === 'string') {
      code = body.code
    }
  } catch {
    /* ignore non-JSON error bodies */
  }
  return new ApiError(response.status, detail, code)
}

function buildQuery(params: ListStaffParams): string {
  const search = new URLSearchParams()
  if (params.active_only !== undefined) {
    search.set('active_only', String(params.active_only))
  }
  if (params.bookable_only !== undefined) {
    search.set('bookable_only', String(params.bookable_only))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export async function fetchAdminStaff(
  token: string,
  salonId: string,
  params: ListStaffParams = {},
): Promise<StaffListItem[]> {
  const query = buildQuery(params)
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/staff${query}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as StaffListItem[]
}

function staffCollectionUrl(salonId: string): string {
  return `/api/v1/salons/${encodeURIComponent(salonId)}/staff`
}

export async function createAdminStaff(
  token: string,
  salonId: string,
  body: StaffCreateBody,
): Promise<StaffListItem> {
  const response = await fetch(staffCollectionUrl(salonId), {
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
  return (await response.json()) as StaffListItem
}

export async function patchAdminStaff(
  token: string,
  salonId: string,
  staffId: string,
  body: StaffUpdateBody,
): Promise<StaffListItem> {
  const response = await fetch(
    `${staffCollectionUrl(salonId)}/${encodeURIComponent(staffId)}`,
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
  return (await response.json()) as StaffListItem
}
