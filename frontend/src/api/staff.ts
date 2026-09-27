import { ApiError } from './errors'
import type { ListStaffParams, StaffListItem } from '../types/staff'

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
