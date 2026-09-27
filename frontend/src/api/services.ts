import { ApiError } from './errors'
import type { ListServicesParams, ServiceListItem } from '../types/services'

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
