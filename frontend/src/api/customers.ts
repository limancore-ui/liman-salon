import { ApiError } from './errors'
import type { CustomerListItem, ListCustomersParams } from '../types/customers'

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

function buildQuery(params: ListCustomersParams): string {
  const search = new URLSearchParams()
  if (params.q !== undefined && params.q !== '') {
    search.set('q', params.q)
  }
  if (params.limit !== undefined) {
    search.set('limit', String(params.limit))
  }
  if (params.offset !== undefined) {
    search.set('offset', String(params.offset))
  }
  if (params.sort !== undefined) {
    search.set('sort', params.sort)
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export async function fetchAdminCustomers(
  token: string,
  salonId: string,
  params: ListCustomersParams = {},
): Promise<CustomerListItem[]> {
  const query = buildQuery(params)
  const response = await fetch(
    `/api/v1/salons/${encodeURIComponent(salonId)}/customers${query}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!response.ok) {
    throw await readApiError(response)
  }
  return (await response.json()) as CustomerListItem[]
}
