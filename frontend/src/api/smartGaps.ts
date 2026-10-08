import { ApiError } from './errors'
import type { FetchSmartGapsParams, SmartGapListResponse } from '../types/smartGaps'

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

function buildQuery(params: FetchSmartGapsParams): string {
  const search = new URLSearchParams()
  search.set('staff_id', params.staff_id)
  search.set('start_date', params.start_date)
  search.set('end_date', params.end_date)
  return `?${search.toString()}`
}

export async function fetchAdminSmartGaps(
  token: string,
  salonId: string,
  params: FetchSmartGapsParams,
): Promise<SmartGapListResponse> {
  const query = buildQuery(params)
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/smart-gaps${query}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as SmartGapListResponse
}
